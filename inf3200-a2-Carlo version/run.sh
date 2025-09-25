#!/usr/bin/env bash
set -euo pipefail   # error, unset variable catch, or pipe check

# input check (need 1)
if [[ $# -ne 1 || ! "$1" =~ ^[0-9]+$ || "$1" -lt 1 ]]; then
  echo "usage: $0 <number_of_servers>" >&2
  exit 1
fi
N="$1"

# abs path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_PY="$SCRIPT_DIR/server.py"
if [[ ! -f "$SERVER_PY" ]]; then
  echo "error: server.py not found at $SERVER_PY" >&2
  exit 1
fi

# nodes list and if 0 then error
mapfile -t NODES < <(/share/ifi/available-nodes.sh)
if [[ ${#NODES[@]} -eq 0 ]]; then
  echo "error: no compute nodes available" >&2
  exit 1
fi

# check if a port is listening on a node ss or netstat 
is_listening() {
  local node="$1" port="$2"
  ssh -o ConnectTimeout=1 -q "$node" \
    'if command -v ss >/dev/null 2>&1; then
       ss -H -tln | awk "{print \$4}" | grep -Eq "(:|\\.)'"$port"'$"
     else
       netstat -tln 2>/dev/null | awk "{print \$4}" | grep -Eq "(:|\\.)'"$port"'$"
     fi'
}

# test if port is free (not of is_listening)
is_free() {
  ! is_listening "$1" "$2"
}

addresses=()

# launch
for ((i=0; i<N; i++)); do
  node="${NODES[$(( i % ${#NODES[@]} ))]}"

  # pick random free port, retry if not free
  while :; do
    port=$(shuf -i 49152-65535 -n1)
    if is_free "$node" "$port"; then
      break
    fi
  done

  # start remotely and truly detach so it survives the ssh session
  # //use absolute path for server.py 
  ssh -f "$node" "nohup python3 -u '$SERVER_PY' '$port' >/dev/null 2>&1 < /dev/null &"

  # readiness wait, poll up to 2s for the port to start listening
  ready=0
  for _ in {1..20}; do
    if is_listening "$node" "$port"; then
      ready=1
      break
    fi
    sleep 0.1
  done
  

  addresses+=("${node}:${port}")

  # space to avoid clash when multiple servers starts at once
  sleep 0.05
done

# print only json
python3 - <<PY "${addresses[@]}"
import json, sys
print(json.dumps(sys.argv[1:]))
PY
