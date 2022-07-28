#!/bin/bash
# Run this only on the server pod
# Applies the patch files on webapp / worker container

echo Running patch on $HOSTNAME
if [ "$WO_HOST" = "dev.asdc.cloud.edu.au" ]; then
  cp -R /webodm/app/media/patch/development/* /webodm/
fi
if [ "$WO_HOST" = "asdc.cloud.edu.au" ]; then
  #INSTALL PATCHED FILES IN POD
  cp -R /webodm/app/media/patch/production/* /webodm/
fi

#Update everything
pip install -r requirements.txt
webpack 
python manage.py collectstatic --noinput
python manage.py rebuildplugins

