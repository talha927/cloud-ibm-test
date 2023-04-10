#!/usr/bin/env bash

celery -A ibm.tasks.celery_app.celery_app worker -Q workflow_queue --pool=solo --loglevel=info --without-gossip --without-mingle --without-heartbeat
