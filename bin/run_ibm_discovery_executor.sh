#!/usr/bin/env bash

celery -A ibm.discovery worker -Q ibm_discovery_executor_queue --pool=solo --loglevel=info --without-gossip --without-mingle --without-heartbeat
