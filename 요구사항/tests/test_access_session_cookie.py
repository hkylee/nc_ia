from src import web_app


def test_access_login_cookie_is_session_scoped():
    token = web_app.create_user_session_token({"employeeId": "10001", "name": "테스터"})
    header = web_app.session_cookie_header(web_app.ACCESS_COOKIE_NAME, token)

    assert f"{web_app.ACCESS_COOKIE_NAME}={token}" in header
    assert "HttpOnly" in header
    assert "SameSite=Lax" in header
    assert "Max-Age" not in header
    assert "Expires" not in header


def test_llm_access_uses_request_token_without_cookie_state():
    web_app.validate_llm_access_from_payload(
        {"llmAccessToken": web_app.LLM_ACCESS_TOKEN_VALUE},
        "llm",
    )


def test_site_writer_mode_persists_without_storing_llm_token(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "SITE_SETTINGS_PATH", tmp_path / "site_settings.json")

    settings = web_app.save_site_writer_mode("llm", {"employeeId": "1111120", "name": "관리자"})
    raw = (tmp_path / "site_settings.json").read_text(encoding="utf-8")

    assert settings["writerMode"] == "llm"
    assert web_app.load_site_settings()["writerMode"] == "llm"
    assert web_app.LLM_ACCESS_TOKEN_VALUE not in raw
    assert "llmAccessToken" not in raw


def test_site_writer_mode_default_stays_mock_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "SITE_SETTINGS_PATH", tmp_path / "site_settings.json")
    monkeypatch.setattr(web_app, "RUNTIME_REPORTS_ROOT", tmp_path / "reports")

    assert web_app.load_site_settings()["writerMode"] == "mock"
    assert web_app.public_site_settings_status()["writerMode"] == "mock"
    assert web_app.public_site_settings_status()["persisted"] is False


def test_site_settings_path_prefers_persistent_runtime_root(tmp_path, monkeypatch):
    persistent_root = tmp_path / "persistent"
    monkeypatch.delenv("NC_SITE_SETTINGS_PATH", raising=False)
    monkeypatch.delenv("NC_REPORTS_DIR", raising=False)
    monkeypatch.setenv("NC_PERSISTENT_ROOT", str(persistent_root))

    assert web_app.resolve_site_settings_path() == persistent_root / "reports" / "site_settings.json"


def test_site_settings_path_reports_dir_wins_over_persistent_root(tmp_path, monkeypatch):
    reports_root = tmp_path / "runtime_reports"
    persistent_root = tmp_path / "persistent"
    monkeypatch.delenv("NC_SITE_SETTINGS_PATH", raising=False)
    monkeypatch.setenv("NC_REPORTS_DIR", str(reports_root))
    monkeypatch.setenv("NC_PERSISTENT_ROOT", str(persistent_root))
    monkeypatch.setattr(web_app, "RUNTIME_REPORTS_ROOT", reports_root)

    assert web_app.resolve_site_settings_path() == reports_root / "site_settings.json"


def test_site_settings_env_override_wins(tmp_path, monkeypatch):
    explicit_path = tmp_path / "custom" / "site_settings.json"
    monkeypatch.setenv("NC_SITE_SETTINGS_PATH", str(explicit_path))
    monkeypatch.setenv("NC_REPORTS_DIR", str(tmp_path / "runtime_reports"))
    monkeypatch.setenv("NC_PERSISTENT_ROOT", str(tmp_path / "persistent"))

    assert web_app.resolve_site_settings_path() == explicit_path


def test_site_settings_loads_and_migrates_legacy_reports_file(tmp_path, monkeypatch):
    new_path = tmp_path / "persistent" / "reports" / "site_settings.json"
    legacy_reports = tmp_path / "legacy_reports"
    legacy_reports.mkdir()
    legacy_path = legacy_reports / "site_settings.json"
    legacy_path.write_text('{"writerMode":"llm","updatedBy":"관리자"}\n', encoding="utf-8")
    monkeypatch.setattr(web_app, "SITE_SETTINGS_PATH", new_path)
    monkeypatch.setattr(web_app, "RUNTIME_REPORTS_ROOT", legacy_reports)

    settings = web_app.load_site_settings()

    assert settings["writerMode"] == "llm"
    assert new_path.exists()


def test_public_site_settings_status_excludes_user_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "SITE_SETTINGS_PATH", tmp_path / "site_settings.json")
    web_app.save_site_writer_mode("llm", {"employeeId": "1111120", "name": "관리자"})

    status = web_app.public_site_settings_status()

    assert status["writerMode"] == "llm"
    assert status["persisted"] is True
    assert "updatedBy" not in status
    assert "updatedByEmployeeIdHash" not in status


