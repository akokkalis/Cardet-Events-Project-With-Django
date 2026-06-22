#!/bin/sh
# Runs on every container start (not just image build) since docker-compose
# bind-mounts the project source over /app, so anything baked into the image
# at build time would be hidden anyway. Recreates the gitignored static
# assets (core/static/vendor/, staticfiles/) if they're missing, then runs
# whatever CMD/command docker-compose passes in.
set -e

sh /app/scripts/fetch_vendor_assets.sh
python manage.py collectstatic --noinput

exec "$@"
