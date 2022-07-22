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
  echo "Sleeping 24 hours..."
  sleep 86400;
done
