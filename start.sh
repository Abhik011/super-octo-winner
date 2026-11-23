
#!/bin/bash

set -m

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT_DIR/.venv/bin"

echo "======================================"
echo "       MAISON KALA BACKEND"
echo "======================================"

start_service() {
    NAME="$1"
    DIR="$2"
    PORT="$3"

    echo "Starting $NAME on port $PORT..."

    (
        cd "$ROOT_DIR/$DIR"
        "$VENV/uvicorn" app.main:app \
            --reload \
            --host 127.0.0.1 \
            --port "$PORT"
    ) &

    PIDS+=("$!")
}

PIDS=()

cleanup() {
    echo ""
    echo "Stopping Maison Kala services..."

    for PID in "${PIDS[@]}"; do
        kill "$PID" 2>/dev/null || true
    done

    wait
    echo "All services stopped."
}

trap cleanup INT TERM EXIT

start_service "Identity" "services/identity" 8001
start_service "Catalog" "services/catalog" 8002
start_service "Inventory" "services/inventory" 8003
start_service "Cart" "services/cart" 8004
start_service "Order" "services/order-service" 8005

echo ""
echo "======================================"
echo "       SERVICES STARTED"
echo "======================================"
echo "Identity:  http://localhost:8001/docs"
echo "Catalog:   http://localhost:8002/docs"
echo "Inventory: http://localhost:8003/docs"
echo "Cart:      http://localhost:8004/docs"
echo "Orders:    http://localhost:8005/docs"
echo "======================================"
echo "Press CTRL+C to stop all services."

wait
