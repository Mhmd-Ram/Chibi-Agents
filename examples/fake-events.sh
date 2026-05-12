#!/usr/bin/env bash
# Fire test events at a running chibi daemon.
# Usage:
#   ./fake-events.sh thinking
#   ./fake-events.sh tool Read
#   ./fake-events.sh subagent_start Explore exp-1
#   ./fake-events.sh subagent_stop  exp-1
#   ./fake-events.sh stop
set -euo pipefail

HOST=${CHIBI_HOST:-127.0.0.1}
PORT=${CHIBI_PORT:-47821}
URL="http://${HOST}:${PORT}/event"

post() {
  curl -s -X POST "$URL" -H "Content-Type: application/json" -d "$1" >/dev/null
}

cmd=${1:-thinking}
case "$cmd" in
  thinking)         post '{"type":"prompt_submit"}' ;;
  stop)             post '{"type":"stop"}' ;;
  notification)     post '{"type":"notification"}' ;;
  tool)             post "{\"type\":\"tool_start\",\"tool\":\"${2:-Read}\"}" ;;
  subagent_start)   post "{\"type\":\"subagent_start\",\"agent\":\"${2:-Explore}\",\"agent_id\":\"${3:-${2:-Explore}-1}\"}" ;;
  subagent_stop)    post "{\"type\":\"subagent_stop\",\"agent_id\":\"${2:-Explore-1}\"}" ;;
  close)            post "{\"type\":\"close\",\"agent_id\":\"${2:-Explore-1}\"}" ;;
  close_subagents)  post '{"type":"close_subagents"}' ;;
  close_all)        post '{"type":"close_all"}' ;;
  hide_main)        post '{"type":"hide_main"}' ;;
  show_main)        post '{"type":"show_main"}' ;;
  scale)            post "{\"type\":\"set_scale\",\"scale\":${2:-1.0}}" ;;
  say)              post "{\"type\":\"say\",\"text\":\"${2:-hello!}\"}" ;;
  toggle_speech)    post '{"type":"toggle_speech"}' ;;
  stats)            curl -s "http://${HOST}:${PORT}/stats" | python -m json.tool; exit 0 ;;
  *) echo "unknown command: $cmd" >&2; exit 2 ;;
esac

echo "ok: $cmd"
