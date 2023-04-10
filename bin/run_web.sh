#!/usr/bin/env bash

LOGGING_LEVEL="${LOGGING_LEVEL:DEBUG}"

#run and deploy latest migrations
flask deploy

gunicorn --reload --access-logfile "-" --error-logfile "-" --log-level LOGGING_LEVEL --worker-class gevent --workers=3 --timeout 60 --bind 0.0.0.0:8081 app:app
