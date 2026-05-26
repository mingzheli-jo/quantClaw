#!/usr/bin/env bash
set -e

DOMAIN="quant.azhefuye.online"
APP_PORT=8000
NGINX_CONF="/etc/nginx/sites-available/${DOMAIN}"
NGINX_LINK="/etc/nginx/sites-enabled/${DOMAIN}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Pre-flight checks ---
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Please run with sudo:  sudo bash start.sh"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "==> .env not found, creating from .env.example..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "IMPORTANT: Edit .env and set SECRET_KEY, ADMIN_PASSWORD, FEISHU_WEBHOOK_URL"
    echo "Then re-run this script."
    exit 1
fi

# --- Step 1: Install Nginx & Certbot if missing ---
echo "==> Checking Nginx and Certbot..."
if ! command -v nginx &>/dev/null; then
    echo "    Installing Nginx..."
    apt-get update -qq && apt-get install -y -qq nginx
fi

if ! command -v certbot &>/dev/null; then
    echo "    Installing Certbot..."
    apt-get update -qq && apt-get install -y -qq certbot python3-certbot-nginx
fi

# --- Step 2: Build and start Docker containers ---
echo "==> Building and starting containers..."
cd "$PROJECT_DIR"
docker compose down --remove-orphans 2>/dev/null || true
docker compose build
docker compose up -d

echo "==> Waiting for app to be ready..."
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:${APP_PORT}/api/health >/dev/null 2>&1 || \
       curl -sf http://127.0.0.1:${APP_PORT}/docs >/dev/null 2>&1 || \
       curl -sf http://127.0.0.1:${APP_PORT}/ >/dev/null 2>&1; then
        echo "    App is up!"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "    WARNING: App may not be fully ready yet, continuing with Nginx setup..."
    fi
    sleep 2
done

# --- Step 3: Configure Nginx reverse proxy ---
echo "==> Configuring Nginx for ${DOMAIN}..."
cat > "$NGINX_CONF" <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
NGINX

ln -sf "$NGINX_CONF" "$NGINX_LINK"
nginx -t && systemctl reload nginx
echo "    Nginx configured (HTTP)."

# --- Step 4: SSL certificate ---
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
if [ ! -d "$CERT_DIR" ]; then
    echo "==> Requesting SSL certificate for ${DOMAIN}..."
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect
    echo "    SSL certificate obtained and Nginx updated."
else
    echo "==> SSL certificate already exists, ensuring Nginx is configured..."
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect --keep-existing
    echo "    SSL verified."
fi

# --- Done ---
echo ""
echo "========================================="
echo "  QuantClaw is running!"
echo "  URL: https://${DOMAIN}"
echo "  Logs: docker compose logs -f quantclaw"
echo "  Restart: docker compose restart"
echo "========================================="
