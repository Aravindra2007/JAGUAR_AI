import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from auth import init_auth


class RegistrationEmailTests(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=Path(__file__).resolve().parents[1] / "templates",
        )
        app.secret_key = "test-secret"
        init_auth(app)
        self.client = app.test_client()

    def _registration_form(self, email):
        return {
            "username": "jane",
            "full_name": "Jane Smith",
            "email": email,
            "password": "secure-password",
            "confirm_password": "secure-password",
        }

    def test_rejects_malformed_email_before_creating_account(self):
        with patch("auth.db.create_user") as create_user:
            response = self.client.post(
                "/register",
                data=self._registration_form("jane@@gmail.com"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Please enter a valid email address.", response.data)
        create_user.assert_not_called()

    def test_does_not_report_success_when_verification_email_cannot_send(self):
        user = {"id": "user-1"}
        with (
            patch("auth.db.create_user", return_value=user),
            patch("auth.db.save_otp"),
            patch("auth.email_utils.send_otp_email", return_value=False),
        ):
            response = self.client.post(
                "/register",
                data=self._registration_form("jane@gmail.com"),
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/verify")
        with self.client.session_transaction() as session:
            self.assertEqual(session["verify_user_id"], "user-1")
            messages = [message for _, message in session["_flashes"]]
        self.assertIn(
            "We couldn't send a verification code. "
            "Check the email address and try resending the code.",
            messages,
        )

    def test_reports_failed_resend(self):
        user = {"email": "jane@gmail.com"}
        with (
            patch("auth.db.get_user_by_id", return_value=user),
            patch("auth.db.save_otp"),
            patch("auth.email_utils.send_otp_email", return_value=False),
        ):
            with self.client.session_transaction() as session:
                session["verify_user_id"] = "user-1"
            response = self.client.post(
                "/verify",
                data={"action": "resend"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"We couldn&#39;t send a verification code.",
            response.data,
        )


if __name__ == "__main__":
    unittest.main()
