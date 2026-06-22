#!/usr/bin/env bash
# Regenerate the encrypted EVOLEM dashboard from the live Attio Dealflow list.
#   ATTIO_API_KEY=<key> DASH_PASSWORD=EvolemLogin ./generator/build.sh
set -euo pipefail
cd "$(dirname "$0")"
: "${ATTIO_API_KEY:?set ATTIO_API_KEY}"
: "${DASH_PASSWORD:?set DASH_PASSWORD}"
python3 build_payload.py        # live Dealflow -> payload.json
python3 inject.py               # template.html + payload.json -> plain.html
node encrypt.mjs                # plain.html -> ../index.html (StatiCrypt v3)
rm -f plain.html                # never commit the decrypted report
echo "Dashboard regenerated: ../index.html"
