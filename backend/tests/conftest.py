"""Integration test fixtures — require the stack to be running.

    make up && make migrate && make seed
    docker compose run --rm -e PYTEST=1 api pytest tests/
"""
import os

import httpx
import pytest

BASE_URL = os.getenv("API_URL", "http://localhost:8010")
SU_EMAIL = os.getenv("SUPERUSER_EMAIL", "admin@batmon.local")
SU_PASSWORD = os.getenv("SUPERUSER_PASSWORD", "changeme_superuser_password")
SU_NEW_PASSWORD = "Sup3rS3curePass!"

CLIENT_A_EMAIL = "client_a@test.batmon.local"
CLIENT_A_NAME = "Test Client A"
CLIENT_B_EMAIL = "client_b@test.batmon.local"
CLIENT_B_NAME = "Test Client B"
CLIENT_NEW_PASS = "Cl13ntP@ss123"


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    with httpx.Client(base_url=BASE_URL, timeout=10, follow_redirects=True) as c:
        yield c


def login(c: httpx.Client, email: str, password: str) -> str:
    r = c.post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def change_password(c: httpx.Client, token: str, old: str, new: str) -> str:
    r = c.post(
        "/auth/change-password",
        json={"current_password": old, "new_password": new},
        headers={"Authorization": f"Bearer {token}"},
    )
    r.raise_for_status()
    return r.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def superuser_token(client: httpx.Client) -> str:
    r = client.post("/auth/login", json={"email": SU_EMAIL, "password": SU_PASSWORD})
    if r.status_code == 200:
        token = r.json()["access_token"]
        if r.json().get("must_change_password"):
            token = change_password(client, token, SU_PASSWORD, SU_NEW_PASSWORD)
        return token
    # Password was already changed in a prior test run
    return login(client, SU_EMAIL, SU_NEW_PASSWORD)
