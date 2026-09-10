#!/bin/sh
set -eu

MIHOMO_DIR=/app/mihomo
DATA_DIR=/app/data
MIHOMO_LOOP=""
BOT_PID=""

if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_DIR" "$MIHOMO_DIR/providers"
  if [ ! -s "$DATA_DIR/catalog.sqlite3" ] && [ -f /app/catalog.seed.sqlite3 ]; then
    cp /app/catalog.seed.sqlite3 "$DATA_DIR/catalog.sqlite3"
  fi
  chown -R botuser:botuser "$DATA_DIR" "$MIHOMO_DIR"
  exec gosu botuser "$0" "$@"
fi

if [ ! -s "$DATA_DIR/catalog.sqlite3" ] && [ -f /app/catalog.seed.sqlite3 ]; then
  cp /app/catalog.seed.sqlite3 "$DATA_DIR/catalog.sqlite3"
fi

term() {
  if [ -n "${BOT_PID:-}" ]; then
    kill -TERM "$BOT_PID" 2>/dev/null || true
    wait "$BOT_PID" 2>/dev/null || true
  fi
  if [ -n "${MIHOMO_LOOP:-}" ]; then
    kill -TERM "$MIHOMO_LOOP" 2>/dev/null || true
    wait "$MIHOMO_LOOP" 2>/dev/null || true
  fi
}

trap term TERM INT

if [ "${SKIP_MIHOMO:-0}" != "1" ]; then
  (
    while true; do
      echo "starting mihomo"
      mihomo -d "$MIHOMO_DIR" || true
      echo "mihomo exited, restart in 5s"
      sleep 5
    done
  ) &
  MIHOMO_LOOP=$!
  python - <<'PY'
import socket
import sys
import time

for _ in range(90):
    sock = socket.socket()
    sock.settimeout(1)
    try:
        sock.connect(("127.0.0.1", 11808))
        print("mihomo mixed-port ready")
        sys.exit(0)
    except OSError:
        time.sleep(1)
    finally:
        sock.close()
print("mihomo port not ready yet; bot will retry Telegram")
PY
  python - <<'PY'
import json
import re
import time
import urllib.request

secret = ""
try:
    text = open("/app/mihomo/config.yaml", encoding="utf-8").read()
    match = re.search(r'(?m)^secret:\s*"([^"]+)"', text)
    if match:
        secret = match.group(1)
except OSError:
    secret = ""

if not secret:
    print("mihomo API secret missing; bot will retry Telegram")
else:
    for _ in range(45):
        req = urllib.request.Request(
            "http://127.0.0.1:19090/proxies/AUTO",
            headers={"Authorization": f"Bearer {secret}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.load(resp)
            now = data.get("now") if isinstance(data, dict) else None
            nodes = data.get("all") if isinstance(data, dict) else None
            if isinstance(now, str) and now and isinstance(nodes, list) and nodes:
                print(f"mihomo AUTO ready node={now} proxies={len(nodes)}")
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        print("mihomo AUTO not ready yet; bot will retry Telegram")
PY
fi

python bot.py &
BOT_PID=$!
set +e
wait "$BOT_PID"
STATUS=$?
set -e
trap - TERM INT
term
exit "$STATUS"
