from src.policy_versioning import (
    INITIAL_POLICY_VERSION,
    format_policy_version,
    next_policy_version,
    parse_policy_version,
    policy_version_sort_key,
)


def test_next_policy_version_starts_at_v0_10() -> None:
    assert INITIAL_POLICY_VERSION == "v0.10"
    assert next_policy_version([]) == "v0.10"


def test_next_policy_version_increments_minor_sequence_without_decimal_rollover() -> None:
    assert next_policy_version(["v0.10"]) == "v0.11"
    assert next_policy_version(["v0.18"]) == "v0.19"
    assert next_policy_version(["v0.19"]) == "v0.20"


def test_legacy_one_digit_versions_are_interpreted_as_migrated_sequence() -> None:
    assert parse_policy_version("v0.1") == (0, 10, "")
    assert parse_policy_version("v0.9") == (0, 18, "")
    assert next_policy_version(["v0.1"]) == "v0.11"


def test_policy_version_format_and_sort_key_use_two_digit_minor() -> None:
    assert format_policy_version(0, 9) == "v0.09"
    assert format_policy_version(1, 0, "_보완본") == "v1.00_보완본"
    assert parse_policy_version("v0.20") == (0, 20, "")
    assert policy_version_sort_key("v0.20") > policy_version_sort_key("v0.19")
