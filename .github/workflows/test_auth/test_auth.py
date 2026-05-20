from __future__ import annotations

import json
import os
import sys
import time
import unittest
from datetime import datetime
from datetime import timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request
from urllib.request import urlopen
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy.exc import OperationalError


REPO_ROOT = Path(__file__).resolve().parents[3]
AUTH_SERVICE_ROOT = REPO_ROOT / "auth_service"
if str(AUTH_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AUTH_SERVICE_ROOT))


os.environ.setdefault("AUTH_DB_HOST", "localhost")
os.environ.setdefault("AUTH_DB_PORT", "5432")
os.environ.setdefault("AUTH_DB_USER", "kairos_auth_user")
os.environ.setdefault("AUTH_DB_PASSWORD", "kairos_auth_password")
os.environ.setdefault("AUTH_DB_NAME", "kairos_auth_db")
os.environ.setdefault("JWT_SECRET", "unit-test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")
os.environ.setdefault("JWT_REFRESH_EXPIRE_MINUTES", "10080")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_DB", "0")


from app import security  # noqa: E402
from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402


AUTH_TEST_BASE_URL = os.getenv("AUTH_TEST_BASE_URL", "http://localhost:8001")
RUN_E2E_TESTS = os.getenv("RUN_E2E_TESTS") == "1"


def _read_json_response(response) -> dict[str, object]:
    raw_body = response.read().decode("utf-8")
    return json.loads(raw_body) if raw_body else {}


def _request_json(
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, object], dict[str, str]]:
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)

    request_data = None
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
        request_data = json.dumps(payload).encode("utf-8")

    request = Request(
        f"{AUTH_TEST_BASE_URL}{path}",
        data=request_data,
        headers=request_headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=30) as response:
            return (
                response.status,
                _read_json_response(response),
                dict(response.headers.items()),
            )
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, json.loads(body) if body else {}, dict(exc.headers.items())


def _cleanup_user_by_email(email: str) -> None:
    db = None
    try:
        db = SessionLocal()
        user = db.query(models.User).filter(models.User.email == email).scalar_one_or_none()
        if user:
            db.delete(user)
            db.commit()
    except OperationalError:
        return
    except Exception:
        return
    finally:
        try:
            if db is not None:
                db.close()
        except Exception:
            pass


class AuthSecurityUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings_patch = patch.object(
            security,
            "settings",
            SimpleNamespace(
                jwt_secret="unit-test-secret",
                jwt_algorithm="HS256",
                jwt_expire_minutes=5,
                jwt_refresh_expire_minutes=10,
            ),
        )
        self.settings_patch.start()

    def tearDown(self) -> None:
        self.settings_patch.stop()

    def test_access_and_refresh_tokens_round_trip(self) -> None:
        user_id = uuid4()
        session_id = "session-123"

        access_token, access_expires_in = security.create_access_token(
            user_id=user_id,
            email="user@example.com",
            session_id=session_id,
        )
        refresh_token, refresh_expires_in = security.create_refresh_token(
            user_id=user_id,
            email="user@example.com",
            session_id=session_id,
        )

        access_claims = security.decode_access_token(access_token)
        refresh_claims = security.decode_refresh_token(refresh_token)

        self.assertEqual(access_expires_in, 300)
        self.assertEqual(refresh_expires_in, 600)
        self.assertEqual(access_claims["sub"], str(user_id))
        self.assertEqual(access_claims["email"], "user@example.com")
        self.assertEqual(access_claims["type"], "access")
        self.assertEqual(access_claims["sid"], session_id)
        self.assertEqual(refresh_claims["type"], "refresh")

    def test_decode_refresh_token_rejects_access_token(self) -> None:
        access_token, _ = security.create_access_token(
            user_id=uuid4(),
            email="user@example.com",
            session_id="session-456",
        )

        with self.assertRaises(Exception):
            security.decode_refresh_token(access_token)

    def test_get_token_expiration_handles_valid_token(self) -> None:
        token, _ = security.create_access_token(
            user_id=uuid4(),
            email="user@example.com",
            session_id="session-789",
        )

        expires_at = security.get_token_expiration(token)

        self.assertIsNotNone(expires_at)
        self.assertIsInstance(expires_at, datetime)
        self.assertEqual(expires_at.tzinfo, timezone.utc)


