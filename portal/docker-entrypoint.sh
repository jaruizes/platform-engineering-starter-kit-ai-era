#!/bin/sh
# Starts the portal. Its configuration and catalog use the local addresses
# (http://localhost:<port>); when PUBLIC_URL is another address, as on AWS,
# they are rewritten to it, keeping each port.
set -e
origin="${PUBLIC_URL%:*}"
if [ -n "$PUBLIC_URL" ] && [ "$origin" != "http://localhost" ]; then
  host="${origin#*://}"
  # The configuration, the catalog and the files the templates generate.
  find app-config.yaml catalog standards/catalog-info.yaml -type f \( -name '*.yaml' -o -name '*.md' \) \
    -exec sed -i -e "s|http://localhost:|$origin:|g" -e "s|localhost:3000|$host:3000|g" {} +
fi
if [ -f /etc/platform-ca/ca.crt ]; then
  export NODE_EXTRA_CA_CERTS=/etc/platform-ca/ca.crt
fi
exec node packages/backend --config app-config.yaml --config branding/branding.yaml "$@"
