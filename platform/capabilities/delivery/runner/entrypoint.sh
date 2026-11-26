#!/bin/sh
# Registers the runner with the Git server the first time (the registration
# is kept in /data) and waits for jobs.
set -e
mkdir -p /data/home /data/work
cd /data
if [ ! -f .runner ]; then
  act_runner register --no-interactive --config /etc/act_runner/config.yaml \
    --instance "$GITEA_URL" --token "$RUNNER_TOKEN" --name "${RUNNER_NAME:-platform}" --labels "platform:host"
fi
exec act_runner daemon --config /etc/act_runner/config.yaml
