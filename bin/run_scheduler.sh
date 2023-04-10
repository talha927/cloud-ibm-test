#!/usr/bin/env bash

rm celerybeat.pid

# Run celery worker for background tasks
sleep 1.5m # compensate delay of mysql + web container setup

celery -A ibm.tasks.celery_app.celery_app beat --loglevel=info
