#!/bin/bash
# Deploy to a sprites.dev VM. Usage: SPRITE=<name> deploy/sprite.sh [--restart]
#
# One-time setup on the sprite:
#   1. /app/run.sh:
#        #!/bin/bash
#        export TYPESAFE_API_KEY="$(cat /app/.typesafe_key)" DRONECAM_HOST=0.0.0.0 DRONECAM_PORT=8080
#        exec /usr/bin/python3 /app/server.py
#   2. /app/.typesafe_key holding your key (chmod 600). Use a spend-limited key for a public page.
#   3. sprite exec -s $SPRITE -- sprite-env services create web --cmd /bin/bash --args /app/run.sh --dir /app --http-port 8080
#   4. sprite config update --url-auth public -s $SPRITE
#
# Each run pushes server.py and public/. Static files update at once; pass --restart after a server.py change.
set -euo pipefail
N="${SPRITE:-jev-dronecam}"
cd "$(dirname "$0")/.."
COPYFILE_DISABLE=1 tar --no-mac-metadata --no-xattrs -czf - server.py public | sprite exec -s "$N" -- tar -xzf - -C /app
if [[ "${1:-}" == "--restart" ]]; then sprite exec -s "$N" -- sprite-env services signal web TERM; sleep 3; fi
URL=$(sprite info -s "$N" | awk '/^URL:/{print $2}')
curl -s -o /dev/null -w "$URL -> %{http_code}\n" "$URL/"