@unittest.skipUnless(RUN_E2E_TESTS, "E2E tests disabled")
class AuthServiceEndToEndTests(unittest.TestCase):
    def test_auth_service_flow(self) -> None:
        unique_suffix = int(time.time() * 1000)
        email = f"ci-auth-{unique_suffix}@example.com"
        password = "Secret123!"
        user_payload = {
            "nombre": "CI Auth",
            "email": email,
            "password": password,
        }

        self.addCleanup(_cleanup_user_by_email, email)

        register_status, register_body, _ = _request_json(
            "POST", "/auth/register", user_payload
        )
        self.assertIn(register_status, {200, 201})
        self.assertEqual(register_body["email"], email)

        login_status, login_body, _ = _request_json(
            "POST",
            "/auth/login",
            {"email": email, "password": password},
        )
        self.assertEqual(login_status, 200)
        access_token = str(login_body["access_token"])
        refresh_token = str(login_body["refresh_token"])

        status_status, status_body, _ = _request_json(
            "POST",
            "/auth/token-status",
            {"token": access_token},
        )
        self.assertEqual(status_status, 200)
        self.assertFalse(bool(status_body["blacklisted"]))

        me_status, me_body, _ = _request_json(
            "GET",
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(me_status, 200)
        self.assertEqual(me_body["email"], email)

        verify_status, verify_body, _ = _request_json(
            "GET",
            "/auth/verify",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(verify_status, 200)
        self.assertTrue(bool(verify_body["valid"]))
        self.assertEqual(verify_body["email"], email)

        refresh_status, refresh_body, _ = _request_json(
            "POST",
            "/auth/refresh",
            {"refresh_token": refresh_token},
        )
        self.assertEqual(refresh_status, 200)
        new_access_token = str(refresh_body["access_token"])
        new_refresh_token = str(refresh_body["refresh_token"])

        old_access_status, _, _ = _request_json(
            "GET",
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(old_access_status, 401)

        old_refresh_status, old_refresh_body, _ = _request_json(
            "POST",
            "/auth/token-status",
            {"token": refresh_token},
        )
        self.assertEqual(old_refresh_status, 200)
        self.assertTrue(bool(old_refresh_body["blacklisted"]))

        new_me_status, new_me_body, _ = _request_json(
            "GET",
            "/auth/me",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        self.assertEqual(new_me_status, 200)
        self.assertEqual(new_me_body["email"], email)

        new_verify_status, new_verify_body, _ = _request_json(
            "GET",
            "/auth/verify",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        self.assertEqual(new_verify_status, 200)
        self.assertTrue(bool(new_verify_body["valid"]))

        status_after_refresh, status_after_refresh_body, _ = _request_json(
            "POST",
            "/auth/token-status",
            {"token": new_refresh_token},
        )
        self.assertEqual(status_after_refresh, 200)
        self.assertFalse(bool(status_after_refresh_body["blacklisted"]))

    def test_clerk_sync_creates_and_updates_local_user(self) -> None:
        unique_suffix = int(time.time() * 1000)
        email = f"ci-clerk-{unique_suffix}@example.com"
        clerk_id = f"clerk_{unique_suffix}"

        self.addCleanup(_cleanup_user_by_email, email)

        first_payload = {
            "clerk_id": clerk_id,
            "email": email,
            "nombre": "CI Clerk",
            "avatar_url": "https://example.com/avatar-1.png",
        }
        create_status, create_body, _ = _request_json(
            "POST", "/auth/clerk/sync", first_payload
        )
        self.assertEqual(create_status, 200)
        self.assertEqual(create_body["email"], email)
        self.assertEqual(create_body["clerk_id"], clerk_id)
        self.assertEqual(create_body["avatar_url"], first_payload["avatar_url"])

        update_payload = {
            "clerk_id": clerk_id,
            "email": email,
            "nombre": "CI Clerk Updated",
            "avatar_url": "https://example.com/avatar-2.png",
        }
        update_status, update_body, _ = _request_json(
            "POST", "/auth/clerk/sync", update_payload
        )
        self.assertEqual(update_status, 200)
        self.assertEqual(update_body["id_usuario"], create_body["id_usuario"])
        self.assertEqual(update_body["clerk_id"], clerk_id)
        self.assertEqual(update_body["avatar_url"], update_payload["avatar_url"])
