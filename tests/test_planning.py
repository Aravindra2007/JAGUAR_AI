import os
import tempfile
import unittest
from unittest.mock import patch

from plan_executor import PlanValidationError, execute_plan, resume_plan, validate_plan
from router import CommandRouter
import task_state
from tool_executor import ToolExecutor


class PlanValidationTests(unittest.TestCase):
    def test_rejects_unknown_dependencies(self):
        with self.assertRaisesRegex(PlanValidationError, "unknown step"):
            validate_plan({
                "goal": "invalid",
                "steps": [{
                    "id": "step_1",
                    "tool": "list_directory",
                    "input": {"path": "."},
                    "depends_on": ["missing"],
                }],
            })

    def test_rejects_cycles(self):
        with self.assertRaisesRegex(PlanValidationError, "cycle"):
            validate_plan({
                "goal": "invalid",
                "steps": [
                    {
                        "id": "step_1",
                        "tool": "list_directory",
                        "input": {"path": "."},
                        "depends_on": ["step_2"],
                    },
                    {
                        "id": "step_2",
                        "tool": "list_directory",
                        "input": {"path": "."},
                        "depends_on": ["step_1"],
                    },
                ],
            })

    def test_rejects_unknown_tools(self):
        with self.assertRaisesRegex(PlanValidationError, "not allowed"):
            validate_plan({
                "goal": "invalid",
                "steps": [{
                    "id": "step_1",
                    "tool": "execute_python",
                    "input": {},
                    "depends_on": [],
                }],
            })

    def test_rejects_invalid_tool_arguments_before_execution(self):
        with self.assertRaisesRegex(PlanValidationError, "Missing required"):
            validate_plan({
                "goal": "invalid",
                "steps": [{
                    "id": "step_1",
                    "tool": "write_file",
                    "input": {"path": "main.py"},
                    "depends_on": [],
                }],
            })

    def test_planner_parses_json_responses(self):
        from planner import parse_plan

        self.assertEqual(
            parse_plan('```json\n{"goal":"chat","steps":[],"response":"Hello"}\n```'),
            {"goal": "chat", "steps": [], "response": "Hello"},
        )

    def test_planner_reviews_observations_for_remaining_work(self):
        from planner import review_results

        with patch(
            "planner.ask",
            return_value='{"complete":false,"response":"One step remains.","steps":[]}',
        ) as ask:
            review = review_results(
                "OpenAI",
                [{"role": "user", "content": "Finish the task"}],
                {"goal": "Finish the task", "steps": []},
                "A step failed.",
            )

        self.assertFalse(review["complete"])
        self.assertIn("Execution results", ask.call_args.args[1][-1]["content"])

    def test_planner_rejects_missing_step_ids(self):
        with self.assertRaisesRegex(PlanValidationError, "exactly id"):
            validate_plan({
                "goal": "invalid",
                "steps": [{
                    "tool": "list_directory",
                    "input": {"path": "."},
                    "depends_on": [],
                }],
            })


class PlanExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.executor = ToolExecutor(workspace_dir=self.temp_dir.name)

    def test_pauses_and_resumes_for_each_confirmation(self):
        result = execute_plan({
            "goal": "Create a folder and Python file",
            "response": "",
            "steps": [
                {
                    "id": "folder",
                    "tool": "create_folder",
                    "input": {"path": "AI_Project"},
                    "depends_on": [],
                },
                {
                    "id": "file",
                    "tool": "write_file",
                    "input": {
                        "path": "AI_Project/main.py",
                        "content": "print('hello')\n",
                    },
                    "depends_on": ["folder"],
                },
            ],
        }, self.executor, continuation={"provider": "OpenAI", "messages": []})

        self.assertEqual(result["kind"], "confirmation")
        self.assertIn("Create folder", result["envelope"]["prompt"])
        first_pending = task_state.peek_pending_plan(result["envelope"]["token"])
        self.assertIsNotNone(first_pending)
        task_id = first_pending["task_id"]
        self.assertEqual(first_pending["completed_steps"], [])

        result = resume_plan(result["envelope"]["token"], "yes", self.executor)
        self.assertEqual(result["kind"], "confirmation")
        self.assertIn("Write", result["envelope"]["prompt"])
        second_pending = task_state.peek_pending_plan(result["envelope"]["token"])
        self.assertIsNotNone(second_pending)
        self.assertEqual(second_pending["task_id"], task_id)
        self.assertEqual(second_pending["completed_steps"], ["folder"])
        self.assertEqual(len(second_pending["observations"]), 1)

        result = resume_plan(result["envelope"]["token"], "yes", self.executor)
        self.assertTrue(result["success"])
        self.assertEqual(result["continuation"]["provider"], "OpenAI")
        self.assertTrue(os.path.isdir(os.path.join(self.temp_dir.name, "AI_Project")))
        with open(
            os.path.join(self.temp_dir.name, "AI_Project", "main.py"),
            encoding="utf-8",
        ) as file:
            self.assertEqual(file.read(), "print('hello')\n")
        self.assertEqual(
            [step["status"] for step in result["plan"]["steps"]],
            ["completed", "completed"],
        )

    def test_approved_document_directory_skips_related_file_confirmations(self):
        documents = os.path.join(self.temp_dir.name, "documents")
        os.mkdir(documents)
        executor = ToolExecutor(
            workspace_dir=self.temp_dir.name,
            user_id="document-owner",
        )
        result = execute_plan({
            "goal": "Create two related document files",
            "steps": [
                {
                    "id": "first",
                    "tool": "write_file",
                    "input": {"path": "documents/first.txt", "content": "first"},
                    "depends_on": [],
                },
                {
                    "id": "second",
                    "tool": "write_file",
                    "input": {"path": "documents/second.txt", "content": "second"},
                    "depends_on": [],
                },
            ],
        }, executor, continuation={"user_id": "document-owner"})

        self.assertEqual(result["kind"], "confirmation")
        self.assertIn("without asking again until Jaguar restarts", result["envelope"]["prompt"])

        result = resume_plan(result["envelope"]["token"], "yes", executor)

        self.assertEqual(result["kind"], "result")
        self.assertTrue(result["success"])
        self.assertTrue(os.path.isfile(os.path.join(documents, "first.txt")))
        self.assertTrue(os.path.isfile(os.path.join(documents, "second.txt")))

    def test_document_approval_does_not_cover_other_directories_or_users(self):
        documents = os.path.join(self.temp_dir.name, "documents")
        other_directory = os.path.join(self.temp_dir.name, "other")
        os.mkdir(documents)
        os.mkdir(other_directory)
        owner_executor = ToolExecutor(
            workspace_dir=self.temp_dir.name,
            user_id="document-owner",
        )
        result = owner_executor.execute(
            "write_file",
            {"path": "documents/approved.txt", "content": "approved"},
        )
        approved = owner_executor.execute_confirmed_result(result["token"], "yes")
        self.assertTrue(approved["success"])

        different_directory = owner_executor.execute(
            "write_file",
            {"path": "other/unapproved.txt", "content": "not approved"},
        )
        different_user = ToolExecutor(
            workspace_dir=self.temp_dir.name,
            user_id="another-user",
        ).execute(
            "write_file",
            {"path": "documents/other-user.txt", "content": "not approved"},
        )
        existing_file = owner_executor.execute(
            "write_file",
            {"path": "documents/approved.txt", "content": "overwrite"},
        )
        other_action = owner_executor.execute(
            "create_folder",
            {"path": "documents/new-folder"},
        )

        self.assertEqual(different_directory["kind"], "confirmation")
        self.assertEqual(different_user["kind"], "confirmation")
        self.assertEqual(existing_file["kind"], "result")
        self.assertFalse(existing_file["success"])
        self.assertEqual(other_action["kind"], "confirmation")
        with open(os.path.join(documents, "approved.txt"), encoding="utf-8") as file:
            self.assertEqual(file.read(), "approved")

    def test_pending_plan_can_only_be_resumed_by_its_owner(self):
        owner_executor = ToolExecutor(
            workspace_dir=self.temp_dir.name,
            user_id="account-1",
        )
        other_executor = ToolExecutor(
            workspace_dir=self.temp_dir.name,
            user_id="account-2",
        )
        result = execute_plan({
            "goal": "Create a folder",
            "steps": [{
                "id": "folder",
                "tool": "create_folder",
                "input": {"path": "Owned"},
                "depends_on": [],
            }],
        }, owner_executor, continuation={"user_id": "account-1"})
        token = result["envelope"]["token"]

        rejected = resume_plan(token, "yes", other_executor)
        self.assertFalse(rejected["success"])
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir.name, "Owned")))

        resumed = resume_plan(token, "yes", owner_executor)
        self.assertTrue(resumed["success"])
        self.assertTrue(os.path.isdir(os.path.join(self.temp_dir.name, "Owned")))

    def test_existing_folder_is_satisfied_and_plan_continues(self):
        os.mkdir(os.path.join(self.temp_dir.name, "AI_Project"))

        result = execute_plan({
            "goal": "Ensure folder exists and add a Python file",
            "steps": [
                {
                    "id": "folder",
                    "tool": "create_folder",
                    "input": {"path": "AI_Project"},
                    "depends_on": [],
                },
                {
                    "id": "file",
                    "tool": "write_file",
                    "input": {"path": "AI_Project/main.py", "content": "print('ready')"},
                    "depends_on": ["folder"],
                },
            ],
        }, self.executor)

        self.assertEqual(result["kind"], "confirmation")
        self.assertEqual(result["envelope"]["tool_name"], "write_file")

    def test_open_folder_is_confined_and_requires_approval(self):
        os.mkdir(os.path.join(self.temp_dir.name, "AI_Project"))

        result = self.executor.execute("open_folder", {"path": "AI_Project"})
        outside = self.executor.execute("open_folder", {"path": ".."})

        self.assertEqual(result["kind"], "confirmation")
        self.assertEqual(result["tool_name"], "open_folder")
        self.assertEqual(outside["kind"], "result")
        self.assertFalse(outside["success"])

    def test_failure_blocks_dependents_but_runs_independent_steps(self):
        result = execute_plan({
            "goal": "Read a missing file and inspect the workspace",
            "steps": [
                {
                    "id": "read",
                    "tool": "read_file",
                    "input": {"path": "missing.txt"},
                    "depends_on": [],
                },
                {
                    "id": "write",
                    "tool": "write_file",
                    "input": {"path": "dependent.txt", "content": "not written"},
                    "depends_on": ["read"],
                },
                {
                    "id": "list",
                    "tool": "list_directory",
                    "input": {"path": "."},
                    "depends_on": [],
                },
            ],
        }, self.executor)

        self.assertFalse(result["success"])
        self.assertEqual(
            [step["status"] for step in result["plan"]["steps"]],
            ["failed", "blocked", "completed"],
        )
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir.name, "dependent.txt")))

    def test_unverified_step_blocks_dependent_steps(self):
        plan = {
            "goal": "Open a folder and then use it",
            "steps": [
                {
                    "id": "open",
                    "tool": "open_folder",
                    "input": {"path": "."},
                    "depends_on": [],
                },
                {
                    "id": "dependent",
                    "tool": "list_directory",
                    "input": {"path": "."},
                    "depends_on": ["open"],
                },
            ],
        }
        with patch.object(
            self.executor,
            "execute",
            side_effect=[
                {
                    "kind": "result",
                    "text": "Could not verify UI launch.",
                    "success": False,
                    "observation": {
                        "status": "unverified",
                        "verified": False,
                        "failure_type": "unrecoverable",
                        "message": "Could not verify UI launch.",
                    },
                },
                AssertionError("dependent step must not execute"),
            ],
        ):
            result = execute_plan(plan, self.executor)

        self.assertEqual(
            [step["status"] for step in result["plan"]["steps"]],
            ["unverified", "blocked"],
        )

    def test_denial_blocks_dependent_steps(self):
        result = execute_plan({
            "goal": "Create folder and file",
            "steps": [
                {
                    "id": "folder",
                    "tool": "create_folder",
                    "input": {"path": "Project"},
                    "depends_on": [],
                },
                {
                    "id": "file",
                    "tool": "write_file",
                    "input": {"path": "Project/main.py", "content": ""},
                    "depends_on": ["folder"],
                },
                {
                    "id": "list",
                    "tool": "list_directory",
                    "input": {"path": "."},
                    "depends_on": [],
                },
            ],
        }, self.executor)

        result = resume_plan(result["envelope"]["token"], "no", self.executor)

        self.assertFalse(result["success"])
        self.assertEqual(
            [step["status"] for step in result["plan"]["steps"]],
            ["failed", "blocked", "completed"],
        )
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir.name, "Project")))


