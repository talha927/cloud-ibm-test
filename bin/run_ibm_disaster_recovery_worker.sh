#!/usr/bin/env bash

celery -A ibm.tasks.celery_app worker -Q disaster_recovery_queue --loglevel=info -c 5 --without-gossip --without-mingle --without-heartbeat --max-tasks-per-child=1 -Ofair
