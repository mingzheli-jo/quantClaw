#!/usr/bin/env bash
set -e

if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in values."
    exit 1
fi

source .env

# First time: get SSL certificate
if [ ! -d "certbot/conf/live/quant.azhefuye.online" ]; then
    echo "==> Requesting initial SSL certificate..."
    mkdir -p certbot/conf certbot/www

    # Start nginx temporarily for ACME challenge
    docker compose up -d nginx
    sleep 5

    docker compose run --rm certbot certonly \
        --webroot --webroot-path=/var/www/certbot \
        --email ${ADMIN_EMAIL:-admin@example.com} \
        --agree-tos --no-eff-email \
        -d quant.azhefuye.online

    docker compose down
    echo "==> SSL certificate obtained."
fi

echo "==> Building and starting QuantClaw..."
docker compose build
docker compose up -d

echo ""
echo "========================================="
echo "  QuantClaw is running!"
echo "  URL: https://quant.azhefuye.online"
echo "  Logs: docker compose logs -f quantclaw"
echo "========================================="