class PlannerRoutingIntegrationTests(unittest.TestCase):
    def test_claude_and_other_providers_use_the_same_plan_path(self):
        router = object.__new__(CommandRouter)
        config = {
            "enabled": True,
            "provider": "Claude (Anthropic)",
            "api_key": "test-key",
            "model": "test-model",
            "temperature": 0.2,
            "system_prompt": "",
            "ollama_host": "",
            "tools_enabled": True,
            "workspace_dir": tempfile.gettempdir(),
        }
        with (
            patch("router.state.get_llm_config", return_value=config),
            patch("router.state.get_language", return_value="English"),
            patch("router.state.get_history", return_value=[]),
            patch("router.state.get_and_clear_pending_attachment", return_value=None),
            patch("router.state.set_text"),
            patch("router.agents.pick_agent", return_value="general"),
            patch("router.agents.system_prompt_for", return_value="system"),
            patch(
                "router.create_plan",
                return_value={"goal": "greeting", "steps": [], "response": "Hello."},
            ) as create_plan,
        ):
            result = router._ask_llm("Hello")

        self.assertEqual(result, "Hello.")
        self.assertEqual(create_plan.call_args.kwargs["provider"], "Claude (Anthropic)")

    def test_result_review_can_propose_a_bounded_follow_up_plan(self):
        router = object.__new__(CommandRouter)
        with tempfile.TemporaryDirectory() as workspace:
            os.mkdir(os.path.join(workspace, "Project"))
            execution = {
                "success": True,
                "text": "The first part is complete.",
                "plan": {
                    "goal": "Create and open a project",
                    "steps": [{
                        "id": "create",
                        "tool": "create_folder",
                        "input": {"path": "Project"},
                        "depends_on": [],
                        "status": "completed",
                        "result": "Created Project.",
                    }],
                },
            }
            continuation = {"provider": "OpenAI", "messages": []}
            config = {"workspace_dir": workspace}
            with patch(
                "router.review_results",
                return_value={
                    "complete": False,
                    "response": "The folder still needs to be opened.",
                    "steps": [{
                        "id": "open",
                        "tool": "open_folder",
                        "input": {"path": "Project"},
                        "depends_on": [],
                    }],
                },
            ):
                result = router._review_plan_results(execution, continuation, config)

        self.assertEqual(result["type"], "needs_confirmation")
        self.assertEqual(result["envelope"]["tool_name"], "open_folder")

    def test_review_does_not_retry_a_previously_attempted_action(self):
        router = object.__new__(CommandRouter)
        action = {"path": "Project"}
        signature = router._action_signature("create_folder", action)
        execution = {
            "success": False,
            "text": "A recoverable problem occurred.",
            "plan": {
                "goal": "Create a folder.",
                "steps": [{
                    "id": "create",
                    "tool": "create_folder",
                    "input": action,
                    "depends_on": [],
                    "status": "failed",
                    "result": "Failed.",
                    "observation": {
                        "status": "failed",
                        "verified": False,
                        "failure_type": "recoverable",
                        "message": "Failed.",
                    },
                }],
            },
        }
        continuation = {
            "provider": "OpenAI",
            "messages": [],
            "replan_count": 0,
            "attempted_actions": [signature],
        }
        with patch(
            "router.review_results",
            return_value={
                "complete": False,
                "response": "Retry it.",
                "steps": [{
                    "id": "retry",
                    "tool": "create_folder",
                    "input": action,
                    "depends_on": [],
                }],
            },
        ):
            result = router._review_plan_results(execution, continuation, {})

        self.assertIn("repeating an action", result)

    def test_permission_failure_does_not_trigger_replanning(self):
        router = object.__new__(CommandRouter)
        execution = {
            "success": False,
            "text": "Permission denied.",
            "plan": {
                "goal": "Write file.",
                "steps": [{
                    "id": "write",
                    "tool": "write_file",
                    "input": {"path": "restricted.txt", "content": "x"},
                    "depends_on": [],
                    "status": "failed",
                    "result": "Permission denied.",
                    "observation": {
                        "status": "failed",
                        "verified": False,
                        "failure_type": "unrecoverable",
                        "message": "Permission denied.",
                    },
                }],
            },
        }
        with patch("router.review_results") as review:
            result = router._review_plan_results(
                execution,
                {"provider": "OpenAI", "messages": []},
                {},
            )

        review.assert_not_called()
        self.assertIn("No automatic retry", result)


if __name__ == "__main__":
    unittest.main()
