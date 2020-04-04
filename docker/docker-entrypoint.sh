#!/bin/bash
set -e

if [ "$1" = 'pynodered' ]; then
    ln -sf /node-red /home/pynodered/.node-red
    cd /pynodered
    su pynodered -c "pip3 install ."
    su pynodered -c "/usr/local/bin/pynodered nodered.py"
fi

exec "$@"
