# batmonai — Production Deployment Guide

## Architecture Overview

```
Internet
    │
    ▼
192.168.0.204 (front Caddy, LAN gateway)
    │  HTTP/HTTPS → batmon.energymonai.com
    ▼
VM4 (Rocky Linux)  ← this guide covers VM4
    │
    └── docker compose (all services)
            ├── caddy        (HTTPS, /api/* proxy, /*)
            ├── api          (FastAPI on :8000, internal)
            ├── frontend     (nginx on :80, internal)
            ├── ingestion    (MQTT → DB)
            ├── mosquitto    (:8883 TLS, public)
            ├── pgbouncer    (connection pool, internal)
            ├── postgres     (TimescaleDB, internal)
            ├── migrate      (one-shot, runs on deploy)
            └── backup       (pg_dump cron, 02:30 daily)
```

**MQTT 8883** is raw TCP (not HTTP). The front Caddy on `192.168.0.204` cannot proxy raw TCP by default. See [§6 MQTT forward](#6-l4-forward-for-mqtt-8883) for options.

---

## Prerequisites on VM4

```bash
# Rocky Linux 9 — install Docker
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker

# Add your user to the docker group (re-login after)
sudo usermod -aG docker $USER

# Open firewall ports
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --permanent --add-port=8883/tcp   # MQTT TLS
sudo firewall-cmd --reload
```

---

## 1. First-time Setup

```bash
# Clone the repo
git clone https://github.com/atulrasto/batmonai.git /home/harshit/batmonai
cd /home/harshit/batmonai

# Copy and edit the environment file
cp .env.example .env
nano .env   # Fill in real passwords, JWT secret, SMTP, etc.
```

**Minimum `.env` changes for prod:**

| Key | What to set |
|-----|------------|
| `POSTGRES_PASSWORD` | Strong random password |
| `APP_DB_PASSWORD` | Different strong random password |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` |
| `SUPERUSER_EMAIL` | Your admin email |
| `SUPERUSER_PASSWORD` | Strong initial password (you will change it on first login) |
| `MQTT_INGESTION_PASSWORD` | Strong random string |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | Your SMTP relay credentials |
| `SMTP_FROM` | Sender address, e.g. `alerts@batmon.energymonai.com` |

**Remove or comment out dev-only port mappings** (optional — the prod override suppresses them anyway):

```env
# These are ignored by docker-compose.prod.yml but harmless to leave:
POSTGRES_HOST_PORT=5450
PGBOUNCER_HOST_PORT=6450
API_HOST_PORT=8010
FRONTEND_HOST_PORT=5180
CADDY_HTTP_PORT=8080
CADDY_HTTPS_PORT=8443
```

---

## 2. TLS Certificates for MQTT

The Mosquitto broker requires TLS certs. In prod, use a **real CA-signed cert** or the same cert that Caddy manages for your domain.

### Option A — Caddy-managed cert (recommended)

Caddy fetches a Let's Encrypt cert for `batmon.energymonai.com`. Copy the cert into the mosquitto certs directory:

```bash
# After Caddy has obtained its cert (first start), extract it:
mkdir -p mosquitto/certs

# Find Caddy's cert storage (inside the caddy_data volume):
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  exec caddy sh -c "find /data/caddy/certificates -name '*.crt' | head -5"

# Copy files out:
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  cp caddy:/data/caddy/certificates/acme-v02.api.letsencrypt.org-directory/batmon.energymonai.com/batmon.energymonai.com.crt \
  mosquitto/certs/server.crt

docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  cp caddy:/data/caddy/certificates/acme-v02.api.letsencrypt.org-directory/batmon.energymonai.com/batmon.energymonai.com.key \
  mosquitto/certs/server.key

# For MQTT client CA verification, use Let's Encrypt root:
curl -o mosquitto/certs/ca.crt https://letsencrypt.org/certs/isrgrootx1.pem
```

Then update `mosquitto/mosquitto.conf` to reference these files. Restart mosquitto after copying.

### Option B — Self-signed dev cert (quick test)

```bash
make gen-certs   # generates a local CA + server cert in mosquitto/certs/
```

Clients (firmware / `sim_publisher.py`) must trust `mosquitto/certs/ca.crt`.

---

## 3. VM4 Caddy — `caddy/Caddyfile.prod` (already in the repo)

VM4's Caddy container routes HTTP traffic internally — it does **not** handle TLS or ACME. TLS is terminated by the front Caddy on `192.168.0.204` (see §4).

**No manual setup needed.** The file already exists in the repo at `caddy/Caddyfile.prod` and `docker-compose.prod.yml` mounts it automatically:

```yaml
# inside docker-compose.prod.yml (already configured)
caddy:
  volumes:
    - ./caddy/Caddyfile.prod:/etc/caddy/Caddyfile:ro
```

Content of `caddy/Caddyfile.prod` for reference:

```
{
    auto_https off
}

:80 {
    handle /api/* {
        uri strip_prefix /api
        reverse_proxy api:8000
    }
    handle {
        reverse_proxy frontend:80
    }
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        ...
    }
}
```

VM4's Caddy listens on port 80 only. The front Caddy on `192.168.0.204` is the only public HTTPS endpoint.

---

## 4. Front Caddy Configuration (192.168.0.204) — TLS termination

The **gateway** Caddy on `192.168.0.204` terminates TLS for `batmon.energymonai.com`, obtains the Let's Encrypt cert, and proxies plain HTTP to VM4. Add this site block to its `/etc/caddy/Caddyfile`:

```
# /etc/caddy/Caddyfile on 192.168.0.204
batmon.energymonai.com {
    reverse_proxy VM4_IP:80
}
```

Replace `VM4_IP` with VM4's LAN IP address. Caddy on `192.168.0.204` will automatically obtain a Let's Encrypt cert — port 80 and 443 must be reachable from the internet on that machine. After adding the block, reload:

```bash
sudo systemctl reload caddy   # or: caddy reload --config /etc/caddy/Caddyfile
```

---

## 5. Deploy

```bash
cd /home/harshit/batmonai

# Pull latest code
git pull

# Start everything (migrate runs automatically before api/ingestion start)
make prod-up

# Seed the superuser (only needed on first deploy)
make prod-seed
```

**Deploy sequence on every update:**

```bash
cd /home/harshit/batmonai
git pull
make prod-up   # docker compose pull + build + up -d
```

Migrations run automatically via the `migrate` service which must complete successfully before `api` and `ingestion` start (enforced by `depends_on: condition: service_completed_successfully`).

---

## 6. L4 Forward for MQTT (:8883)

MQTT uses raw TCP on port 8883. The front Caddy (`192.168.0.204`) cannot proxy raw TCP without the `caddy-l4` experimental plugin. Choose one option:

### Option A — firewalld DNAT on 192.168.0.204 (simplest)

```bash
# On the 192.168.0.204 machine:
# Forward incoming :8883 TCP to VM4:8883
sudo firewall-cmd --permanent --add-masquerade
sudo firewall-cmd --permanent --add-forward-port=port=8883:proto=tcp:toport=8883:toaddr=VM4_IP
sudo firewall-cmd --reload

# Verify:
sudo firewall-cmd --list-forward-ports
```

### Option B — caddy-l4 plugin on 192.168.0.204

Build a custom Caddy with the `caddy-l4` module and add to the Caddyfile:

```
{
    layer4 {
        0.0.0.0:8883 {
            route {
                proxy {
                    upstream VM4_IP:8883
                }
            }
        }
    }
}
```

### Option C — Direct public IP port-forward

If the public IP maps directly to VM4 (or if the router allows port forwarding), simply forward TCP 8883 → VM4:8883 in the router/firewall and skip the Caddy L4 config entirely.

---

## 7. Verify the Deployment

```bash
# Check all containers are healthy
make prod-logs   # or:
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

# Test HTTPS
curl -I https://batmon.energymonai.com/

# Test API health
curl https://batmon.energymonai.com/api/health

# Test MQTT TLS from a client machine
mosquitto_pub -h batmon.energymonai.com -p 8883 \
  --cafile mosquitto/certs/ca.crt \
  -u ingestion -P <MQTT_INGESTION_PASSWORD> \
  -t test -m hello
```

---

## 8. Backups

The `backup` service runs `pg_dump` daily at 02:30 (configurable via `BACKUP_CRON` in `.env`). Dumps are written to `./backups/` on the host and the last 14 are retained.

```bash
# Trigger an immediate backup
make backup

# List backups
ls -lh backups/

# Restore from a specific dump
make restore FILE=backups/batmonai_20260701_023001.dump
```

Optionally rsync `backups/` to off-site storage:

```bash
# Add to host crontab (runs after the 02:30 backup):
# 03:00 * * * rsync -az /home/harshit/batmonai/backups/ user@backup-server:/backups/batmonai/
```

---

## 9. Routine Operations

| Task | Command |
|------|---------|
| View logs | `make prod-logs` |
| Restart a service | `docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api` |
| Run a migration manually | `make prod-migrate` |
| Roll back one migration | `docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate alembic downgrade -1` |
| Open a DB shell | `docker compose exec postgres psql -U batmonai -d batmonai` |
| Force-refresh Caddy cert | `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile` |

---

## 10. Troubleshooting

**Container won't start — dependency not healthy**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps   # check status
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs postgres
```

**Migration fails**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate alembic history
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate alembic current
```

**Caddy not obtaining cert**

- Ensure port 80 and 443 reach VM4 from the internet (the front Caddy must forward or the domain must point directly).
- Check `docker compose logs caddy` for ACME errors.
- Verify the DNS A record for `batmon.energymonai.com` resolves to the public IP.

**MQTT devices can't connect**

- Confirm port 8883 is reachable: `nc -zv batmon.energymonai.com 8883`
- Check the L4 forward is in place (§5).
- Verify the device's CA cert matches the broker's cert.
- Check `docker compose logs mosquitto` for auth rejections.

**Device publishes but no DB rows**

```bash
docker compose logs ingestion | tail -50
# Look for "Unknown or inactive appliance" — the appliance must exist in the DB
# and be active before it can publish telemetry.
```
