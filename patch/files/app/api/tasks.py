import os
import logging
logger = logging.getLogger('app.logger')
import json
import datetime
from wsgiref.util import FileWrapper

import mimetypes

from shutil import copyfileobj
from django.core.exceptions import ObjectDoesNotExist, SuspiciousFileOperation, ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
from django.http import FileResponse
from django.http import HttpResponse
from rest_framework import status, serializers, viewsets, filters, exceptions, permissions, parsers
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from app import models, pending_actions
from nodeodm import status_codes
from nodeodm.models import ProcessingNode
from worker import tasks as worker_tasks
from .common import get_and_check_project, get_asset_download_filename
from app.security import path_traversal_check
from django.utils.translation import gettext_lazy as _


def flatten_files(request_files):
    # MultiValueDict in, flat array of files out
    return [file for filesList in map(
        lambda key: request_files.getlist(key),
        [keys for keys in request_files])
     for file in filesList]

class TaskIDsSerializer(serializers.BaseSerializer):
    def to_representation(self, obj):
        return obj.id

class TaskSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=models.Project.objects.all())
    processing_node = serializers.PrimaryKeyRelatedField(queryset=ProcessingNode.objects.all()) 
    processing_node_name = serializers.SerializerMethodField()
    can_rerun_from = serializers.SerializerMethodField()
    statistics = serializers.SerializerMethodField()

    def get_processing_node_name(self, obj):
        if obj.processing_node is not None:
            return str(obj.processing_node)
        else:
            return None

    def get_statistics(self, obj):
        return obj.get_statistics()

    def get_can_rerun_from(self, obj):
        """
        When a task has been associated with a processing node
        and if the processing node supports the "rerun-from" parameter
        this method returns the valid values for "rerun-from" for that particular
        processing node.

        TODO: this could be improved by returning an empty array if a task was created
        and purged by the processing node (which would require knowing how long a task is being kept
        see https://github.com/OpenDroneMap/NodeODM/issues/32
        :return: array of valid rerun-from parameters
        """
        if obj.processing_node is not None:
            rerun_from_option = list(filter(lambda d: 'name' in d and d['name'] == 'rerun-from', obj.processing_node.available_options))
            if len(rerun_from_option) > 0 and 'domain' in rerun_from_option[0]:
                return rerun_from_option[0]['domain']

        return []

    class Meta:
        model = models.Task
        exclude = ('console_output', 'orthophoto_extent', 'dsm_extent', 'dtm_extent', )
        read_only_fields = ('processing_time', 'status', 'last_error', 'created_at', 'pending_action', 'available_assets', )

