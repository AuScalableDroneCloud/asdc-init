#!/bin/bash
# This gets files from a test copy of WebODM ready to install as patch
# list of files obtained from FILELIST var below
# - Files are copied into ./development or ./production 
# When finished, commit/push to repo and run ./install.sh to restart server

#Files to copy from local WebODM
FILELIST="" #app/models/task.py"

#Default is to assume reference WebODM install and asdc-init dir both same dir
#and script is run from patch subdir
cd ../..
BASEPATH=$(pwd)
WEBODMPATH=$(pwd)/WebODM
cd -

cd $BASEPATH/asdc-init/patch/
PATCHDIR=./files
#Remove current patch files
rm -rf $PATCHDIR
mkdir $PATCHDIR
for f in ./$FILELIST
do
  DIR="$(dirname "${f}")"
  echo "Creating dir $DIR..."
  mkdir -p $PATCHDIR/$DIR
  echo "Copying file $f..."
  cp "$WEBODMPATH/$f" "$PATCHDIR/$f"
done


