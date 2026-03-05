#!/bin/bash
# Stop the NOVA-7 app
PIDS=$(ps aux | grep "uvicorn app.main:app" | grep -v grep | awk '{print $2}')
if [ -n "$PIDS" ]; then
    echo "$PIDS" | xargs sudo kill -9
    sleep 1
    echo "Stopped uvicorn"
else
    echo "Not running"
fi
