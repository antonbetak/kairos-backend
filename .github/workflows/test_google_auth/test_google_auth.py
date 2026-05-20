from __future__ import annotations

from http.client import HTTPConnection
import json
import os
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs
from urllib.parse import urlparse
from urllib.request import Request
from urllib.request import urlopen
from unittest.mock import AsyncMock
from unittest.mock import patch
from types import ModuleType


fake_pika = ModuleType("pika")
fake_pika.URLParameters = object
fake_pika.BlockingConnection = object
fake_pika.BasicProperties = object
sys.modules.setdefault("pika", fake_pika)

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[3]
GOOGLE_AUTH_ROOT = REPO_ROOT / "google_auth"
if str(GOOGLE_AUTH_ROOT) not in sys.path:
    sys.path.insert(0, str(GOOGLE_AUTH_ROOT))


from app.config import Settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services.google_oauth import GoogleOAuthService  # noqa: E402
from app.services.google_oauth import get_google_oauth_service  # noqa: E402


GOOGLE_AUTH_TEST_BASE_URL = os.getenv(
    "GOOGLE_AUTH_TEST_BASE_URL", "http://localhost:8007"
)
RUN_E2E_TESTS = os.getenv("RUN_E2E_TESTS") == "1"


def _read_json_response(response) -> dict[str, object]:
    raw_body = response.read().decode("utf-8")
    return json.loads(raw_body) if raw_body else {}


def _request_json(
    method: str, path: str
) -> tuple[int, dict[str, object], dict[str, str]]:
    request = Request(
        f"{GOOGLE_AUTH_TEST_BASE_URL}{path}",
        headers={"Accept": "application/json"},
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


class GoogleOAuthServiceUnitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            google_client_id="client-id",
            google_client_secret="client-secret",
            google_redirect_uri="http://localhost/callback",
            auth_service_url="http://auth_service:8000",
        )
        self.service = GoogleOAuthService(self.settings)

    def test_state_round_trip(self) -> None:
        state = self.service._create_state(
            client_id="client-id",
            redirect_uri="http://localhost/callback",
        )
        payload = self.service._extract_state_payload(state)

        self.assertTrue(payload.nonce)
        self.assertGreater(payload.issued_at, 0)

    def test_build_authorization_url_contains_expected_parameters(self) -> None:
        authorization_url = self.service.build_authorization_url()
        parsed_url = urlparse(authorization_url)
        query_params = parse_qs(parsed_url.query)

        self.assertEqual(parsed_url.scheme, "https")
        self.assertIn("accounts.google.com", parsed_url.netloc)
        self.assertEqual(query_params["client_id"][0], "client-id")
        self.assertEqual(query_params["redirect_uri"][0], "http://localhost/callback")
        self.assertEqual(query_params["response_type"][0], "code")
        self.assertEqual(query_params["scope"][0], self.settings.google_scope)
        self.assertIn("state", query_params)
        self.assertIn("nonce", query_params)
        self.assertEqual(
            self.service._extract_state_payload(query_params["state"][0]).nonce,
            query_params["nonce"][0],
        )

    async def test_get_current_user_uses_verified_id_token(self) -> None:
        claims = {
            "email": "user@example.com",
            "name": "CI User",
            "picture": "https://example.com/avatar.png",
            "sub": "google-user-123",
            "email_verified": True,
        }

        with (
            patch.object(self.service, "_token_status", AsyncMock(return_value=False)),
            patch.object(
                self.service,
                "verify_id_token",
                return_value=claims,
            ),
        ):
            profile = await self.service.get_current_user("token-value")

        self.assertEqual(profile.email, "user@example.com")
        self.assertEqual(profile.name, "CI User")
        self.assertEqual(profile.google_id, "google-user-123")
        self.assertTrue(profile.email_verified)

    async def test_authenticate_builds_user_and_token_payload(self) -> None:
        state = self.service._create_state(
            client_id="client-id",
            redirect_uri="http://localhost/callback",
        )
        token_response = {
            "access_token": "access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "refresh-token",
            "scope": "openid email profile",
            "id_token": "id-token",
        }
        claims = {
            "email": "user@example.com",
            "name": "CI User",
            "picture": "https://example.com/avatar.png",
            "sub": "google-user-123",
            "email_verified": True,
        }

        with (
            patch.object(
                self.service, "exchange_code", AsyncMock(return_value=token_response)
            ),
            patch.object(
                self.service,
                "verify_id_token",
                return_value=claims,
            ),
            patch.object(self.service, "fetch_userinfo", AsyncMock(return_value={})),
            patch.object(
                self.service._auth_sync_bus,
                "sync_google_user",
                return_value=(
                    {
                        "id_usuario": "11111111-1111-1111-1111-111111111111",
                        "nombre": "CI User",
                        "email": "user@example.com",
                        "handle": "ciuser",
                        "avatar_url": "https://example.com/avatar.png",
                    },
                    {
                        "access_token": "kairos-access",
                        "refresh_token": "kairos-refresh",
                        "token_type": "bearer",
                        "expires_in": 3600,
                        "refresh_expires_in": 7200,
                    },
                ),
            ),
        ):
            response = await self.service.authenticate("authorization-code", state)

        self.assertEqual(response.provider, "google")
        self.assertEqual(response.user.email, "user@example.com")
        self.assertEqual(response.tokens.access_token, "access-token")
        self.assertEqual(response.tokens.refresh_token, "refresh-token")
        self.assertEqual(response.kairos_user.email, "user@example.com")
        self.assertEqual(response.kairos_tokens.access_token, "kairos-access")


class GoogleOAuthRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            google_client_id="client-id",
            google_client_secret="client-secret",
            google_redirect_uri="http://localhost/callback",
            auth_service_url="http://auth_service:8000",
        )
        self.service = GoogleOAuthService(self.settings)
        app.dependency_overrides[get_google_oauth_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_clerk_session_route_calls_sync_flow(self) -> None:
        payload = {
            "user": {
                "email": "user@example.com",
                "name": "CI User",
                "picture": "https://example.com/avatar.png",
                "google_id": "google-user-123",
                "email_verified": True,
            },
            "tokens": {
                "access_token": "google-access",
                "token_type": "Bearer",
                "refresh_token": "google-refresh",
                "id_token": "google-id-token",
            },
        }

        with (
            patch.object(
                self.service,
                "_verify_clerk_google_token",
                AsyncMock(return_value=None),
            ),
            patch.object(
                self.service._auth_sync_bus,
                "sync_google_user",
                return_value=(
                    {
                        "id_usuario": "11111111-1111-1111-1111-111111111111",
                        "nombre": "CI User",
                        "email": "user@example.com",
                        "handle": "ciuser",
                        "avatar_url": "https://example.com/avatar.png",
                    },
                    {
                        "access_token": "kairos-access",
                        "refresh_token": "kairos-refresh",
                        "token_type": "bearer",
                        "expires_in": 3600,
                        "refresh_expires_in": 7200,
                    },
                ),
            ),
        ):
            response = self.client.post("/auth/google/clerk/session", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["user"]["email"], "user@example.com")
        self.assertEqual(body["kairos_user"]["email"], "user@example.com")
        self.assertEqual(body["kairos_tokens"]["access_token"], "kairos-access")


@unittest.skipUnless(RUN_E2E_TESTS, "E2E tests disabled")
class GoogleAuthEndToEndTests(unittest.TestCase):
    def test_google_auth_health_and_login_redirect(self) -> None:
        health_status, health_body, _ = _request_json("GET", "/health")
        self.assertEqual(health_status, 200)
        self.assertEqual(health_body["status"], "ok")
        self.assertEqual(health_body["service"], "google_auth_service")

        root_status, root_body, _ = _request_json("GET", "/")
        self.assertEqual(root_status, 200)
        self.assertEqual(root_body["status"], "running")
        self.assertEqual(root_body["service"], "google_auth_service")

        connection = HTTPConnection("localhost", 8007, timeout=30)
        connection.request("GET", "/auth/google/login")
        response = connection.getresponse()
        self.assertEqual(response.status, 307)
        location = response.getheader("Location", "")
        response.read()
        connection.close()

        parsed_location = urlparse(location)
        query_params = parse_qs(parsed_location.query)

        self.assertEqual(parsed_location.scheme, "https")
        self.assertIn("accounts.google.com", parsed_location.netloc)
        self.assertEqual(query_params["client_id"][0], "ci-google-client-id")
        self.assertEqual(
            query_params["redirect_uri"][0],
            "http://localhost:8007/auth/google/callback",
        )
        self.assertIn("state", query_params)
        self.assertIn("nonce", query_params)
