#!/usr/bin/env bash
# Serve the claudism_spans remote evaluator and expose it to Arize AX.
#
# Starts the evaluator on 127.0.0.1:$PORT and a Cloudflare quick tunnel in
# front of it, then prints the endpoint URL. The bearer token AX must send is
# in .eval-token; it is not printed, so it stays out of logs. Ctrl+C stops both.
#
# The token is generated once into .eval-token (gitignored) and reused, so the
# evaluator configured in AX keeps working across restarts. The tunnel URL
# does not: a quick tunnel gets a new hostname every time, so after a restart
# update the endpoint on the evaluator in AX.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8080}"

if [[ ! -s .eval-token ]]; then
  umask 077
  python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > .eval-token
fi
export CLAUDISM_EVAL_TOKEN="$(cat .eval-token)"
export PORT

uv run --group server blogwriter-eval-server &
server=$!
log="$(mktemp)"
cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" >"$log" 2>&1 &
tunnel=$!
trap 'kill $server $tunnel 2>/dev/null; rm -f "$log"' EXIT INT TERM

url=""
for _ in $(seq 60); do
  url="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$log" | head -1 || true)"
  [[ -n "$url" ]] && break
  sleep 1
done
[[ -n "$url" ]] || { echo "tunnel did not start:"; cat "$log"; exit 1; }

cat <<MSG

  Remote evaluator is up.

    Endpoint : $url/v1/evaluate
    Header   : Authorization: Bearer <contents of .eval-token>

  Health: curl $url/

MSG
wait $server
