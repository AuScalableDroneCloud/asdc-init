#!/bin/bash
# This gets files from a test copy of WebODM ready to install as patch
# list of files obtained from FILELIST var below
# - Files are copied into ./files
# When finished, commit/push to repo and run ./install.sh to restart server

#Files to copy from local WebODM
FILELIST="
nginx/nginx-ssl.conf.template
package.json
requirements.txt
app/models/task.py
app/static/app/js/components/TaskListItem.jsx
"

#Default is to assume reference WebODM install and asdc-init dir both same dir
#and script is run from patch subdir
cd ../..
BASEPATH=$(pwd)
WEBODMPATH=$(pwd)/WebODM
cd -

echo "ON DEV PC"
cd $BASEPATH/asdc-init/patch/
for f in ./$FILELIST
do
  DIR="$(dirname "${f}")"
  echo "Creating dir $DIR..."
  mkdir -p ./files/$DIR
  echo "Copying file $f..."
  cp "$WEBODMPATH/$f" "files/$f"
done


