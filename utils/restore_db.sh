#!/bin/bash
echo "Restoring database from backup $1..."
#This example restores a single table - using --clean drops old tables!
#pg_restore --clean -h db -U postgres -t nodeodm_processingnode -d webodm_dev $1
pg_restore --schema-only -h db -U postgres -t nodeodm_processingnode -d webodm_dev $1
pg_restore --data-only -h db -U postgres -t nodeodm_processingnode -d webodm_dev $1

