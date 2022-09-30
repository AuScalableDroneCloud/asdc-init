#!/bin/bash
# Run this only on the server pod
# Applies the patch files on webapp / worker container

echo Running patch on $HOSTNAME
cp -R /webodm/app/media/patch/files/* /webodm/

#Update everything
pip install -r requirements.txt
webpack 
python manage.py collectstatic --noinput
python manage.py rebuildplugins

