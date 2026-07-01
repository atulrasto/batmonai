"""Phase 2 acceptance: auth flow + forced-password-change gate."""
import pytest
import httpx

from tests.conftest import (
    BASE_URL,
    SU_EMAIL,
    SU_PASSWORD,
    SU_NEW_PASSWORD,
    auth_header,
    change_password,
    login,
)


def test_login_bad_credentials(client: httpx.Client) -> None:
    r = client.post("/auth/login", json={"email": SU_EMAIL, "password": "wrongpassword"})
    assert r.status_code == 401


def test_superuser_first_login_returns_must_change(client: httpx.Client) -> None:
    """On first login the token carries must_change_password=true."""
    r = client.post("/auth/login", json={"email": SU_EMAIL, "password": SU_PASSWORD})
    if r.status_code == 401:
        # password was already changed in a previous run — skip
        pytest.skip("Superuser password already changed")
    assert r.status_code == 200
    assert r.json()["must_change_password"] is True


def test_must_change_password_blocks_other_routes(client: httpx.Client) -> None:
    r = client.post("/auth/login", json={"email": SU_EMAIL, "password": SU_PASSWORD})
    if r.status_code == 401:
        pytest.skip("Superuser password already changed")
    token = r.json()["access_token"]
    # /auth/me should work (no password change gate on /me itself)
    # but protected routes like /clients should return 403
    r2 = client.get("/clients", headers=auth_header(token))
    assert r2.status_code == 403
    assert r2.json()["detail"] == "PASSWORD_CHANGE_REQUIRED"


def test_change_password_clears_flag(client: httpx.Client) -> None:
    r = client.post("/auth/login", json={"email": SU_EMAIL, "password": SU_PASSWORD})
    if r.status_code == 401:
        pytest.skip("Superuser password already changed")
    token = r.json()["access_token"]
    new_token = change_password(client, token, SU_PASSWORD, SU_NEW_PASSWORD)
    assert new_token
    r2 = client.get("/clients", headers=auth_header(new_token))
    assert r2.status_code == 200  # superuser can list clients after password change


def test_superuser_token_valid(client: httpx.Client, superuser_token: str) -> None:
    r = client.get("/auth/me", headers=auth_header(superuser_token))
    assert r.status_code == 200
    assert r.json()["role"] == "superuser"
