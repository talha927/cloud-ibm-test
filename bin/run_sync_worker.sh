#!/usr/bin/env bash

celery -A ibm.tasks.celery_app.celery_app worker -Q sync_queue -c 5 --loglevel=info --without-gossip --without-mingle --without-heartbeat --max-tasks-per-child=1 -Ofair
