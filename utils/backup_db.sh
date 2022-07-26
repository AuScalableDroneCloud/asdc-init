#!/bin/bash
/webodm/wait-for-postgres.sh db
TS=$(date "+%Y%m%d-%H%M")
echo "Begin backup loop";
while :;
do 
  echo "Backing up database..."
  fn=webodm_db_$TS.dump
  pg_dump -h db -U postgres -F c webodm_dev > webodm_db_latest.dump
  mkdir -p app/store/backups
  cp --no-preserve=ownership,timestamps webodm_db_latest.dump /webodm/app/store/backups/$fn
  #ln -s /webodm/app/store/backups/$fn /webodm/app/media/webodm_db_latest.dump

  #echo "Sleeping 24 hours..."
  #sleep 86400;

  #Do a filesystem access check - to compare output with livenessprobe that is failing
  #(loops for 1440 minutes = 24 hours)
  for i in {1..1440}
  do 
    echo "[$i] Checking filesystem access... /webodm/app/media"
    ls /webodm/app/media
    echo "[$i] Checking filesystem access... /webodm/app/store"
    ls /webodm/app/store
    echo "[$i] Sleeping 1 minute"
    sleep 60;
  done

done
