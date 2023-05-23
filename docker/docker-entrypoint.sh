#!/bin/bash
set -e

if [ "$1" = 'htd-lync' ]; then
    cd /data
    python htd-amqtt-client.py
fi

exec "$@"
