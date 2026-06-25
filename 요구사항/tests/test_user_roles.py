import tempfile
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src import web_app


class UserRoleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_user_db_path = web_app.USER_DB_PATH
        self.original_user_approval_required = web_app.USER_APPROVAL_REQUIRED
        web_app.USER_DB_PATH = Path(self.tmp.name) / "users.sqlite3"
        web_app.USER_APPROVAL_REQUIRED = False

    def tearDown(self):
        web_app.USER_DB_PATH = self.original_user_db_path
        web_app.USER_APPROVAL_REQUIRED = self.original_user_approval_required
        self.tmp.cleanup()

    def test_viewer_role_can_be_assigned_and_blocks_document_writes(self):
        web_app.create_user_account("조회 사용자", "viewer01", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")
        authenticated = web_app.authenticate_user("viewer01", "secret1")

        self.assertEqual("viewer", authenticated["role"])
        self.assertFalse(web_app.can_write_documents(authenticated))

    def test_user_role_keeps_document_write_permission(self):
        web_app.create_user_account("일반 사용자", "user01", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")
        web_app.update_user_account_role(
            "user01",
            "user",
            {"employeeId": "1111120", "name": "관리자", "role": "user"},
        )
        authenticated = web_app.authenticate_user("user01", "secret1")

        self.assertEqual("user", authenticated["role"])
        self.assertTrue(web_app.can_write_documents(authenticated))

    def test_legacy_users_without_role_are_treated_as_editors(self):
        self.assertEqual("user", web_app.normalize_user_role(None))
        self.assertTrue(web_app.can_write_documents({"employeeId": "legacy01", "name": "기존 사용자"}))

    def test_manager_keeps_write_permission_even_if_role_is_viewer(self):
        manager = {"employeeId": "1111120", "name": "관리자", "role": "viewer"}

        self.assertTrue(web_app.can_manage_users(manager))
        self.assertTrue(web_app.can_write_documents(manager))

    def test_policy_generation_admin_actions_are_detected(self):
        self.assertTrue(web_app.policy_generation_admin_action_required({"rewriteExisting": True, "templateType": "simple"}))
        self.assertTrue(web_app.policy_generation_admin_action_required({"templateType": "full"}))
        self.assertTrue(web_app.policy_generation_admin_action_required({"fullFromSimple": True, "templateType": "full"}))
        self.assertFalse(web_app.policy_generation_admin_action_required({"templateType": "simple"}))

    def test_authenticated_non_manager_cannot_start_rewrite_or_full_generation(self):
        user = {"employeeId": "user01", "name": "일반 사용자", "role": "user"}

        with self.assertRaisesRegex(PermissionError, "다시 작성"):
            web_app.start_policy_job(
                {
                    "topic": "AI검색",
                    "templateType": "simple",
                    "reviewMode": "auto",
                    "inspectionMode": "none",
                    "writerMode": "mock",
                    "rewriteExisting": True,
                    "authenticatedUser": user,
                }
            )
        with self.assertRaisesRegex(PermissionError, "Full 버전"):
            web_app.start_policy_job(
                {
                    "topic": "AI검색",
                    "templateType": "full",
                    "reviewMode": "auto",
                    "inspectionMode": "none",
                    "writerMode": "mock",
                    "authenticatedUser": user,
                }
            )

    def test_role_update_cannot_change_self_or_manager_account(self):
        web_app.create_user_account("관리 대상", "role01", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")

        with self.assertRaises(PermissionError):
            web_app.update_user_account_role(
                "role01",
                "viewer",
                {"employeeId": "role01", "name": "관리 대상", "role": "user"},
            )
        with self.assertRaises(PermissionError):
            web_app.update_user_account_role(
                "1111120",
                "viewer",
                {"employeeId": "admin01", "name": "관리자", "role": "user"},
            )


if __name__ == "__main__":
    unittest.main()
