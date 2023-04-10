#!/usr/bin/env bash

# --max-tasks-per-child: create a new process for every new task. helps in memory leaks
# -Ofair: distributes tasks fairly to every process

celery -A ibm.discovery worker -Q ibm_discovery_worker_queue -c 5 --loglevel=info --without-gossip --without-mingle --without-heartbeat --max-tasks-per-child=1 -Ofair
