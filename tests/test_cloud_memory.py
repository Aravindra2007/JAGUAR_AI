import unittest
from types import SimpleNamespace
from unittest.mock import patch

from jaguar_core import memory


class FakeQuery:
    def __init__(self, data=None, calls=None):
        self.data = data or []
        self.calls = calls if calls is not None else []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self
        return call

    def execute(self):
        return SimpleNamespace(data=self.data)


class FakeSupabase:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or []
        self.queries = []

    def table(self, name):
        self.calls.append(("table", name))
        query = FakeQuery(self.result, self.calls)
        self.queries.append(query)
        return query

    def rpc(self, name, params):
        self.calls.append(("rpc", name, params))
        query = FakeQuery(self.result, self.calls)
        self.queries.append(query)
        return query


class CloudMemoryTests(unittest.TestCase):
    def test_saving_memory_is_user_scoped_and_explicit(self):
        client = FakeSupabase()
        with patch("jaguar_core.memory.get_supabase_client", return_value=client):
            entry_id = memory.remember(
                "PlantAI uses TensorFlow",
                user_id="account-1",
                kind="project",
                metadata={"project": "PlantAI"},
            )

        self.assertTrue(entry_id)
        self.assertEqual(client.calls[0], ("table", "jaguar_memories"))
        row = client.calls[1][1][0]
        self.assertEqual(row["user_id"], "account-1")
        self.assertEqual(row["content"], "PlantAI uses TensorFlow")
        self.assertEqual(row["kind"], "project")

    def test_recall_uses_only_the_requested_owner(self):
        client = FakeSupabase([{
            "id": "mem-1",
            "kind": "project",
            "content": "PlantAI uses TensorFlow",
            "metadata": {"project": "PlantAI"},
            "importance": 0.9,
            "confidence": 1.0,
            "created_at": "2026-11-11T00:00:00+00:00",
            "score": 0.8,
        }])
        with patch("jaguar_core.memory.get_supabase_client", return_value=client):
            entries = memory.recall(
                "continue PlantAI",
                user_id="account-2",
                top_k=3,
            )

        self.assertEqual(entries[0].text, "PlantAI uses TensorFlow")
        self.assertEqual(client.calls[0][0:2], ("rpc", "search_jaguar_memories"))
        self.assertEqual(client.calls[0][2]["p_user_id"], "account-2")
        self.assertEqual(client.calls[0][2]["p_limit"], 3)

    def test_updates_and_deletes_are_owner_scoped(self):
        client = FakeSupabase([{"id": "mem-1"}])
        with patch("jaguar_core.memory.get_supabase_client", return_value=client):
            self.assertTrue(memory.update_memory(
                "mem-1",
                "Updated project context",
                user_id="account-1",
            ))
            self.assertTrue(memory.forget("mem-1", user_id="account-1"))

        filters = [call for call in client.calls if call[0] == "eq"]
        self.assertIn(("eq", ("user_id", "account-1"), {}), filters)
        self.assertEqual(
            sum(1 for call in client.calls if call[0] == "delete"),
            1,
        )

    def test_preferences_are_stored_remotely_per_user(self):
        client = FakeSupabase()
        with patch("jaguar_core.memory.get_supabase_client", return_value=client):
            prefs = memory.update_preference(
                "language",
                "Hindi",
                user_id="account-3",
            )

        self.assertEqual(prefs["language"], "Hindi")
        upsert = next(call for call in client.calls if call[0] == "upsert")
        self.assertEqual(upsert[1][0]["user_id"], "account-3")

    def test_cloud_memory_requires_an_authenticated_owner(self):
        with patch("jaguar_core.memory.get_supabase_client") as get_client:
            with self.assertRaises(memory.MemoryStoreError):
                memory.remember("A project fact")
            get_client.assert_not_called()

    def test_chat_memory_is_not_saved_without_explicit_action(self):
        self.assertFalse(hasattr(memory, "ingest_chat_turn"))


if __name__ == "__main__":
    unittest.main()
