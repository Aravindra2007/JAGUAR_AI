import unittest
from unittest.mock import patch

import db
import listener
import state

with (
    patch.object(db, "init_db"),
    patch.object(listener.VoiceListener, "start"),
):
    from app import app


class LLMConfigAccessTests(unittest.TestCase):
    def test_config_endpoints_require_login(self):
        client = app.test_client()

        self.assertIn(client.post("/set-llm-config", json={}).status_code, (301, 302))
        self.assertIn(client.get("/llm-config").status_code, (301, 302))

    def test_settings_are_user_scoped_and_api_key_is_not_returned(self):
        client = app.test_client()
        user = {
            "id": "llm-config-test-user",
            "username": "test-user",
            "email": "test@example.com",
        }

        with patch("auth.db.get_user_by_id", return_value=user):
            with client.session_transaction() as session:
                session["_user_id"] = user["id"]
                session["_fresh"] = True

            response = client.post(
                "/set-llm-config",
                json={
                    "provider": "OpenAI",
                    "model": "test-model",
                    "api_key": "user-secret",
                },
            )
            self.assertEqual(response.status_code, 200)

            response = client.get("/llm-config")
            self.assertEqual(response.status_code, 200)
            settings = response.get_json()

        self.assertNotIn("api_key", settings)
        self.assertTrue(settings["api_key_configured"])
        self.assertEqual(
            state.get_llm_config(user_id=user["id"])["api_key"],
            "user-secret",
        )
        self.assertNotEqual(
            state.get_llm_config(user_id="another-user")["api_key"],
            "user-secret",
        )

    def test_user_defaults_do_not_inherit_process_wide_credentials(self):
        original_config = state.get_llm_config()
        try:
            state.set_llm_config(api_key="process-wide-secret")
            state.set_llm_config(
                user_id="isolated-user",
                provider="OpenAI",
            )

            self.assertNotEqual(
                state.get_llm_config(user_id="isolated-user")["api_key"],
                "process-wide-secret",
            )
        finally:
            state.set_llm_config(**original_config)


if __name__ == "__main__":
    unittest.main()
