"""Runtime path helpers for local and hosted environments."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_runtime_path(env_key: str, default: str | Path) -> Path:
    raw = os.environ.get(env_key, "").strip()
    candidate = Path(raw).expanduser() if raw else Path(default)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve(strict=False)


INPUT_ROOT = resolve_runtime_path("NC_INPUT_DIR", PROJECT_ROOT / "input")
OUTPUT_ROOT = resolve_runtime_path("NC_OUTPUT_DIR", PROJECT_ROOT / "output")
REPORTS_ROOT = resolve_runtime_path("NC_REPORTS_DIR", PROJECT_ROOT / "reports")
LOGS_ROOT = REPORTS_ROOT / "logs"
EVIDENCE_ROOT = REPORTS_ROOT / "evidence"
INSPECTIONS_ROOT = REPORTS_ROOT / "inspections"
TOPIC_KNOWLEDGE_ROOT = resolve_runtime_path("NC_TOPIC_KNOWLEDGE_DIR", EVIDENCE_ROOT / "topic_knowledge")
REFERENCE_DB_PATH = resolve_runtime_path("NC_REFERENCE_DB_PATH", EVIDENCE_ROOT / "reference_evidence.db")
REQUIREMENTS_DB_PATH = resolve_runtime_path("NC_REQUIREMENTS_DB_PATH", EVIDENCE_ROOT / "requirements.db")
POLICY_GRAPH_DB_PATH = resolve_runtime_path("NC_POLICY_GRAPH_DB_PATH", EVIDENCE_ROOT / "policy_graph.db")
FEATURE_INVENTORY_DB_PATH = resolve_runtime_path("NC_FEATURE_INVENTORY_DB_PATH", EVIDENCE_ROOT / "feature_inventory.db")
