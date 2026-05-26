#!/usr/bin/env bash
set -e

DOMAIN="quant.azhefuye.online"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
CADDY_FILE="/opt/wechat-batch-rewriter/Caddyfile"
CADDY_CONTAINER="wechat-batch-rewriter-caddy-1"
NETWORK_NAME="caddy-net"

# --- Pre-flight checks ---
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "==> .env not found, creating from .env.example..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "IMPORTANT: Edit .env and set SECRET_KEY, ADMIN_PASSWORD, FEISHU_WEBHOOK_URL"
    echo "Then re-run this script."
    exit 1
fi

# --- Step 1: Create shared Docker network ---
echo "==> Creating shared network: ${NETWORK_NAME}..."
docker network create "$NETWORK_NAME" 2>/dev/null || true

# --- Step 2: Connect Caddy to shared network ---
echo "==> Connecting Caddy to ${NETWORK_NAME}..."
docker network connect "$NETWORK_NAME" "$CADDY_CONTAINER" 2>/dev/null || true

# --- Step 3: Add QuantClaw to Caddyfile ---
if ! grep -q "$DOMAIN" "$CADDY_FILE" 2>/dev/null; then
    echo "==> Adding ${DOMAIN} to Caddyfile..."
    cat >> "$CADDY_FILE" <<CADDY

${DOMAIN} {
    encode zstd gzip

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
        -Server
    }

    reverse_proxy quantclaw-quantclaw-1:8000

    log {
        output file /data/quant-access.log
        format json
    }
}
CADDY
    echo "    Caddyfile updated."
else
    echo "==> ${DOMAIN} already in Caddyfile, skipping."
fi

# --- Step 4: Build and start QuantClaw ---
echo "==> Building and starting containers..."
cd "$PROJECT_DIR"
docker compose down --remove-orphans 2>/dev/null || true
docker compose build
docker compose up -d

# --- Step 5: Reload Caddy to pick up new config ---
echo "==> Reloading Caddy..."
docker exec "$CADDY_CONTAINER" caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile 2>/dev/null || \
    docker restart "$CADDY_CONTAINER"

# --- Step 6: Remove host Nginx config if exists ---
if [ -f "/etc/nginx/sites-enabled/${DOMAIN}" ]; then
    echo "==> Cleaning up old Nginx config..."
    rm -f "/etc/nginx/sites-enabled/${DOMAIN}" "/etc/nginx/sites-available/${DOMAIN}"
    systemctl reload nginx 2>/dev/null || true
fi

echo ""
echo "========================================="
echo "  QuantClaw is running!"
echo "  URL: https://${DOMAIN}"
echo "  Logs: docker compose logs -f quantclaw"
echo "  Restart: docker compose restart"
echo "========================================="
