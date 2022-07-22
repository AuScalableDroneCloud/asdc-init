#!/bin/bash
TS=$(date "+%Y%m%d-%H%M")

#Sync from cinder volume to s3 volume - initial step (cinder primary, s3 backup)
#SOURCE=/webodm/app/media/project/
#TARGET=/webodm/app/store/project/

#Sync from s3 volume to cinder - trial: s3 primary, cinder backup
SOURCE=/webodm/app/media/project/
TARGET=/webodm/app/media/project_backup/
#Swap SOURCE/TARGET above

#Run the sync
#-r recursive
#-a (-rlptgoD recursive+symlinks+perms+mod times + group + owner + devices) most of these are not relevant
#-c use checksum not just date/size - slower, disable for now!
#--size-only use only size to compare (needed if not using -c, as date/time not accurate on s3)
#-v list changes
#--delete delete at target if not in source
#-W whole file - no delta transfers
#--inplace update files inplace
echo "Begin sync loop";
while :;
do 
  echo "Re-synching storage/backup..."
  #rsync -rvW --size-only --inplace --delete ${SOURCE} ${TARGET} 2>&1 | tee "/webodm/app/media/tmp/sync-${TS}.log"
  #Remove --delete for the backup mode
  rsync -rvW --size-only --inplace ${SOURCE} ${TARGET} 2>&1 | tee "/webodm/app/media/tmp/sync-${TS}.log"
  echo "Sleeping 24 hours..."
  sleep 86400;
done
