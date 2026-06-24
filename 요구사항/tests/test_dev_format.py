"""Regression tests for src/exporters/dev_format.py.

변환기 핵심 invariants를 input/samples/의 실제 정책서로 검증.
새 정책서 변환 시 발생할 수 있는 회귀 (extract 함수 시그니처 변경,
mapping.csv 컬럼 누락, 4단 nesting 깨짐, warnings critical 발생 등)를
즉시 catch한다.

상세 가이드: docs/EXPORTERS.md
시드 진입점: AGENTS.md §21
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.exporters.dev_format import build_dev_format


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FULL_SAMPLE = PROJECT_ROOT / "input" / "samples" / "NC_정책서_Full_v1.0_확정본.html"
SIMPLE_SAMPLE = PROJECT_ROOT / "input" / "samples" / "NC_AI검색_정책서_간소화_v1.5.html"
# 상품상세/담기 sample — multi-class diagram-wrap + h4 fallback regression coverage.
# 회원가입/탈퇴(FULL_SAMPLE)와 달리 PR slug(DTL/CMP/SEL...)와 UC slug(CUS/OPS/CS/SYS)가
# 다른 분류 체계라, _extract_processes의 h4 fallback이 동작해야 mapping이 정상화된다.
PDD_SAMPLE = PROJECT_ROOT / "input" / "samples" / "NC_상품상세담기_정책서_Full_v0.11.html"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def full_output(tmp_path_factory) -> Path:
    """Run converter once on Full sample, share output across tests in module."""
    if not FULL_SAMPLE.is_file():
        pytest.skip(f"Full sample not present: {FULL_SAMPLE}")
    out_dir = tmp_path_factory.mktemp("full_export")
    return build_dev_format(FULL_SAMPLE, out_dir)


@pytest.fixture(scope="module")
def simple_output(tmp_path_factory) -> Path:
    """Run converter on the simplified AI검색 sample (smoke test for 간소화 inputs)."""
    if not SIMPLE_SAMPLE.is_file():
        pytest.skip(f"Simple sample not present: {SIMPLE_SAMPLE}")
    out_dir = tmp_path_factory.mktemp("simple_export")
    return build_dev_format(SIMPLE_SAMPLE, out_dir)


@pytest.fixture(scope="module")
def pdd_output(tmp_path_factory) -> Path:
    """Run converter on the 상품상세/담기 Full sample.

    회귀 방지 대상 두 가지:
    1) diagram-wrap multi-class regex (e.g. class="diagram-wrap state-transition-diagram")
    2) _extract_processes의 h4 fallback (PR slug != UC slug 정책서)
    """
    if not PDD_SAMPLE.is_file():
        pytest.skip(f"PDD sample not present: {PDD_SAMPLE}")
    out_dir = tmp_path_factory.mktemp("pdd_export")
    return build_dev_format(PDD_SAMPLE, out_dir)


# ---------------------------------------------------------------------------
# Full 정책서 — 모든 산출물·구조·검증 invariants
# ---------------------------------------------------------------------------

def test_full_artifacts_present(full_output: Path) -> None:
    """5종 핵심 산출물 + diagrams/ 폴더가 모두 생성되어야 한다."""
    assert (full_output / "README.md").is_file(), "README.md missing"
    assert (full_output / "00_INDEX.md").is_file(), "00_INDEX.md missing"
    assert (full_output / "mapping.csv").is_file(), "mapping.csv missing"
    assert (full_output / "entities.yaml").is_file(), "entities.yaml missing"
    assert (full_output / "warnings.md").is_file(), "warnings.md missing"
    # Full 정책서는 BPMN/UC/State 다이어그램 포함
    assert (full_output / "diagrams").is_dir(), "diagrams/ missing"
    assert any((full_output / "diagrams").glob("*.svg")), "diagrams/*.svg missing"


def test_full_usecase_files_exist(full_output: Path) -> None:
    """UC별 분리 파일이 최소 5개 이상 생성되어야 한다 (Full 정책서는 13개 UC)."""
    uc_files = list(full_output.glob("usecase_US-*.md"))
    assert len(uc_files) >= 5, f"too few usecase files: {len(uc_files)}"
    # 모든 UC 파일이 비어있지 않아야 함
    for uc in uc_files:
        assert uc.stat().st_size > 0, f"empty usecase file: {uc.name}"


def test_full_4_level_nesting(full_output: Path) -> None:
    """Full 정책서의 가장 큰 UC 파일은 4단 nesting (H1/H2/H3/H4)을 모두 포함해야 한다.

    결정사항 #7 (디자인팀 mermaid 샘플 등가 4단 nesting) 검증.
    """
    uc_files = sorted(full_output.glob("usecase_US-*.md"), key=lambda p: -p.stat().st_size)
    assert uc_files, "no usecase files to inspect"
    largest = uc_files[0]
    text = largest.read_text(encoding="utf-8")
    h1 = len(re.findall(r"^# ", text, re.MULTILINE))
    h2 = len(re.findall(r"^## ", text, re.MULTILINE))
    h3 = len(re.findall(r"^### ", text, re.MULTILINE))
    h4 = len(re.findall(r"^#### ", text, re.MULTILINE))
    assert h1 >= 1, f"{largest.name}: missing H1 (UC)"
    assert h2 >= 1, f"{largest.name}: missing H2 (Process)"
    assert h3 >= 1, f"{largest.name}: missing H3 (Function)"
    assert h4 >= 1, f"{largest.name}: missing H4 (Policy Group)"


def test_full_warnings_zero_critical(full_output: Path) -> None:
    """Full 정책서 변환 결과의 broken_refs는 0이어야 한다.

    orphans는 정보용 (정책서 작성 단계의 매핑 누락 신호)이라 critical 아님.
    """
    warnings_text = (full_output / "warnings.md").read_text(encoding="utf-8")
    bf_match = re.search(r"Broken cross-refs.*?\((\d+)건\)", warnings_text)
    assert bf_match, "warnings.md missing 'Broken cross-refs' section"
    broken_count = int(bf_match.group(1))
    assert broken_count == 0, (
        f"broken_refs found ({broken_count}). "
        "변환기 회귀 또는 정책서 ID 정합성 깨짐."
    )


def test_full_mapping_csv_columns(full_output: Path) -> None:
    """mapping.csv는 결정된 11개 컬럼 (UC/PR/FN/PG/PI + 이름 + actor)을 헤더로 가져야 한다."""
    csv_text = (full_output / "mapping.csv").read_text(encoding="utf-8")
    first_line = csv_text.splitlines()[0]
    expected_columns = {
        "usecase_id", "usecase_name",
        "process_id", "process_name",
        "function_id", "function_name", "function_actor",
        "policy_group_id", "policy_group_name",
        "policy_item_id", "policy_item_name",
    }
    actual_columns = set(first_line.split(","))
    missing = expected_columns - actual_columns
    assert not missing, f"mapping.csv missing columns: {missing}"


def test_full_mapping_csv_rows(full_output: Path) -> None:
    """mapping.csv는 헤더 외에 최소 100 data rows를 가져야 한다."""
    csv_text = (full_output / "mapping.csv").read_text(encoding="utf-8")
    lines = csv_text.splitlines()
    data_rows = len(lines) - 1  # exclude header
    assert data_rows >= 100, f"too few mapping rows: {data_rows}"


def test_full_entities_yaml_structure(full_output: Path) -> None:
    """entities.yaml은 9개 핵심 entity 섹션 + meta + cross_refs + hierarchy를 포함해야 한다."""
    yml = (full_output / "entities.yaml").read_text(encoding="utf-8")
    required_sections = [
        "meta:",
        "usecases:",
        "actors:",
        "processes:",
        "functions:",
        "policy_groups:",
        "policy_items:",
        "states:",
        "transitions:",
        "terms:",
        "cross_refs:",
        "hierarchy:",
    ]
    for sec in required_sections:
        assert sec in yml, f"entities.yaml missing section: {sec}"


def test_full_readme_generated(full_output: Path) -> None:
    """자동 생성된 README.md는 최소 사이즈와 두 팀 활용 가이드 핵심 키워드를 포함해야 한다."""
    readme = (full_output / "README.md").read_text(encoding="utf-8")
    assert len(readme) >= 1000, f"README.md too short: {len(readme)} bytes"
    # 두 팀이 받을 수 있는 활용 가이드 — AI 에이전트 input + 산출물 5종 안내
    assert "산출물" in readme, "README missing 산출물 안내"
    assert "mapping.csv" in readme, "README missing mapping.csv 설명"
    assert "usecase_" in readme, "README missing usecase_ 파일 설명"
    assert "AI" in readme, "README missing AI 활용 시나리오"


# ---------------------------------------------------------------------------
# 간소화 정책서 — 최소 산출물 smoke test
# ---------------------------------------------------------------------------

def test_simple_artifacts_present(simple_output: Path) -> None:
    """간소화 정책서도 5종 산출물 생성에 성공해야 한다 (diagrams 없을 수 있음)."""
    assert (simple_output / "README.md").is_file()
    assert (simple_output / "00_INDEX.md").is_file()
    assert (simple_output / "mapping.csv").is_file()
    assert (simple_output / "entities.yaml").is_file()
    assert (simple_output / "warnings.md").is_file()
    uc_files = list(simple_output.glob("usecase_US-*.md"))
    assert uc_files, "간소화 정책서: usecase_*.md 미생성"


def test_simple_no_broken_refs(simple_output: Path) -> None:
    """간소화 정책서도 broken_refs는 0이어야 한다."""
    warnings_text = (simple_output / "warnings.md").read_text(encoding="utf-8")
    bf_match = re.search(r"Broken cross-refs.*?\((\d+)건\)", warnings_text)
    assert bf_match
    assert int(bf_match.group(1)) == 0


# ---------------------------------------------------------------------------
# 상품상세/담기 Full — multi-class diagram + h4 fallback 회귀 방지
# ---------------------------------------------------------------------------

def test_pdd_diagrams_multiclass_extracted(pdd_output: Path) -> None:
    """diagram-wrap이 multi-class(예: 'diagram-wrap state-transition-diagram')로
    감싸여 있어도 SVG 추출이 동작해야 한다.

    회귀 방지 대상: extract_diagrams regex가 multi-class를 지원하지 않으면
    상품상세/담기처럼 상태 전이 다이어그램이 0개로 추출됨.
    """
    diag_dir = pdd_output / "diagrams"
    assert diag_dir.is_dir(), "diagrams/ folder missing for PDD sample"
    svgs = list(diag_dir.glob("*.svg"))
    assert len(svgs) >= 3, f"expected at least 3 SVGs (BPMN/State/UC), got {len(svgs)}"


def test_pdd_mapping_rich_via_h4_fallback(pdd_output: Path) -> None:
    """PR slug와 UC slug가 다른 분류 체계여도 mapping.csv가 풍부해야 한다.

    회귀 방지 대상: _extract_processes의 h4 fallback이 동작하지 않으면
    Process.usecase_id가 비어 mapping.csv가 거의 비어버린다
    (fix 전 상품상세/담기는 28 rows, fix 후 900+ rows).
    """
    csv_text = (pdd_output / "mapping.csv").read_text(encoding="utf-8")
    data_rows = len(csv_text.splitlines()) - 1
    assert data_rows >= 500, (
        f"mapping.csv too few rows ({data_rows}). "
        "h4 fallback이 깨지면 UC↔Process 매핑이 끊긴다."
    )


def test_pdd_warnings_zero_critical(pdd_output: Path) -> None:
    """상품상세/담기도 broken_refs 0이어야 한다."""
    warnings_text = (pdd_output / "warnings.md").read_text(encoding="utf-8")
    bf_match = re.search(r"Broken cross-refs.*?\((\d+)건\)", warnings_text)
    assert bf_match
    assert int(bf_match.group(1)) == 0


def test_pdd_uc_files_rich(pdd_output: Path) -> None:
    """주요 UC 파일이 placeholder가 아닌 풍부한 내용이어야 한다 (>10KB 5개 이상)."""
    uc_files = list(pdd_output.glob("usecase_US-*.md"))
    rich = [f for f in uc_files if f.stat().st_size >= 10_000]
    assert len(rich) >= 5, (
        f"too few rich UC files ({len(rich)}). "
        "Process가 UC에 안 묶이면 대부분 UC가 placeholder가 된다."
    )


# ---------------------------------------------------------------------------
# Silent failure / unknown prefix 자동 감지 (P0 + P2) — 3 baseline 모두 0이어야 함.
# 새 정책서 변환 시 0이 아니면 silent failure 신호로 cold review 가이드.
# ---------------------------------------------------------------------------

def _warnings_section_count(warnings_text: str, section_title_prefix: str) -> int | None:
    """warnings.md에서 특정 섹션의 (N건) 카운트 추출. 섹션이 없으면 None."""
    m = re.search(re.escape(section_title_prefix) + r".*?\((\d+)건\)", warnings_text)
    return int(m.group(1)) if m else None


def test_full_no_silent_failure(full_output: Path) -> None:
    """회원가입/탈퇴 baseline에 silent_failure_suspect 0건이어야 한다 (P0 회귀 방지)."""
    w = (full_output / "warnings.md").read_text(encoding="utf-8")
    cnt = _warnings_section_count(w, "Silent failure 의심")
    assert cnt == 0, f"회원가입/탈퇴 baseline에 silent failure 경고 발생: {cnt}건"


def test_full_no_unknown_prefix(full_output: Path) -> None:
    """회원가입/탈퇴 baseline에 unknown_id_prefixes 0건이어야 한다 (P2 회귀 방지)."""
    w = (full_output / "warnings.md").read_text(encoding="utf-8")
    cnt = _warnings_section_count(w, "Unknown ID prefix")
    assert cnt == 0, f"회원가입/탈퇴 baseline에 unknown prefix 경고 발생: {cnt}건"


def test_pdd_no_silent_failure(pdd_output: Path) -> None:
    """상품상세/담기 baseline도 P0 silent failure 0건이어야 한다."""
    w = (pdd_output / "warnings.md").read_text(encoding="utf-8")
    cnt = _warnings_section_count(w, "Silent failure 의심")
    assert cnt == 0, f"상품상세/담기 baseline에 silent failure 경고 발생: {cnt}건"


def test_pdd_no_unknown_prefix(pdd_output: Path) -> None:
    """상품상세/담기 baseline도 P2 unknown prefix 0건이어야 한다."""
    w = (pdd_output / "warnings.md").read_text(encoding="utf-8")
    cnt = _warnings_section_count(w, "Unknown ID prefix")
    assert cnt == 0, f"상품상세/담기 baseline에 unknown prefix 경고 발생: {cnt}건"


# ---------------------------------------------------------------------------
# Cosmetic 1 회귀 방지: PolicyItem content가 leading "- " 머리표 없이 시작.
# ---------------------------------------------------------------------------

def _policy_item_contents_from_yaml(yaml_path: Path) -> list[str]:
    """entities.yaml에서 PolicyItem content 값들만 추출 (간이 파서)."""
    text = yaml_path.read_text(encoding="utf-8")
    # quoted single-line content: `    content: "..."`
    return re.findall(r'^    content: "((?:[^"\\]|\\.)*)"', text, re.MULTILINE)


def test_full_policy_content_no_leading_bullet(full_output: Path) -> None:
    """회원가입/탈퇴 baseline의 PolicyItem content 어느 것도 leading bullet으로
    시작하면 안 됨 (Cosmetic 1 fix 회귀 방지)."""
    contents = _policy_item_contents_from_yaml(full_output / "entities.yaml")
    leading_bullets = [c[:30] for c in contents if re.match(r"^[•·\-\*▪]\s", c)]
    assert not leading_bullets, (
        f"{len(leading_bullets)} PolicyItem content가 leading bullet으로 시작합니다: "
        f"{leading_bullets[:3]}"
    )


def test_pdd_policy_content_no_leading_bullet(pdd_output: Path) -> None:
    """상품상세/담기 baseline도 동일 (Cosmetic 1 회귀 방지)."""
    contents = _policy_item_contents_from_yaml(pdd_output / "entities.yaml")
    leading_bullets = [c[:30] for c in contents if re.match(r"^[•·\-\*▪]\s", c)]
    assert not leading_bullets, (
        f"{len(leading_bullets)} PolicyItem content가 leading bullet으로 시작합니다: "
        f"{leading_bullets[:3]}"
    )


# ---------------------------------------------------------------------------
# Class-first 분류 (B) 회귀 방지
# ---------------------------------------------------------------------------

def test_pdd_class_first_classification_intact(pdd_output: Path) -> None:
    """상품상세/담기 baseline의 entity 카운트가 class-first 분류 도입 후에도 유지.

    회귀 방지 대상: CLASS_TO_BUCKET 매핑이 헤더 fallback과 다른 bucket으로
    분류하면 entity 수가 변함. 같은 결과면 OK (class와 헤더가 같은 의미).
    """
    yml = (pdd_output / "entities.yaml").read_text(encoding="utf-8")
    # PDD baseline 기준 카운트 (456b2da commit 시점 + class-first 이후 유지)
    expected_min = {
        "usecases": 15,
        "processes": 35,
        "functions": 30,
        "policy_groups": 18,
        "policy_items": 100,
        "states": 15,
        "transitions": 20,
        "terms": 10,
    }
    for section, min_count in expected_min.items():
        # entry pattern: "  - id:"
        m = re.search(
            rf"^{section}:\s*\n((?:[^\n]*\n)*?)(?=^[a-z_]+:|^---|\Z)",
            yml, re.MULTILINE,
        )
        assert m, f"{section} section not found in entities.yaml"
        # Entry counter: most entities use "  - id:", transitions use "  - from_state:".
        # Generic "  - " (2-space indent + dash + space) catches both.
        entries = len(re.findall(r"^  - ", m.group(1), re.MULTILINE))
        assert entries >= min_count, (
            f"{section} count {entries} < expected {min_count}. "
            "class-first 분류가 헤더 fallback과 다른 bucket을 반환했을 가능성."
        )


def test_full_class_first_classification_intact(full_output: Path) -> None:
    """회원가입/탈퇴 baseline(class 없음)이 class-first 도입 후에도 헤더 fallback으로
    정상 분류되는지. CLASS_TO_BUCKET 분기가 의도치 않게 legacy를 잡으면 안 됨."""
    yml = (full_output / "entities.yaml").read_text(encoding="utf-8")
    expected_min = {
        "usecases": 12,
        "processes": 20,
        "functions": 25,
        "policy_groups": 40,
        "policy_items": 400,
        "states": 7,
        "transitions": 100,
        "terms": 35,
    }
    for section, min_count in expected_min.items():
        m = re.search(
            rf"^{section}:\s*\n((?:[^\n]*\n)*?)(?=^[a-z_]+:|^---|\Z)",
            yml, re.MULTILINE,
        )
        assert m, f"{section} section not found in entities.yaml"
        # Entry counter: most entities use "  - id:", transitions use "  - from_state:".
        # Generic "  - " (2-space indent + dash + space) catches both.
        entries = len(re.findall(r"^  - ", m.group(1), re.MULTILINE))
        assert entries >= min_count, (
            f"legacy {section} count {entries} < expected {min_count}. "
            "class-first 도입이 헤더 fallback 경로를 깨뜨렸을 가능성."
        )
