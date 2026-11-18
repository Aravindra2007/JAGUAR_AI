import os
import unittest
from unittest.mock import patch

from email_utils import send_otp_email


class SendOtpEmailTests(unittest.TestCase):
    def test_smtp_recipient_refusal_is_reported_as_failure(self):
        with (
            patch.dict(
                os.environ,
                {"MAIL_USERNAME": "sender@example.com", "MAIL_PASSWORD": "secret"},
            ),
            patch("email_utils.smtplib.SMTP") as smtp_class,
        ):
            server = smtp_class.return_value
            server.send_message.return_value = {
                "jane@gmail.com": (550, b"mailbox unavailable")
            }

            sent = send_otp_email("jane@gmail.com", "123456")

        self.assertFalse(sent)
        server.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
