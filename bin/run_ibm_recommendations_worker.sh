#!/usr/bin/env bash

celery -A ibm.tasks.celery_app worker -Q recommendations_queue -c 5 --loglevel=info --without-gossip --without-mingle --without-heartbeat --max-tasks-per-child=1 -Ofair
