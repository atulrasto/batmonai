# New VM Project Playbook

Quick reference for deploying any future Docker Compose project on a new VM (e.g. VM5) behind the front Caddy gateway on `192.168.0.204`.

---

## 1. Provision the VM (Rocky Linux 9)

```bash
# Install Docker
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin make git
sudo systemctl enable --now docker

# Add deploy user to docker group (re-login after)
sudo usermod -aG docker $USER
```

---

## 2. Open firewall ports

```bash
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
# Add any other project-specific ports (e.g. 8883 for MQTT)
sudo firewall-cmd --reload
```

---

## 3. Clone the project

```bash
git clone https://github.com/atulrasto/<project>.git /home/harshit/<project>
cd /home/harshit/<project>
cp .env.example .env
nano .env   # fill in all required values
```

---

## 4. Generate MQTT TLS certs (if project uses Mosquitto)

```bash
mkdir -p mosquitto/certs
cd mosquitto/certs

openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
  -subj "/C=IN/O=myproject/CN=myproject-ca"

openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr \
  -subj "/C=IN/O=myproject/CN=<domain>"
openssl x509 -req -days 3650 -in server.csr \
  -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt \
  -extfile <(printf "[v3]\nsubjectAltName=DNS:<domain>\nextendedKeyUsage=serverAuth") \
  -extensions v3

chmod 644 server.key server.crt ca.crt
rm server.csr ca.srl
cd /home/harshit/<project>
```

---

## 5. Configure VM's internal Caddy (HTTP only — no TLS)

The project's `Caddyfile.prod` (or equivalent) should have:

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
}
```

TLS is handled entirely by the front Caddy on `192.168.0.204` — do NOT enable ACME on the VM's Caddy.

---

## 6. Start services

```bash
make prod-up        # builds + starts all containers
make prod-seed      # seed initial data (first deploy only)
```

Check everything is healthy:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

---

## 7. Add domain to front Caddy (192.168.0.204)

SSH into `192.168.0.204` and edit `/home/harshit/energymonai/Caddyfile` (or wherever the proxy Caddyfile lives):

```
<newdomain>.energymonai.com {
    reverse_proxy VM5_LAN_IP:80
}
```

Reload the proxy:

```bash
cd /home/harshit/energymonai
docker compose restart proxy
```

Caddy will automatically obtain a Let's Encrypt cert for the new domain. The site will be live at `https://<newdomain>.energymonai.com` within ~30 seconds.

---

## 8. MQTT TCP forwarding (if project uses Mosquitto on 8883)

MQTT is raw TCP — the HTTP reverse proxy cannot handle it. You need a separate L4 forward from the public-facing machine to the new VM.

**Check first:** is port 8883 already in use on `192.168.0.204`?
```bash
ss -tlnp | grep 8883   # on 192.168.0.204
```

### If 8883 is free on 192.168.0.204 — DNAT to new VM
```bash
# On 192.168.0.204:
sudo firewall-cmd --permanent --add-masquerade
sudo firewall-cmd --permanent \
  --add-forward-port=port=8883:proto=tcp:toport=8883:toaddr=VM_LAN_IP
sudo firewall-cmd --reload
```

### If 8883 is already taken (e.g. another project) — use a different public port
```bash
# Example: external 8884 → VM_LAN_IP:8883
sudo firewall-cmd --permanent --add-masquerade
sudo firewall-cmd --permanent \
  --add-forward-port=port=8884:proto=tcp:toport=8883:toaddr=VM_LAN_IP
sudo firewall-cmd --reload
```
Then configure firmware/devices to connect on the alternate port (8884 in this example).

### If router allows direct port-forward to the VM (cleanest)
Forward TCP `8883` → `VM_LAN_IP:8883` in the router/firewall directly. No front-machine config needed.

> **Current state (2026-07-01):**
> - energymonai on `192.168.0.204` occupies port **8883**
> - batmonai on VM4 (`192.168.0.207`) needs **8883 forwarded via router** OR mapped to a different external port (e.g. 8884) via firewalld DNAT on `192.168.0.204`

---

## 9. Every future deploy

```bash
cd /home/harshit/<project>
git pull
make prod-up
```

Migrations and rebuilds happen automatically.

---

## Checklist

- [ ] VM has Docker + make + git installed
- [ ] Deploy user is in `docker` group (re-logged in)
- [ ] Firewall ports open (80, 443, + project-specific)
- [ ] `.env` filled from `.env.example`
- [ ] MQTT certs generated (if needed) with correct domain SAN
- [ ] `Caddyfile.prod` uses `auto_https off`, listens on `:80` only
- [ ] `make prod-up` — all containers healthy
- [ ] `make prod-seed` — initial data seeded
- [ ] New domain block added to proxy Caddyfile on `192.168.0.204`
- [ ] Proxy reloaded — cert obtained — site live on HTTPS
- [ ] MQTT TCP forward configured (check port conflicts with existing projects)
