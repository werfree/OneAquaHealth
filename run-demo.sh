#!/usr/bin/env bash
# Demo helper for the OneAquaHealth pipeline.
#
#   ./run-demo.sh stack     start RabbitMQ (needs colima/docker running)
#   ./run-demo.sh app       run the ingestion app in the foreground (PANE 1)
#   ./run-demo.sh publish   send one sample down each of the three channels
#   ./run-demo.sh verify    read the resources back off the FHIR server
#   ./run-demo.sh ask "…"   put a question to the assistant
#   ./run-demo.sh brief     generate the One Health risk briefing
#   ./run-demo.sh seed      generate + ingest the 28-day series (takes a few minutes)
#   ./run-demo.sh studio    open the surveillance studio with the autodemo running
#   ./run-demo.sh down      stop RabbitMQ
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH=oah-agent/src:oah-ingestion/src:oah-pydantic-models/src:oah-demo-publishers/src

case "${1:-}" in
  stack)
    docker start oah-rabbitmq 2>/dev/null || \
    docker run -d --name oah-rabbitmq -p 5672:5672 -p 15672:15672 \
      -e RABBITMQ_DEFAULT_USER=oah -e RABBITMQ_DEFAULT_PASS=oah-local-dev \
      -v rabbitmq_data:/var/lib/rabbitmq rabbitmq:4-management
    printf 'waiting for RabbitMQ'
    until docker exec oah-rabbitmq rabbitmq-diagnostics -q ping >/dev/null 2>&1; do printf '.'; sleep 2; done
    echo ' ready'
    ;;
  app)     exec python3 -m oah_ingestion.app ;;
  seed)    exec python3 demo/generate_timeseries.py --days 28 --ingest ;;
  publish) exec python3 -m oah_demo_publishers ;;
  verify)  exec python3 - <<'PY'
from oah_agent.tools import search_observations, list_sites
print("Sites on the FHIR server:")
for s in list_sites()["sites"]:
    print(f"   {s['site_id']:<22} {s['name']}")
print()
for kind, label in [("environmental_component", "with-component"),
                    ("environmental_simple",    "indicators    "),
                    ("health",                  "health-measure")]:
    r = search_observations(kind=kind, limit=200)
    print(f"{label}: {r['count']:>2} Observation(s)")
PY
    ;;
  ask)   shift; exec python3 -m oah_agent.cli "$@" ;;
  brief) shift; exec python3 -m oah_agent.cli --brief "$@" ;;
  chat)  exec python3 -m oah_agent.cli --chat ;;
  studio) exec open "http://localhost:8000/api/officer/panel?autorun=1" ;;
  down)  docker stop oah-rabbitmq ;;
  *) sed -n '2,12p' "$0"; exit 1 ;;
esac