class TaskViewSet(viewsets.ViewSet):
    """
    Task get/add/delete/update
    A task represents a set of images and other input to be sent to a processing node.
    Once a processing node completes processing, results are stored in the task.
    """
    queryset = models.Task.objects.all().defer('orthophoto_extent', 'dsm_extent', 'dtm_extent', 'console_output', )
    
    parser_classes = (parsers.MultiPartParser, parsers.JSONParser, parsers.FormParser, )
    ordering_fields = '__all__'

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        We don't use object level permissions on tasks, relying on
        project's object permissions instead (but standard model permissions still apply)
        and with the exception of 'retrieve' (task GET) for public tasks access
        """
        #DISABLE AUTH FOR LOCAL TESTING
        if self.action == 'retrieve':
            permission_classes = [] #[permissions.AllowAny]
        else:
            permission_classes = [] #[permissions.DjangoModelPermissions, ]

        return [permission() for permission in permission_classes]

    def set_pending_action(self, pending_action, request, pk=None, project_pk=None, perms=('change_project', )):
        get_and_check_project(request, project_pk, perms)
        try:
            task = self.queryset.get(pk=pk, project=project_pk)
        except (ObjectDoesNotExist, ValidationError):
            raise exceptions.NotFound()

        task.pending_action = pending_action
        task.partial = False # Otherwise this will not be processed
        task.last_error = None
        task.save()

        # Process task right away
        worker_tasks.process_task.delay(task.id)

        return Response({'success': True})

    @action(detail=True, methods=['post'])
    def cancel(self, *args, **kwargs):
        return self.set_pending_action(pending_actions.CANCEL, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def restart(self, *args, **kwargs):
        return self.set_pending_action(pending_actions.RESTART, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def remove(self, *args, **kwargs):
        return self.set_pending_action(pending_actions.REMOVE, *args, perms=('delete_project', ), **kwargs)

    @action(detail=True, methods=['get'])
    def output(self, request, pk=None, project_pk=None):
        """
        Retrieve the console output for this task.
        An optional "line" query param can be passed to retrieve
        only the output starting from a certain line number.
        """
        get_and_check_project(request, project_pk)
        try:
            task = self.queryset.get(pk=pk, project=project_pk)
        except (ObjectDoesNotExist, ValidationError):
            raise exceptions.NotFound()

        output = ""
        if task.processing_node:
            # Update task info from processing node
            info = task.processing_node.get_task_info(task.uuid, 0)

            if len(info.output) > 0:
                output = "\n".join(info.output) + '\n'

        elif task.console_output:
            output = task.console_output

        line_num = max(0, int(request.query_params.get('line', 0)))
        data = '\n'.join(output.rstrip().split('\n')[line_num:])

        if request.query_params.get('text', False):
            return HttpResponse(data, content_type='text/plain; charset=UTF-8')
        else:
            return Response(data)

    def list(self, request, project_pk=None):
        get_and_check_project(request, project_pk)
        tasks = self.queryset.filter(project=project_pk)
        tasks = filters.OrderingFilter().filter_queryset(self.request, tasks, self)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None, project_pk=None):
        try:
            task = self.queryset.get(pk=pk, project=project_pk)
        except (ObjectDoesNotExist, ValidationError):
            raise exceptions.NotFound()

        if not task.public:
            get_and_check_project(request, task.project.id)

        serializer = TaskSerializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def commit(self, request, pk=None, project_pk=None):
        """
        Commit a task after all images have been uploaded
        """
        get_and_check_project(request, project_pk, ('change_project', ))
        try:
            task = self.queryset.get(pk=pk, project=project_pk)
        except (ObjectDoesNotExist, ValidationError):
            raise exceptions.NotFound()

        task.partial = False
        task.images_count = models.ImageUpload.objects.filter(task=task).count()

        if task.images_count < 2:
            raise exceptions.ValidationError(detail=_("You need to upload at least 2 images before commit"))

        task.save()
        worker_tasks.process_task.delay(task.id)

        serializer = TaskSerializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def upload(self, request, pk=None, project_pk=None):
        """
        Add images to a task
        """
        get_and_check_project(request, project_pk, ('change_project', ))
        try:
            task = self.queryset.get(pk=pk, project=project_pk)
        except (ObjectDoesNotExist, ValidationError):
            raise exceptions.NotFound()

        files = flatten_files(request.FILES)

        if len(files) == 0:
            raise exceptions.ValidationError(detail=_("No files uploaded"))

        with transaction.atomic():
            for image in files:
                models.ImageUpload.objects.create(task=task, image=image)

        task.images_count = models.ImageUpload.objects.filter(task=task).count()
        # Update other parameters such as processing node, task name, etc.
        serializer = TaskSerializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({'success': True}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def uploaded(self, request, pk=None, project_pk=None):
        """
        Add images to a task that have already been uploaded via tusd (eg: to S3 object storage)
        """
        get_and_check_project(request, project_pk, ('change_project', ))
        try:
            task = self.queryset.get(pk=pk, project=project_pk)
        except (ObjectDoesNotExist, ValidationError):
            raise exceptions.NotFound()

        files = request.data

        if len(files) == 0:
            raise exceptions.ValidationError(detail=_("No files uploaded"))

        with transaction.atomic():
            for image in files:
                #Append the original filename to url
                imageurl = image["uploadURL"] + '#' + image["name"]
                logger.info("uploadURL: " + imageurl)
                models.ImageUpload.objects.create(task=task, image=imageurl)

        task.create_task_directories()

        return Response({'success': True}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def updateassets(self, request, pk=None, project_pk=None):
        """
        Updates the available assets list,
        call if assets have been changed to force an update
        """
        get_and_check_project(request, project_pk, ('change_project', ))
        try:
            task = self.queryset.get(pk=pk, project=project_pk)
        except (ObjectDoesNotExist, ValidationError):
            raise exceptions.NotFound()

        #Update the asset list and save
        task.update_available_assets_field(commit=True)
        return Response({'success': True}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None, project_pk=None):
        """
        Duplicate a task
        """
        get_and_check_project(request, project_pk, ('change_project', ))
        try:
            task = self.queryset.get(pk=pk, project=project_pk)
        except (ObjectDoesNotExist, ValidationError):
            raise exceptions.NotFound()

        new_task = task.duplicate()
        if new_task:
            return Response({'success': True, 'task': TaskSerializer(new_task).data}, status=status.HTTP_200_OK)
        else:
            return Response({'error': _("Cannot duplicate task")}, status=status.HTTP_200_OK)

    def create(self, request, project_pk=None):
        project = get_and_check_project(request, project_pk, ('change_project', ))

        # If this is a partial task, we're going to upload images later
        # for now we just create a placeholder task.
        if request.data.get('partial'):
            task = models.Task.objects.create(project=project,
                                              pending_action=pending_actions.PULL)
            serializer = TaskSerializer(task, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            files = flatten_files(request.FILES)

            if len(files) <= 1:
                raise exceptions.ValidationError(detail=_("Cannot create task, you need at least 2 images"))

            with transaction.atomic():
                task = models.Task.objects.create(project=project,
                                                  pending_action=pending_actions.PULL)

                for image in files:
                    models.ImageUpload.objects.create(task=task, image=image)
                task.images_count = len(files)

                # Update other parameters such as processing node, task name, etc.
                serializer = TaskSerializer(task, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()

                worker_tasks.process_task.delay(task.id)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


    def update(self, request, pk=None, project_pk=None, partial=False):
        get_and_check_project(request, project_pk, ('change_project', ))
        try:
            task = self.queryset.get(pk=pk, project=project_pk)
        except (ObjectDoesNotExist, ValidationError):
            raise exceptions.NotFound()

        # Check that a user has access to reassign a project
        if 'project' in request.data:
            try:
                get_and_check_project(request, request.data['project'], ('change_project', ))
            except exceptions.NotFound:
                raise exceptions.PermissionDenied()

        serializer = TaskSerializer(task, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Process task right away
        worker_tasks.process_task.delay(task.id)

        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)


class TaskNestedView(APIView):
    queryset = models.Task.objects.all().defer('orthophoto_extent', 'dtm_extent', 'dsm_extent', 'console_output', )
    permission_classes = (AllowAny, )

    def get_and_check_task(self, request, pk, annotate={}):
        try:
            task = self.queryset.annotate(**annotate).get(pk=pk)
        except (ObjectDoesNotExist, ValidationError):
            raise exceptions.NotFound()

        # Check for permissions, unless the task is public
        if not task.public:
            get_and_check_project(request, task.project.id)

        return task


def download_file_response(request, filePath, content_disposition, download_filename=None):
    filename = os.path.basename(filePath)
    if download_filename is None: 
        download_filename = filename
    filesize = os.stat(filePath).st_size
    file = open(filePath, "rb")

    # More than 100mb, normal http response, otherwise stream
    # Django docs say to avoid streaming when possible
    stream = filesize > 1e8 or request.GET.get('_force_stream', False)
    if stream:
        response = FileResponse(file)
    else:
        response = HttpResponse(FileWrapper(file),
                                content_type=(mimetypes.guess_type(filename)[0] or "application/zip"))

    response['Content-Type'] = mimetypes.guess_type(filename)[0] or "application/zip"
    response['Content-Disposition'] = "{}; filename={}".format(content_disposition, download_filename)
    response['Content-Length'] = filesize

    # For testing
    if stream:
        response['_stream'] = 'yes'

    return response


def download_file_stream(request, stream, content_disposition, download_filename=None):
    response = HttpResponse(FileWrapper(stream),
                            content_type=(mimetypes.guess_type(download_filename)[0] or "application/zip"))

    response['Content-Type'] = mimetypes.guess_type(download_filename)[0] or "application/zip"
    response['Content-Disposition'] = "{}; filename={}".format(content_disposition, download_filename)

    # For testing
    response['_stream'] = 'yes'
    
    return response


"""
Task downloads are simply aliases to download the task's assets
(but require a shorter path and look nicer the API user)
"""
class TaskDownloads(TaskNestedView):
    def get(self, request, pk=None, project_pk=None, asset=""):
        """
        Downloads a task asset (if available)
        """
        task = self.get_and_check_task(request, pk)

        # Check and download
        try:
            asset_fs, is_zipstream = task.get_asset_file_or_zipstream(asset)
        except FileNotFoundError:
            raise exceptions.NotFound(_("Asset does not exist"))

        if not is_zipstream and not os.path.isfile(asset_fs):
            raise exceptions.NotFound(_("Asset does not exist"))
        
        download_filename = request.GET.get('filename', get_asset_download_filename(task, asset))

        if not is_zipstream:
            return download_file_response(request, asset_fs, 'attachment', download_filename=download_filename)
        else:
            return download_file_stream(request, asset_fs, 'attachment', download_filename=download_filename)

"""
Raw access to the task's asset folder resources
Useful when accessing a textured 3d model, or the Potree point cloud data
"""
class TaskAssets(TaskNestedView):
    def get(self, request, pk=None, project_pk=None, unsafe_asset_path=""):
        """
        Downloads a task asset (if available)
        """
        task = self.get_and_check_task(request, pk)

        # Check for directory traversal attacks
        try:
            asset_path = path_traversal_check(task.assets_path(unsafe_asset_path), task.assets_path(""))
        except SuspiciousFileOperation:
            raise exceptions.NotFound(_("Asset does not exist"))

        if (not os.path.exists(asset_path)) or os.path.isdir(asset_path):
            raise exceptions.NotFound(_("Asset does not exist"))

        if unsafe_asset_path == "metadata.json":
            #Update the current file list in metadata
            try:
                with open(task.assets_path('metadata.json'), 'r') as jfile:
                    metadata = json.load(jfile)
            except:
                metadata = {"custom_assets": {}}

            metadata["files"] = [os.path.relpath(os.path.join(dp, f), task.task_path()) for dp, dn, filenames in os.walk(task.task_path()) for f in filenames]

            #Update metadata json
            with open(task.assets_path('metadata.json'), 'w') as outfile:
                json.dump(metadata, outfile)

        return download_file_response(request, asset_path, 'inline')

    def post(self, request, pk=None, project_pk=None, unsafe_asset_path=""):
        """
        Add an asset to a task
        """
        task = self.get_and_check_task(request, pk)

        files = flatten_files(request.FILES)

        if len(files) == 0:
            raise exceptions.ValidationError(detail=_("No files uploaded"))

        #Get metadata json
        try:
            with open(task.assets_path('metadata.json'), 'r') as jfile:
                metadata = json.load(jfile)
        except:
            metadata = {"custom_assets": {}}

        #Just drops the files in the assets folder, can also pass subdir
        destpath = task.assets_path(unsafe_asset_path)
        os.makedirs(destpath, exist_ok=True)
        for f in files:
            destination_file = os.path.join(destpath, str(f))

            with open(destination_file, 'wb+') as fd:
                if isinstance(files[0], InMemoryUploadedFile):
                    for chunk in files[0].chunks():
                        fd.write(chunk)
                else:
                    with open(files[0].temporary_file_path(), 'rb') as file:
                        copyfileobj(file, fd)

            #Add the relative path to custom assets
            fkey = os.path.join(unsafe_asset_path, str(f))
            try:
                current = metadata["custom_assets"][fkey]
            except KeyError:
                current = {}
            current["modified"] = datetime.datetime.now().isoformat()
            metadata["custom_assets"][fkey] = current

        #Update metadata json
        with open(task.assets_path('metadata.json'), 'w') as outfile:
            json.dump(metadata, outfile)

        #Update the asset list and save
        task.update_available_assets_field(commit=True)
        return Response({'success': True}, status=status.HTTP_200_OK)

    def delete(self, request, pk=None, project_pk=None, unsafe_asset_path=""):
        """
        Deletes a task asset (if available)
        """
        task = self.get_and_check_task(request, pk)

        # Check for directory traversal attacks
        try:
            asset_path = path_traversal_check(task.assets_path(unsafe_asset_path), task.assets_path(""))
        except SuspiciousFileOperation:
            raise exceptions.NotFound(_("Asset does not exist"))

        if (not os.path.exists(asset_path)) or os.path.isdir(asset_path):
            raise exceptions.NotFound(_("Asset does not exist"))

        #return download_file_response(request, asset_path, 'inline')
        filepath = task.assets_path(unsafe_asset_path)
        if not os.path.exists(filepath):
            raise exceptions.NotFound()

        #Get metadata json
        try:
            with open(task.assets_path('metadata.json'), 'r') as jfile:
                metadata = json.load(jfile)
                del metadata["custom_assets"][filename]
            #Update metadata json
            with open(task.assets_path('metadata.json'), 'w') as outfile:
                json.dump(metadata, outfile)
        except:
            pass

        #Delete the file
        os.remove(filepath)

        #Update the asset list and save
        task.update_available_assets_field(commit=True)
        return Response({'success': True}, status=status.HTTP_200_OK)

"""
Task assets import
"""
class TaskAssetsImport(APIView):
    permission_classes = (permissions.AllowAny,)
    parser_classes = (parsers.MultiPartParser, parsers.JSONParser, parsers.FormParser,)

    def post(self, request, project_pk=None):
        project = get_and_check_project(request, project_pk, ('change_project',))

        files = flatten_files(request.FILES)
        import_url = request.data.get('url', None)
        task_name = request.data.get('name', _('Imported Task'))

        if not import_url and len(files) != 1:
            raise exceptions.ValidationError(detail=_("Cannot create task, you need to upload 1 file"))

        if import_url and len(files) > 0:
            raise exceptions.ValidationError(detail=_("Cannot create task, either specify a URL or upload 1 file."))

        with transaction.atomic():
            task = models.Task.objects.create(project=project,
                                              auto_processing_node=False,
                                              name=task_name,
                                              import_url=import_url if import_url else "file://all.zip",
                                              status=status_codes.RUNNING,
                                              pending_action=pending_actions.IMPORT)
            task.create_task_directories()

            if len(files) > 0:
                destination_file = task.assets_path("all.zip")

                with open(destination_file, 'wb+') as fd:
                    if isinstance(files[0], InMemoryUploadedFile):
                        for chunk in files[0].chunks():
                            fd.write(chunk)
                    else:
                        with open(files[0].temporary_file_path(), 'rb') as file:
                            copyfileobj(file, fd)

            worker_tasks.process_task.delay(task.id)

        serializer = TaskSerializer(task)
        return Response(serializer.data, status=status.HTTP_201_CREATED)