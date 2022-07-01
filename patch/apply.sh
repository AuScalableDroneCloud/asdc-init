#!/bin/bash
# This runs in pod to apply patches to WebODM based on the
# asdc-init git repository
# list of files obtained from /webapp/media/patch/files
# - Files are cloned/pulled to the persistent volume on running app in asdc_init.sh
# - When app server processes are stopped, loop in pod runs the patch on startup
# - Files are copied into pod live version before restarting services
echo Running patch on $HOSTNAME

function exec_k8s()
{
  #Runs kubectl exec in a loop until it succeeds or 10 attempts
  #ARGS: pod container command
  for i in {1..10}
  do
    if kubectl exec --stdin --tty webapp-worker-0 -c webapp -- bash -c "$1"
    then
      echo "OK"
      break
    fi
    echo "Failed: Attempting again ($i)"
  done
}

#INSTALL PATCHED FILES IN POD
echo "ON WEBAPP"
cd /webodm/app/media/patch/
for f in /webodm/app/media/patch/*
do
  echo "Installing patch file: $f..."
  cp "$f" "/webodm/$f"
done
cd /webodm
pip install -r requirements.txt

