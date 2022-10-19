#!/bin/bash
set -e

if [ "$1" = 'pynodered' ]; then
    ln -sf /node-red $HOME/.node-red
    cd /pynodered
    pip3 install .
    exec /usr/local/bin/pynodered nodered.py
fi

exec "$@"
