#!/bin/sh
set -e

exec gunicorn \
  -k uvicorn.workers.UvicornWorker \
  -w 2 \
  --threads 2 \
  --bind 0.0.0.0:5001 \
  --timeout 500 \
  --log-level DEBUG \
  --reload \
  -c /dev/null \
  main:app
