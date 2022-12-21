#!/bin/bash
# This simply stops the web server process to trigger installation of patch
# files from this repository ./patch/files

#Default asdc-init and DronesVL dir both in parent dir

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

cd $HOME/Sync/ASDC/DronesVL
source settings.env
cd -

#To install patch, kill and restart main processes in pod...
#echo "Kill celery"
#kubectl exec --stdin --tty webapp-worker-0 -c worker -- celery -A worker control shutdown

#kubectl exec --stdin --tty webapp-worker-0 -c webapp -- killall webpack
#kubectl exec --stdin --tty webapp-worker-0 -c webapp -- killall celery
echo "Kill nginx"
#kubectl exec --stdin --tty webapp-worker-0 -c webapp -- killall nginx
exec_k8s "killall nginx"
echo "Kill gunicorn"
#kubectl exec --stdin --tty webapp-worker-0 -c webapp -- killall gunicorn
exec_k8s "killall gunicorn"

