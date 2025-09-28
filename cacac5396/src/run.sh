#!/usr/bin/env bash
# run.sh adapted (from A1 with extra functions)
# start N servers on cluster, run testers/bench, optional kill

set -euo pipefail   # stop on error, unset vars, pipe fail

# ---- killall mode (stop all old servers and wait until they are gone) //fast cleanup cluster
if [[ "${1-}" == "--killall" ]]; then
  echo "[info] killing ALL old server.py ..."

  # loop over all compute nodes in the cluster (list comes from file)
  for N in $(cat /share/compute-nodes.txt); do
    # ssh into each node, run cleanup, silence errors if not reachable
    ssh -o ConnectTimeout=2 -o ConnectionAttempts=1 -x "$N" "
      
      for i in 1 2 3 4 5; do
        pgrep -u $USER -fa server.py >/dev/null || break   # stop if no server left
        pkill -u $USER -f server.py || true                # send TERM (easy stop))
        sleep 0.2
      done

      # if still running after tries, do a hard kill
      if pgrep -u $USER -fa server.py >/dev/null; then
        pkill -9 -u $USER -f server.py || true             # send KILL (hard stop)
        # wait up to 10*0.2s until really gone
        for i in \$(seq 1 10); do
          pgrep -u $USER -fa server.py >/dev/null || break
          sleep 0.2
        done
      fi
    " >/dev/null 2>&1 || true &   # run ssh in background, ignore errors
  done

  wait   # wait until all background ssh cleanup servers finishes
  echo "[KILL INFO] all server.py killed"
  exit 0
fi

