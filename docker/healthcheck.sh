#!/bin/bash
# docker/healthcheck.sh

# Simple process check to see if our Python script is running
if pgrep -f "python.*bigquery_vote_processor" > /dev/null; then
  echo "Processor is running"
  exit 0
else
  echo "Processor is not running"
  exit 1
fi