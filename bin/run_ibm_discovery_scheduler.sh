#!/usr/bin/env bash

rm ibm_discovery_celerybeat.pid

celery -A ibm.discovery beat --loglevel=info --pidfile="ibm_discovery_celerybeat.pid"