def test_public_site_settings_status_marks_admin_update_permission(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "SITE_SETTINGS_PATH", tmp_path / "site_settings.json")
    admin = {"employeeId": "1111120", "name": "관리자", "role": "viewer"}
    user = {"employeeId": "10001", "name": "일반 사용자", "role": "user"}

    assert web_app.public_site_settings_status(admin)["canUpdate"] is True
    assert web_app.public_site_settings_status(user)["canUpdate"] is False
    assert web_app.public_site_settings_status(None)["canUpdate"] is False


def test_site_writer_mode_update_permission_is_admin_only():
    assert web_app.can_update_site_writer_mode({"employeeId": "1111120", "name": "관리자"}) is True
    assert web_app.can_update_site_writer_mode({"employeeId": "10001", "name": "일반 사용자"}) is False
    assert web_app.can_update_site_writer_mode(None) is False


def test_site_writer_mode_can_authorize_shared_llm_requests(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "SITE_SETTINGS_PATH", tmp_path / "site_settings.json")
    web_app.save_site_writer_mode("llm", {"employeeId": "1111120", "name": "관리자"})

    web_app.validate_llm_access_from_payload(
        {"writerMode": "llm", "useSiteWriterMode": True},
        "llm",
    )


def test_site_writer_mode_does_not_bypass_access_without_explicit_payload_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "SITE_SETTINGS_PATH", tmp_path / "site_settings.json")
    web_app.save_site_writer_mode("llm", {"employeeId": "1111120", "name": "관리자"})

    try:
        web_app.validate_llm_access_from_payload({"writerMode": "llm"}, "llm")
    except ValueError as exc:
        assert "LLM 사용 권한" in str(exc)
    else:  # pragma: no cover - the assertion above is the expected path.
        raise AssertionError("LLM access should require a token or explicit shared-mode flag.")


def test_clear_cookie_explicitly_expires_cookie():
    header = web_app.clear_cookie_header(web_app.ACCESS_COOKIE_NAME)

    assert f"{web_app.ACCESS_COOKIE_NAME}=" in header
    assert "Max-Age=0" in header


