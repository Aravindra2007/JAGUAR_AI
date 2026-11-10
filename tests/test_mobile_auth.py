import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.mobile_api import _authenticated_user, app


class MobileAuthenticationTests(unittest.TestCase):
    def test_mobile_memory_endpoint_fails_closed_without_a_token(self):
        response = TestClient(app).get("/memory")
        self.assertEqual(response.status_code, 401)

    def test_requires_bearer_token(self):
        with self.assertRaises(HTTPException) as raised:
            _authenticated_user(None)
        self.assertEqual(raised.exception.status_code, 401)

    def test_requires_verified_email(self):
        credentials = SimpleNamespace(scheme="Bearer", credentials="token")
        with (
            patch(
                "api.mobile_api.db.verify_firebase_id_token",
                return_value={"email": "user@example.com", "email_verified": False},
            ),
            patch("api.mobile_api.db.get_user_by_email") as lookup,
        ):
            with self.assertRaises(HTTPException) as raised:
                _authenticated_user(credentials)

        self.assertEqual(raised.exception.status_code, 403)
        lookup.assert_not_called()

    def test_maps_verified_firebase_email_to_jaguar_account(self):
        credentials = SimpleNamespace(scheme="Bearer", credentials="token")
        account = {"id": "jaguar-user-1", "email": "user@example.com"}
        with (
            patch(
                "api.mobile_api.db.verify_firebase_id_token",
                return_value={"email": "USER@example.com", "email_verified": True},
            ),
            patch(
                "api.mobile_api.db.get_user_by_email",
                return_value=account,
            ) as lookup,
        ):
            user = _authenticated_user(credentials)

        self.assertEqual(user["id"], "jaguar-user-1")
        lookup.assert_called_once_with("user@example.com")

    def test_rejects_firebase_user_without_linked_jaguar_account(self):
        credentials = SimpleNamespace(scheme="Bearer", credentials="token")
        with (
            patch(
                "api.mobile_api.db.verify_firebase_id_token",
                return_value={"email": "user@example.com", "email_verified": True},
            ),
            patch("api.mobile_api.db.get_user_by_email", return_value=None),
        ):
            with self.assertRaises(HTTPException) as raised:
                _authenticated_user(credentials)

        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
