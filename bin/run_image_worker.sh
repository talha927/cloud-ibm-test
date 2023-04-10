#!/usr/bin/env bash

celery -A ibm.tasks.celery_app.celery_app worker -Q image_conversion_queue --pool=gevent --concurrency=10 --loglevel=debug --without-gossip --without-mingle --without-heartbeat
