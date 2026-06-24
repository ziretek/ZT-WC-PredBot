#!/bin/bash
mkdir -p /data
export DATA_DIR=${DATA_DIR:-/data}
echo "Starting wcbot with DATA_DIR=$DATA_DIR"
exec python -m wcbot