def test_user_session_token_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.json")
    user = web_app.create_user_account("테스터", "10001", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")
    token = web_app.create_user_session_token(user)

    assert web_app.user_from_session_token(token) == user


def test_user_db_uses_sqlite_and_persists_accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.sqlite3")

    web_app.create_user_account("테스터", "10001", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")
    db = web_app.load_user_db()

    assert (tmp_path / "users.sqlite3").exists()
    assert web_app.find_user_record(db, "10001")["name"] == "테스터"
    assert web_app.authenticate_user("10001", "secret1")["name"] == "테스터"


def test_user_db_default_prefers_persistent_runtime_root(tmp_path, monkeypatch):
    persistent_root = tmp_path / "persistent"
    persistent_root.mkdir()
    monkeypatch.delenv("NC_USER_DB_PATH", raising=False)
    monkeypatch.setenv("NC_PERSISTENT_ROOT", str(persistent_root))

    assert web_app.resolve_user_db_path() == persistent_root / "reports" / "auth" / "users.sqlite3"


def test_user_db_env_override_wins_over_persistent_runtime_root(tmp_path, monkeypatch):
    persistent_root = tmp_path / "persistent"
    persistent_root.mkdir()
    explicit_path = tmp_path / "custom" / "users.sqlite3"
    monkeypatch.setenv("NC_PERSISTENT_ROOT", str(persistent_root))
    monkeypatch.setenv("NC_USER_DB_PATH", str(explicit_path))

    assert web_app.resolve_user_db_path() == explicit_path


def test_runtime_cleanup_never_targets_auth_user_database():
    assert web_app.runtime_cleanup_target(web_app.Path("reports/auth/users.sqlite3")) is None
    assert web_app.runtime_cleanup_target(web_app.Path("reports/inspections/auth/users.sqlite3")) is None
    assert web_app.runtime_cleanup_target(web_app.Path("reports/auth/users.json")) is None


def test_user_login_updates_last_login_at(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.sqlite3")
    web_app.create_user_account("테스터", "10001", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")
    db = web_app.load_user_db()
    user = web_app.find_user_record(db, "10001")
    user["lastLoginAt"] = ""
    web_app.save_user_db(db)

    web_app.authenticate_user("10001", "secret1")

    updated_user = web_app.find_user_record(web_app.load_user_db(), "10001")
    assert updated_user["lastLoginAt"]


def test_user_sqlite_db_migrates_last_login_column(tmp_path, monkeypatch):
    db_path = tmp_path / "users.sqlite3"
    monkeypatch.setattr(web_app, "USER_DB_PATH", db_path)
    now = "2026-05-11T09:00:00"
    password_payload = web_app.hash_user_password("secret1")
    with web_app.sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                employee_id TEXT PRIMARY KEY COLLATE NOCASE,
                name TEXT NOT NULL,
                salt TEXT NOT NULL,
                iterations INTEGER NOT NULL,
                password_hash TEXT NOT NULL,
                approved INTEGER NOT NULL DEFAULT 1,
                role TEXT NOT NULL DEFAULT 'user',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO users (
                employee_id, name, salt, iterations, password_hash,
                approved, role, active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "10001",
                "기존사용자",
                password_payload["salt"],
                password_payload["iterations"],
                password_payload["passwordHash"],
                1,
                "user",
                1,
                now,
                now,
            ),
        )
        conn.commit()

    db = web_app.load_user_db()

    assert web_app.find_user_record(db, "10001")["lastLoginAt"] == ""
    with web_app.sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert "last_login_at" in columns


def test_user_management_dashboard_never_exposes_password_material(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.sqlite3")

    web_app.create_user_account("이용자", "10001", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")
    web_app.create_user_account("승인대기", "10002", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")
    db = web_app.load_user_db()
    pending = web_app.find_user_record(db, "10002")
    pending["approved"] = False
    pending["active"] = False
    web_app.save_user_db(db)

    dashboard = web_app.build_user_management_dashboard()

    assert dashboard["summary"]["totalUsers"] == 2
    assert dashboard["summary"]["approvedUsers"] == 1
    assert dashboard["summary"]["pendingUsers"] == 1
    assert dashboard["summary"]["inactiveUsers"] == 1
    assert {user["employeeId"] for user in dashboard["items"]} == {"10001", "10002"}
    for user in dashboard["items"]:
        assert "lastLoginAt" in user
        assert "passwordHash" not in user
        assert "salt" not in user
        assert "iterations" not in user


def test_user_management_is_limited_to_configured_employee_id(monkeypatch):
    monkeypatch.setattr(web_app, "USER_MANAGEMENT_EMPLOYEE_IDS", {"1111120"})

    assert web_app.can_manage_users({"employeeId": "1111120", "name": "관리자"}) is True
    assert web_app.can_manage_users({"employeeId": "10001", "name": "일반사용자"}) is False
    assert web_app.can_manage_users(None) is False


def test_withdraw_user_account_deactivates_login(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.sqlite3")
    monkeypatch.setattr(web_app, "USER_MANAGEMENT_EMPLOYEE_IDS", {"1111120"})
    admin = web_app.create_user_account("관리자", "1111120", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")
    web_app.create_user_account("일반사용자", "10001", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")

    withdrawn = web_app.withdraw_user_account("10001", admin)

    assert withdrawn["employeeId"] == "10001"
    assert withdrawn["active"] is False
    user = web_app.find_user_record(web_app.load_user_db(), "10001")
    assert user["active"] is False
    assert user["approved"] is False
    try:
        web_app.authenticate_user("10001", "secret1")
    except PermissionError as exc:
        assert "비활성화" in str(exc)
    else:  # pragma: no cover - defensive assertion.
        raise AssertionError("withdrawn users should not be able to login")


def test_withdraw_user_account_protects_self_and_managers(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.sqlite3")
    monkeypatch.setattr(web_app, "USER_MANAGEMENT_EMPLOYEE_IDS", {"1111120", "2222222"})
    admin = web_app.create_user_account("관리자", "1111120", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")
    web_app.create_user_account("다른관리자", "2222222", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")

    try:
        web_app.withdraw_user_account("1111120", admin)
    except PermissionError as exc:
        assert "본인 계정" in str(exc)
    else:  # pragma: no cover - defensive assertion.
        raise AssertionError("admin should not withdraw self")

    try:
        web_app.withdraw_user_account("2222222", admin)
    except PermissionError as exc:
        assert "관리자 계정" in str(exc)
    else:  # pragma: no cover - defensive assertion.
        raise AssertionError("manager accounts should be protected")


def test_user_db_migrates_legacy_json_to_sqlite(tmp_path, monkeypatch):
    now = "2026-05-11T09:00:00"
    password_payload = web_app.hash_user_password("secret1")
    legacy_payload = {
        "version": 1,
        "users": [
            {
                "employeeId": "10001",
                "name": "기존사용자",
                **password_payload,
                "approved": True,
                "role": "user",
                "active": True,
                "createdAt": now,
                "updatedAt": now,
            }
        ],
    }
    (tmp_path / "users.json").write_text(
        web_app.json.dumps(legacy_payload, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.sqlite3")

    assert web_app.authenticate_user("10001", "secret1")["name"] == "기존사용자"
    assert web_app.find_user_record(web_app.load_user_db(), "10001")["employeeId"] == "10001"


def test_signup_requires_entry_code(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.json")

    try:
        web_app.create_user_account("테스터", "10001", "secret1", "bad-code", "secret1")
    except PermissionError as exc:
        assert "입장 코드" in str(exc)
    else:  # pragma: no cover - defensive assertion.
        raise AssertionError("invalid entry code should be rejected")


def test_signup_requires_password_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.json")

    try:
        web_app.create_user_account("테스터", "10001", "secret1", web_app.ACCESS_ENTRY_CODE)
    except ValueError as exc:
        assert "비밀번호 확인" in str(exc)
    else:  # pragma: no cover - defensive assertion.
        raise AssertionError("missing password confirmation should be rejected")


def test_login_unknown_user_shows_signup_guidance(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.json")

    try:
        web_app.authenticate_user("unknown1", "secret1")
    except PermissionError as exc:
        assert str(exc) == "사번 또는 비밀번호를 확인해 주세요. 회원 가입 후 이용 가능합니다."
    else:  # pragma: no cover - defensive assertion.
        raise AssertionError("unknown users should see signup guidance")


def test_password_reset_uses_entry_code_and_preserves_user(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.sqlite3")
    web_app.create_user_account("관리자", "1111120", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")

    user = web_app.reset_user_password("1111120", "secret2", "secret2", web_app.ACCESS_ENTRY_CODE)

    assert user["employeeId"] == "1111120"
    assert user["name"] == "관리자"
    assert web_app.authenticate_user("1111120", "secret2")["name"] == "관리자"
    try:
        web_app.authenticate_user("1111120", "secret1")
    except PermissionError:
        pass
    else:  # pragma: no cover - defensive assertion.
        raise AssertionError("old password should not remain valid after reset")


def test_password_reset_requires_existing_user_and_entry_code(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.sqlite3")

    try:
        web_app.reset_user_password("1111120", "secret2", "secret2", web_app.ACCESS_ENTRY_CODE)
    except ValueError as exc:
        assert "가입된 사번" in str(exc)
    else:  # pragma: no cover - defensive assertion.
        raise AssertionError("password reset should require an existing account")

    web_app.create_user_account("관리자", "1111120", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")
    try:
        web_app.reset_user_password("1111120", "secret2", "secret2", "bad-code")
    except PermissionError as exc:
        assert "입장 코드" in str(exc)
    else:  # pragma: no cover - defensive assertion.
        raise AssertionError("password reset should require the entry code")


def test_signup_rejects_password_confirmation_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.json")

    try:
        web_app.create_user_account("테스터", "10001", "secret1", web_app.ACCESS_ENTRY_CODE, "secret2")
    except ValueError as exc:
        assert "비밀번호 확인" in str(exc)
    else:  # pragma: no cover - defensive assertion.
        raise AssertionError("password confirmation mismatch should be rejected")


def test_signup_can_create_approval_pending_user(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.json")
    monkeypatch.setattr(web_app, "USER_APPROVAL_REQUIRED", True)

    user = web_app.create_user_account("승인대기", "10002", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")

    assert user["approved"] is False
    try:
        web_app.authenticate_user("10002", "secret1")
    except PermissionError as exc:
        assert "승인" in str(exc)
    else:  # pragma: no cover - defensive assertion.
        raise AssertionError("approval-pending users should not be able to login")


def test_authenticated_user_overrides_author_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "USER_DB_PATH", tmp_path / "users.json")
    user = web_app.create_user_account("홍길동", "A1001", "secret1", web_app.ACCESS_ENTRY_CODE, "secret1")

    handler = web_app.PolicyWebHandler.__new__(web_app.PolicyWebHandler)
    handler.current_user = lambda: user
    payload = {"author": "사용자 입력값", "updatedBy": "클라이언트"}

    handler.apply_authenticated_user(payload)

    assert payload["author"] == "홍길동"
    assert payload["updatedBy"] == "홍길동"
    assert payload["authenticatedUser"]["employeeId"] == "A1001"


def test_llm_key_login_requires_signed_in_user():
    handler = web_app.PolicyWebHandler.__new__(web_app.PolicyWebHandler)
    sent = []
    handler.require_api_access = lambda: sent.append("denied") or False
    handler.read_json = lambda: {"key": web_app.LLM_ACCESS_KEY}

    handler.handle_llm_access_login()

    assert sent == ["denied"]
