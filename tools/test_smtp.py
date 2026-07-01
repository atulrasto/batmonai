#!/usr/bin/env python3
"""
Step-by-step SMTP diagnostic.

Run INSIDE the api container:
  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    exec api python /app/tools/test_smtp.py

Or run standalone (reads .env from cwd):
  python tools/test_smtp.py
"""

import os
import smtplib
import socket
import sys
from email.message import EmailMessage

# ── Step 1: read env vars ────────────────────────────────────────────────────
print("\n=== STEP 1: Environment variables ===")
SMTP_HOST     = os.environ.get("SMTP_HOST", "")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM     = os.environ.get("SMTP_FROM", "") or SMTP_USER
SMTP_TLS      = os.environ.get("SMTP_TLS", "true").lower() == "true"
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "")

print(f"  SMTP_HOST     = {SMTP_HOST!r}")
print(f"  SMTP_PORT     = {SMTP_PORT}")
print(f"  SMTP_USER     = {SMTP_USER!r}")
print(f"  SMTP_PASSWORD = {'***' if SMTP_PASSWORD else '(empty)'}")
print(f"  SMTP_FROM     = {SMTP_FROM!r}")
print(f"  SMTP_TLS      = {SMTP_TLS}")
print(f"  CONTACT_EMAIL = {CONTACT_EMAIL!r}")

if not SMTP_HOST:
    print("\n[FAIL] SMTP_HOST is empty — container did not receive env var.")
    print("       Fix: docker compose ... up -d --force-recreate api")
    sys.exit(1)

if not CONTACT_EMAIL:
    print("\n[FAIL] CONTACT_EMAIL is empty.")
    sys.exit(1)

print("  -> All vars present.")

# ── Step 2: DNS resolution ────────────────────────────────────────────────────
print(f"\n=== STEP 2: DNS lookup for {SMTP_HOST} ===")
try:
    ip = socket.gethostbyname(SMTP_HOST)
    print(f"  -> Resolved to {ip}")
except socket.gaierror as e:
    print(f"  [FAIL] DNS error: {e}")
    sys.exit(1)

# ── Step 3: TCP connection ────────────────────────────────────────────────────
print(f"\n=== STEP 3: TCP connect to {SMTP_HOST}:{SMTP_PORT} ===")
try:
    sock = socket.create_connection((SMTP_HOST, SMTP_PORT), timeout=10)
    sock.close()
    print("  -> TCP connection OK")
except OSError as e:
    print(f"  [FAIL] TCP error: {e}")
    sys.exit(1)

# ── Step 4: SMTP handshake ────────────────────────────────────────────────────
print(f"\n=== STEP 4: SMTP handshake (STARTTLS={SMTP_TLS}) ===")
try:
    s = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
    s.set_debuglevel(1)
    s.ehlo()
    if SMTP_TLS:
        print("  -> Calling STARTTLS...")
        s.starttls()
        s.ehlo()
    print("  -> SMTP handshake OK")
except Exception as e:
    print(f"  [FAIL] SMTP handshake error: {e}")
    sys.exit(1)

# ── Step 5: authentication ────────────────────────────────────────────────────
print(f"\n=== STEP 5: SMTP login as {SMTP_USER!r} ===")
try:
    if SMTP_USER:
        s.login(SMTP_USER, SMTP_PASSWORD)
        print("  -> Login OK")
    else:
        print("  -> No SMTP_USER set, skipping login")
except smtplib.SMTPAuthenticationError as e:
    print(f"  [FAIL] Auth error: {e}")
    print("         Check SMTP_USER / SMTP_PASSWORD. For Gmail use an App Password,")
    print("         not your account password.")
    s.quit()
    sys.exit(1)
except Exception as e:
    print(f"  [FAIL] Login error: {e}")
    s.quit()
    sys.exit(1)

# ── Step 6: send test email ───────────────────────────────────────────────────
print(f"\n=== STEP 6: Send test email to {CONTACT_EMAIL!r} ===")
try:
    msg = EmailMessage()
    msg["Subject"] = "batmonai SMTP test"
    msg["From"]    = SMTP_FROM
    msg["To"]      = CONTACT_EMAIL
    msg.set_content("This is an automated SMTP diagnostic email from batmonai.\n\nIf you received this, the contact form is working correctly.")
    s.send_message(msg)
    s.quit()
    print(f"  -> Email sent successfully to {CONTACT_EMAIL}")
except Exception as e:
    print(f"  [FAIL] Send error: {e}")
    sys.exit(1)

print("\n=== ALL STEPS PASSED — SMTP is working ===\n")
