#!/usr/bin/env bash

celery -A ibm.tasks.celery_app.celery_app worker -Q workspace_initiator_queue --pool=gevent --concurrency=10 --loglevel=info --without-gossip --without-mingle --without-heartbeat
