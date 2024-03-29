#!/bin/bash
/webodm/wait-for-postgres.sh db

echo "Begin backup loop";
while :;
do 
  echo "Removing backups older than 30 days..."
  find /webodm/app/store/backups -type f -mtime +30 -delete

  TS=$(date "+%Y%m%d-%H")
  fn=webodm_db_$TS.dump
  if [ ! -f /webodm/app/store/backups/$fn ] && [ ! -f webodm_db_latest.dump ];
  then
    echo "Backing up database..."
    pg_dump -h db -U postgres -F c webodm_dev > webodm_db_latest.dump
    #Restore command
    #pg_restore -d webodm_dev /webodm/app/store/backups/$fn -c -U postgres
    mkdir -p app/store/backups
    cp --no-preserve=ownership,timestamps webodm_db_latest.dump /webodm/app/store/backups/$fn
    rm webodm_db_latest.dump
    #ln -s /webodm/app/store/backups/$fn /webodm/app/media/webodm_db_latest.dump
  else
    echo "Skip backup, already in progress"
  fi

  echo "Sleeping 8 hours..."
  sleep 28800;

  #Do a filesystem access check - to compare output with livenessprobe that is failing
  #(loops for 1440 minutes = 24 hours)
  #for i in {1..1440}
  #do 
  #  echo "[$i] Checking filesystem access... /webodm/app/media"
  #  ls /webodm/app/media
  #  echo "[$i] Checking filesystem access... /webodm/app/store"
  #  ls /webodm/app/store
  #  echo "[$i] Sleeping 1 minute"
  #  sleep 60;
  #done

done