# ---- usage check
if [[ $# < 1 || ! "${1:-}" =~ ^[0-9]+$ || "$1" -lt 1 ]]; then
  echo "usage: $0 <num_servers> [--test|--bench|--all] [--kill] [bench args]" >&2
  exit 1
fi

N="$1"        # number of servers
MODE="none"   # mode after start
KILL_AFTER=0  # auto kill at end

# ---- parse flags
if [[ "${2-}" == "--test" ]]; then MODE="test"; fi
if [[ "${2-}" == "--bench" ]]; then MODE="bench"; fi
if [[ "${2-}" == "--all" ]]; then MODE="all"; fi
if [[ "${2-}" == "--kill" || "${3-}" == "--kill" ]]; then KILL_AFTER=1; fi

# ---- paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_PY="$SCRIPT_DIR/server.py"
BENCH_PY="$SCRIPT_DIR/bench.py"
CHORD_TESTER="$SCRIPT_DIR/chord-tester.py"
RUN_TESTER="$SCRIPT_DIR/run-tester.py"

if [[ ! -f "$SERVER_PY" ]]; then
  echo "error: server.py not found at $SERVER_PY" >&2
  exit 1
fi

# ---- get compute nodes (not frontend c0-0)
mapfile -t NODES < <(/share/ifi/available-nodes.sh)
FILTERED=()
for n in "${NODES[@]}"; do
  if [[ "$n" != "c0-0" ]]; then FILTERED+=("$n"); fi
done
NODES=("${FILTERED[@]}")
if [[ ${#NODES[@]} -eq 0 ]]; then
  echo "error: no compute nodes available" >&2
  exit 1
fi

# ---- helpers

can_ssh() { ssh -o ConnectTimeout=1 -o ConnectionAttempts=1 -q "$1" "true" 2>/dev/null; }
# true if port is listening on node
is_listening() {
  local node="$1" port="$2"
  ssh -o ConnectTimeout=1 -q "$node" \
    'if command -v ss >/dev/null 2>&1; then
       ss -H -tln | awk "{print \$4}" | grep -Eq "(:|\\.)'"$port"'$"
     else
       netstat -tln 2>/dev/null | awk "{print \$4}" | grep -Eq "(:|\\.)'"$port"'$"
     fi' \
  >/dev/null
}
is_free() { ! is_listening "$1" "$2"; }

# check if node can run python3 and see server.py
check_node_ready() {
  local node="$1" server_path="$2"
  ssh -o ConnectTimeout=2 -o ConnectionAttempts=1 -q "$node" \
    "command -v python3 >/dev/null 2>&1 && test -r '$server_path'"
}

# ---- pick nodes and ports (skip non reach nodes)
addresses=()
for ((i=0; i<N; i++)); do
  idx=$(( i % ${#NODES[@]} ))
  node="${NODES[$idx]}"
  tries=0
  while ! can_ssh "$node"; do                # find a node
    idx=$(( (idx + 1) % ${#NODES[@]} ))
    node="${NODES[$idx]}"
    tries=$((tries + 1))
    if [[ $tries -ge ${#NODES[@]} ]]; then
      echo "[ERROR] no reachable compute nodes" >&2
      exit 1
    fi
  done
  while :; do                                 # pick free port
    port=$(shuf -i 49152-65535 -n1)
    if is_free "$node" "$port"; then break; fi
  done
  addresses+=("$node:$port")
done

# ---- build peers json (bash array = JSON string)
peers_json="$(
python3 - <<PY "${addresses[@]}"
import json, sys
print(json.dumps(sys.argv[1:]))
PY
)"
echo "$peers_json" > "$SCRIPT_DIR/peers.json"

# ---- start servers with same neighbor list
for addr in "${addresses[@]}"; do
  node="${addr%%:*}"
  port="${addr##*:}"

  # sanity check on node (python3 + server.py must be usable)
  if ! check_node_ready "$node" "$SERVER_PY"; then
    echo "[ERROR] node $node is missing python3 or server.py" >&2
    exit 1
  fi

  # start remotely and detach; log to /tmp in case of errors
  rlog="/tmp/inf3200_a2_${USER}_${node}_${port}.log"
  ssh -f "$node" "nohup python3 -u '$SERVER_PY' '$port' '$peers_json' >'$rlog' 2>&1 < /dev/null &"

  # wait to 5s for the port
  ready=0
  for _ in {1..50}; do
    if is_listening "$node" "$port"; then
      ready=1
      break
    fi
    sleep 0.1
  done
  if [[ $ready -eq 0 ]]; then
    echo "[ERROR] node $node:$port failed to start" >&2
    echo "[hint] last log lines from $node:$port"
    ssh -o ConnectTimeout=2 -q "$node" "tail -n 80 '$rlog' 2>/dev/null || true"
    exit 1
  fi
done

# ---- print peers json (for chain)
echo "$peers_json"

# ---- run testers
if [[ "$MODE" == "test" || "$MODE" == "all" ]]; then
  if [[ -f "$CHORD_TESTER" ]]; then
    entry="${addresses[0]}"
    echo "[info] chord-tester on $entry ..."
    python3 "$CHORD_TESTER" "$entry" || true
  fi
  if [[ -f "$RUN_TESTER" ]]; then
    echo "[info] run-tester ..."
    python3 "$RUN_TESTER" "$peers_json" || true
  fi
fi

# ---- run benchmark
if [[ "$MODE" == "bench" || "$MODE" == "all" ]]; then
  if [[ -f "$BENCH_PY" ]]; then
    shift 2   # no N and mode
    BENCH_ARGS=("$@")   # remaining args go to bench.py so to test diferent options
    echo "[info] bench.py ..."
    python3 "$BENCH_PY" --peers "$SCRIPT_DIR/peers.json" \
      --csv "$SCRIPT_DIR/results.csv" "${BENCH_ARGS[@]}" || true
    echo "[info] bench done: $SCRIPT_DIR/results.csv"
  fi
fi

# ---- kill servers (cleanup after run)
if [[ "$KILL_AFTER" -eq 1 ]]; then
  echo "[info] killing servers ..."
  for N in $(cat /share/compute-nodes.txt); do
    ssh -o ConnectTimeout=1 "$N" "pkill -u $USER -f server.py" 2>/dev/null || true &
  done
  wait
fi
