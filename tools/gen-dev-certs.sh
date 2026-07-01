#!/bin/bash
# Generates a self-signed CA and Mosquitto server certificate for local dev.
# The server cert has SANs for both "mosquitto" (Docker hostname) and "localhost".
# Run once: make gen-certs
#
# Uses OpenSSL config files (not -subj) to avoid Git Bash path-conversion issues on Windows.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CERTS_DIR="$SCRIPT_DIR/../mosquitto/certs"

mkdir -p "$CERTS_DIR"
cd "$CERTS_DIR"

# ── CA config ─────────────────────────────────────────────────────────────────
cat > _ca.cnf << 'EOF'
[req]
default_bits       = 2048
prompt             = no
distinguished_name = dn
x509_extensions    = v3_ca

[dn]
C  = IN
ST = Dev
L  = Local
O  = batmonai
CN = batmonai-dev-ca

[v3_ca]
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid:always,issuer
basicConstraints       = critical, CA:true
keyUsage               = critical, keyCertSign, cRLSign
EOF

echo "Generating dev CA key + cert..."
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
    -config _ca.cnf -extensions v3_ca

# ── Server cert config (with SANs) ────────────────────────────────────────────
cat > _server.cnf << 'EOF'
[req]
default_bits       = 2048
prompt             = no
distinguished_name = dn

[dn]
C  = IN
ST = Dev
L  = Local
O  = batmonai
CN = mosquitto

[v3_req]
subjectAltName   = @alt_names
keyUsage         = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
DNS.1 = mosquitto
DNS.2 = localhost
IP.1  = 127.0.0.1
EOF

echo "Generating server key + cert with SANs (mosquitto, localhost, 127.0.0.1)..."
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out _server.csr -config _server.cnf
openssl x509 -req -days 3650 \
    -in _server.csr \
    -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out server.crt \
    -extensions v3_req -extfile _server.cnf

# ── Cleanup ───────────────────────────────────────────────────────────────────
rm -f _ca.cnf _server.cnf _server.csr ca.srl

echo ""
echo "Done. Files in: $CERTS_DIR"
echo "  ca.crt     — trust anchor (used by ingestion + sim_publisher TLS mode)"
echo "  server.crt — Mosquitto TLS certificate"
echo "  server.key — Mosquitto TLS private key"
echo ""
echo "Next: make up"
