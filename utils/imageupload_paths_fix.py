"""
Issue:
    app_imageupload.path is ending up with absolute paths

Remove the prefix to fix existing entries
/webodm/app/media/


"""

#When TESTMODE set, will just run the query and return for timing
TESTMODE = True
#TESTMODE = False

import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webodm.settings")
application = get_wsgi_application()

from app.models import Project, Task, ImageUpload
from django.db import models
from django.contrib.auth.models import User

#print([f.name for f in Task._meta.get_fields()])

images = ImageUpload.objects.all()

#print(projects)
prefix = '/webodm/app/media/'
for i in images:
    #print("IMG:", i.image.name)
    if i.image.name[0:len(prefix)] == prefix:
        i.image.name = i.image.name[len(prefix):]
        print("Updated:",i.image.name)
        if not TESTMODE:
            i.save()


