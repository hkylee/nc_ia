#!/usr/bin/env python3
"""Build reference HTML summary pages for feature inventory sheets."""

from __future__ import annotations

import html
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from feature_inventory import DEFAULT_FEATURE_INVENTORY_DB_PATH, ensure_feature_inventory_database  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "output" / "reference_html"
CHANNEL_PAGES = [
    {
        "channel": "T 월드",
        "title": "T 월드 기능 내역",
        "file": "function-inventory-tworld.html",
        "lens": "개인 고객의 조회, 변경, 가입, 납부, 고객지원 흐름에 걸친 기능 밀도를 확인합니다.",
    },
    {
        "channel": "T 멤버십",
        "title": "T 멤버십 기능 내역",
        "file": "function-inventory-membership.html",
        "lens": "혜택 탐색, 예약, 사용처, 등급·포인트 경험을 구성하는 기능 패턴을 확인합니다.",
    },
    {
        "channel": "T 다이렉트",
        "title": "T 다이렉트 기능 내역",
        "file": "function-inventory-direct.html",
        "lens": "상품 탐색에서 주문, 가입, 배송, 개통 전후 업무로 이어지는 구매 여정 기능을 확인합니다.",
    },
    {
        "channel": "T 우주",
        "title": "T 우주 기능 내역",
        "file": "function-inventory-universe.html",
        "lens": "구독 상품 상세, 담기, 결제, 이용, 마이 영역의 구독형 서비스 기능 구조를 확인합니다.",
    },
    {
        "channel": "T 월드 Biz",
        "title": "T 월드 Biz 기능 내역",
        "file": "function-inventory-biz.html",
        "lens": "법인·기업 고객의 회선, 요금, 부가서비스, 인증·관리 업무 기능을 확인합니다.",
    },
    {
        "channel": "통합",
        "title": "통합 기능 목록",
        "file": "function-inventory-integrated.html",
        "lens": "5개 채널 기능을 통합 관점에서 재분류한 공통 기능 후보와 중복 패턴을 확인합니다.",
    },
]


def main() -> int:
    db_path = ensure_feature_inventory_database()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        page_payloads = [build_channel_payload(conn, page) for page in CHANNEL_PAGES]
    for payload in page_payloads:
        write_html(OUTPUT_DIR / payload["file"], render_feature_inventory_page(payload, page_payloads))
    print(f"generated {len(page_payloads)} feature inventory reference html file(s)")
    return 0


def write_html(path: Path, document: str) -> None:
    cleaned = "\n".join(line.rstrip() for line in document.splitlines()).strip() + "\n"
    path.write_text(cleaned, encoding="utf-8")


def build_channel_payload(conn: sqlite3.Connection, page: Mapping[str, str]) -> dict:
    channel = page["channel"]
    summary = dict(
        conn.execute(
            "SELECT * FROM feature_channel_summary WHERE channel = ?",
            (channel,),
        ).fetchone()
        or {}
    )
    top_depth = fetch_rows(
        conn,
        """
        SELECT depth_value AS label, unique_feature_rows AS value
        FROM feature_depth_summary
        WHERE channel = ? AND depth_level = 1 AND COALESCE(depth_value, '') <> ''
        ORDER BY unique_feature_rows DESC, depth_value
        LIMIT 8
        """,
        (channel,),
    )
    top_screens = fetch_rows(
        conn,
        """
        SELECT screen_name AS label, unique_feature_rows AS value
        FROM feature_screen_summary
        WHERE channel = ? AND COALESCE(screen_name, '') <> ''
        ORDER BY unique_feature_rows DESC, screen_name
        LIMIT 8
        """,
        (channel,),
    )
    top_features = fetch_rows(
        conn,
        """
        SELECT feature_name AS label, COUNT(*) AS value
        FROM feature_unique_rows
        WHERE channel = ? AND COALESCE(feature_name, '') <> ''
        GROUP BY feature_name
        ORDER BY value DESC, feature_name
        LIMIT 10
        """,
        (channel,),
    )
    issue_types = fetch_rows(
        conn,
        """
        SELECT issue_type AS label, COUNT(*) AS value
        FROM cleanup_issues
        WHERE source_sheet = CASE WHEN ? = '통합' THEN '통합 기능 목록' ELSE ? END
        GROUP BY issue_type
        ORDER BY value DESC, issue_type
        """,
        (channel, channel),
    )
    type_mix = feature_type_mix(
        [
            row["feature_name"] or ""
            for row in conn.execute(
                "SELECT feature_name FROM feature_unique_rows WHERE channel = ?",
                (channel,),
            ).fetchall()
        ]
    )
    payload = {
        **page,
        "summary": summary,
        "topDepth": top_depth,
        "topScreens": top_screens,
        "topFeatures": top_features,
        "issueTypes": issue_types,
        "typeMix": type_mix,
        "narrative": build_narrative(page, summary, top_depth, top_screens, top_features),
    }
    if channel == "통합":
        payload.update(build_integrated_payload(conn))
    return payload


def fetch_rows(conn: sqlite3.Connection, query: str, params: Sequence[object]) -> list[dict]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def build_integrated_payload(conn: sqlite3.Connection) -> dict:
    structure_mix = fetch_rows(
        conn,
        """
        SELECT
          CASE
            WHEN COALESCE(condition_text, '') <> '' AND COALESCE(input_text, '') <> '' AND COALESCE(output_text, '') <> '' THEN '조건+입력+출력'
            WHEN COALESCE(condition_text, '') <> '' AND COALESCE(output_text, '') <> '' THEN '조건+출력'
            WHEN COALESCE(input_text, '') <> '' AND COALESCE(output_text, '') <> '' THEN '입력+출력'
            WHEN COALESCE(condition_text, '') <> '' THEN '조건 중심'
            WHEN COALESCE(input_text, '') <> '' THEN '입력 중심'
            WHEN COALESCE(output_text, '') <> '' THEN '출력 중심'
            ELSE '설명 중심'
          END AS label,
          COUNT(*) AS value
        FROM feature_unique_rows
        WHERE channel = '통합'
        GROUP BY label
        ORDER BY value DESC, label
        """,
        (),
    )
    policy_candidates = fetch_rows(
        conn,
        """
        SELECT feature_name AS label, COUNT(*) AS value
        FROM feature_unique_rows
        WHERE channel = '통합'
          AND COALESCE(condition_text, '') <> ''
          AND COALESCE(feature_name, '') <> ''
        GROUP BY feature_name
        ORDER BY value DESC, feature_name
        LIMIT 12
        """,
        (),
    )
    data_candidates = fetch_rows(
        conn,
        """
        SELECT feature_name AS label, COUNT(*) AS value
        FROM feature_unique_rows
        WHERE channel = '통합'
          AND COALESCE(feature_name, '') <> ''
          AND (
            feature_description LIKE '%데이터%'
            OR feature_description LIKE '%상태%'
            OR feature_description LIKE '%저장%'
            OR feature_description LIKE '%API%'
            OR feature_description LIKE '%바인딩%'
          )
        GROUP BY feature_name
        ORDER BY value DESC, feature_name
        LIMIT 12
        """,
        (),
    )
    condition_count = scalar_count(
        conn,
        "SELECT COUNT(*) FROM feature_unique_rows WHERE channel = '통합' AND COALESCE(condition_text, '') <> ''",
    )
    input_count = scalar_count(
        conn,
        "SELECT COUNT(*) FROM feature_unique_rows WHERE channel = '통합' AND COALESCE(input_text, '') <> ''",
    )
    output_count = scalar_count(
        conn,
        "SELECT COUNT(*) FROM feature_unique_rows WHERE channel = '통합' AND COALESCE(output_text, '') <> ''",
    )
    evidence_count = scalar_count(
        conn,
        "SELECT COUNT(*) FROM feature_unique_rows WHERE channel = '통합' AND COALESCE(confidence_level, '') <> ''",
    )
    return {
        "integratedMetrics": {
            "conditionCount": condition_count,
            "inputCount": input_count,
            "outputCount": output_count,
            "evidenceCount": evidence_count,
        },
        "structureMix": structure_mix,
        "policyCandidates": policy_candidates,
        "dataCandidates": data_candidates,
    }


def scalar_count(conn: sqlite3.Connection, query: str) -> int:
    row = conn.execute(query).fetchone()
    return int(row[0] or 0) if row else 0


def feature_type_mix(feature_names: Iterable[str]) -> list[dict]:
    buckets = [
        ("이동·탐색", ("이동", "뒤로", "홈", "gnb", "메뉴", "탭", "링크", "네비게이션")),
        ("조회·노출", ("조회", "노출", "호출", "표시", "영역", "리스트", "정보")),
        ("입력·선택", ("입력", "선택", "검색", "필터", "체크", "설정")),
        ("처리·확정", ("신청", "변경", "결제", "인증", "저장", "등록", "삭제", "취소", "확인")),
        ("안내·약관", ("안내", "툴팁", "공지", "약관", "유의", "도움말")),
    ]
    counts: Counter[str] = Counter()
    for raw in feature_names:
        text = raw.casefold()
        matched = False
        for label, terms in buckets:
            if any(term in text for term in terms):
                counts[label] += 1
                matched = True
                break
        if not matched:
            counts["기타"] += 1
    return [{"label": label, "value": counts[label]} for label, _ in buckets if counts[label]] + (
        [{"label": "기타", "value": counts["기타"]}] if counts["기타"] else []
    )


def build_narrative(
    page: Mapping[str, str],
    summary: Mapping[str, object],
    top_depth: Sequence[Mapping[str, object]],
    top_screens: Sequence[Mapping[str, object]],
    top_features: Sequence[Mapping[str, object]],
) -> dict:
    feature_rows = int(summary.get("feature_rows") or 0)
    unique_rows = int(summary.get("unique_feature_rows") or 0)
    duplicate_rows = int(summary.get("duplicate_rows") or 0)
    screen_count = int(summary.get("screen_count") or 0)
    top_area = str((top_depth or top_screens or top_features or [{"label": "주요 기능"}])[0].get("label") or "주요 기능")
    repeated = str((top_features or [{"label": "반복 기능"}])[0].get("label") or "반복 기능")
    duplicate_rate = round(duplicate_rows / max(1, feature_rows) * 100, 1)
    return {
        "summary": (
            f"{page['title']}은 {feature_rows:,}개 기능 행과 {unique_rows:,}개 고유 기능을 기준으로 정리했습니다."
            f" 화면 기준으로는 {screen_count:,}개 단위를 확인했고, 반복·중복 후보는 {duplicate_rows:,}개입니다."
        ),
        "focus": f"기능 밀도가 가장 높은 축은 '{top_area}'입니다. 가장 많이 반복되는 기능 패턴은 '{repeated}'입니다.",
        "integration": (
            f"중복률은 {duplicate_rate}%입니다. 통합채널 전환 시 공통 이동, 조회, 안내, 입력 기능은 표준 컴포넌트와 공통 정책 기준으로 묶어야 합니다."
        ),
    }


def render_feature_inventory_page(payload: Mapping[str, object], all_pages: Sequence[Mapping[str, object]]) -> str:
    if payload.get("channel") == "통합":
        return render_integrated_page(payload, all_pages)
    return render_channel_page(payload, all_pages)


def render_channel_page(payload: Mapping[str, object], all_pages: Sequence[Mapping[str, object]]) -> str:
    summary = payload["summary"]
    kpis = [
        ("기능 행", f"{int(summary.get('feature_rows') or 0):,}"),
        ("고유 기능", f"{int(summary.get('unique_feature_rows') or 0):,}"),
        ("화면", f"{int(summary.get('screen_count') or 0):,}"),
        ("중복 후보", f"{int(summary.get('duplicate_rows') or 0):,}"),
    ]
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{escape(payload['title'])} · 기능 내역</title>
  <style>{page_css()}</style>
</head>
<body>
  <main class="page function-inventory-page">
    {render_nav(payload, all_pages)}
    <section class="hero">
      <div>
        <div class="eyebrow">FEATURE INVENTORY</div>
        <h1>{escape(payload['title'])}</h1>
        <p class="lead">{escape(payload['lens'])}</p>
      </div>
      <div class="hero-note">
        <strong>요약 관점</strong>
        <span>{escape(payload['narrative']['summary'])}</span>
      </div>
    </section>

    <section class="kpi-grid" aria-label="기능 내역 핵심 수치">
      {''.join(render_kpi(label, value) for label, value in kpis)}
    </section>

    <section class="grid-two">
      <article class="panel">
        <div class="section-head">
          <span>01</span>
          <h2>기능 유형 믹스</h2>
        </div>
        {render_bar_list(payload['typeMix'], empty='분류 가능한 기능명이 없습니다.')}
      </article>
      <article class="panel">
        <div class="section-head">
          <span>02</span>
          <h2>상위 IA·업무 덩어리</h2>
        </div>
        {render_bar_list(payload['topDepth'] or payload['topScreens'], empty='IA Depth 또는 화면 단위가 비어 있습니다.')}
      </article>
    </section>

    <section class="grid-two">
      <article class="panel">
        <div class="section-head">
          <span>03</span>
          <h2>기능 밀도 높은 화면</h2>
        </div>
        {render_bar_list(payload['topScreens'], empty='화면 정보가 없는 통합 목록입니다.')}
      </article>
      <article class="panel">
        <div class="section-head">
          <span>04</span>
          <h2>반복 기능 패턴</h2>
        </div>
        {render_bar_list(payload['topFeatures'])}
      </article>
    </section>

    <section class="panel wide">
      <div class="section-head">
        <span>05</span>
        <h2>정책서·요구사항 전환 시 확인할 질문</h2>
      </div>
      <div class="question-grid">
        <article><b>공통화</b><p>반복되는 이동, 조회, 닫기, 확인 기능을 채널별로 다르게 유지할 이유가 있는가?</p></article>
        <article><b>업무 완결</b><p>기능이 화면 조각에 머물지 않고 고객 과업 시작, 판단, 실행, 완료 흐름으로 이어지는가?</p></article>
        <article><b>정책 기준</b><p>기능 설명에서 상태, 권한, 예외, 이력, 고지 기준으로 승격해야 할 판단축은 무엇인가?</p></article>
      </div>
    </section>

  </main>
</body>
</html>
"""


def render_integrated_page(payload: Mapping[str, object], all_pages: Sequence[Mapping[str, object]]) -> str:
    summary = payload["summary"]
    metrics = payload["integratedMetrics"]
    kpis = [
        ("정규화 기능", f"{int(summary.get('unique_feature_rows') or 0):,}"),
        ("중복 후보", f"{int(summary.get('duplicate_rows') or 0):,}"),
        ("조건 포함", f"{int(metrics.get('conditionCount') or 0):,}"),
        ("근거 보유", f"{int(metrics.get('evidenceCount') or 0):,}"),
    ]
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{escape(payload['title'])} · 기능 내역</title>
  <style>{page_css()}</style>
</head>
<body>
  <main class="page function-inventory-page integrated-page">
    {render_nav(payload, all_pages)}
    <section class="hero integrated-hero">
      <div>
        <div class="eyebrow">INTEGRATED FUNCTION MAP</div>
        <h1>{escape(payload['title'])}</h1>
        <p class="lead">통합 기능 목록은 채널별 화면 목록이 아니라, 통합채널에서 공통 컴포넌트·정책·데이터 계약으로 묶을 후보를 정리한 기능 구조표입니다.</p>
      </div>
      <div class="hero-note">
        <strong>읽는 관점</strong>
        <span>화면 수나 IA Depth보다 조건, 입력, 출력, 반복 기능명, 신뢰도 근거를 기준으로 정책서와 요구사항 전환 대상을 찾습니다.</span>
      </div>
    </section>

    <section class="kpi-grid" aria-label="통합 기능 핵심 수치">
      {''.join(render_kpi(label, value) for label, value in kpis)}
    </section>

    <section class="integrated-map">
      <article>
        <span>01</span>
        <strong>공통 기능 표준화</strong>
        <p>이전/다음 이동, GNB, 탭, 푸터, 제목처럼 반복되는 기능을 채널별 구현 단위가 아니라 공통 UX·컴포넌트 기준으로 묶습니다.</p>
      </article>
      <div class="map-arrow">›</div>
      <article>
        <span>02</span>
        <strong>정책 판단 조건화</strong>
        <p>조건이 붙은 기능은 노출 기준, 권한, 상태, 예외, 고지 기준으로 내려 정책 항목과 검수 케이스로 전환합니다.</p>
      </article>
      <div class="map-arrow">›</div>
      <article>
        <span>03</span>
        <strong>데이터 계약 정렬</strong>
        <p>입력·출력·상태값·API·저장 표현이 있는 기능은 BSS/채널/로그 간 데이터 책임과 결과 반영 기준을 확인합니다.</p>
      </article>
    </section>

    <section class="grid-two">
      <article class="panel">
        <div class="section-head">
          <span>01</span>
          <h2>조건·입력·출력 구조</h2>
        </div>
        {render_bar_list(payload['structureMix'], empty='조건·입력·출력 구조가 비어 있습니다.')}
      </article>
      <article class="panel">
        <div class="section-head">
          <span>02</span>
          <h2>공통 기능 후보</h2>
        </div>
        {render_bar_list(payload['topFeatures'])}
      </article>
    </section>

    <section class="grid-two">
      <article class="panel">
        <div class="section-head">
          <span>03</span>
          <h2>정책화 후보</h2>
        </div>
        {render_bar_list(payload['policyCandidates'])}
      </article>
      <article class="panel">
        <div class="section-head">
          <span>04</span>
          <h2>데이터·상태 처리 후보</h2>
        </div>
        {render_bar_list(payload['dataCandidates'])}
      </article>
    </section>

    <section class="panel wide">
      <div class="section-head">
        <span>05</span>
        <h2>요구사항/정책서 전환 질문</h2>
      </div>
      <div class="question-grid integrated-questions">
        <article><b>공통 UX</b><p>반복 기능을 통합 공통 컴포넌트로 묶을 때 유지해야 할 채널별 예외는 무엇인가?</p></article>
        <article><b>노출 조건</b><p>조건이 붙은 기능의 고객 상태, 권한, 상품 보유, 약관 동의, 오류 복구 기준이 정책으로 분리됐는가?</p></article>
        <article><b>데이터 책임</b><p>입력·출력·상태값이 어느 시스템에서 판단되고, 어떤 이력과 로그로 남아야 하는가?</p></article>
        <article><b>검수 기준</b><p>신뢰도 근거가 있는 기능과 없는 기능을 구분해 Dev/QA 점검 우선순위를 정했는가?</p></article>
      </div>
    </section>
  </main>
</body>
</html>
"""


def render_nav(current: Mapping[str, object], all_pages: Sequence[Mapping[str, object]]) -> str:
    links = []
    for page in all_pages:
        active = " active" if page["file"] == current["file"] else ""
        links.append(f'<a class="nav-chip{active}" href="{escape(page["file"])}">{escape(page["title"])}</a>')
    return f'<nav class="page-nav" aria-label="기능 내역 시트 이동">{"".join(links)}</nav>'


def render_kpi(label: str, value: str) -> str:
    return f'<article class="kpi"><span>{escape(label)}</span><strong>{escape(value)}</strong></article>'


def render_bar_list(rows: Sequence[Mapping[str, object]], *, empty: str = "표시할 데이터가 없습니다.") -> str:
    if not rows:
        return f'<p class="empty">{escape(empty)}</p>'
    max_value = max(int(row.get("value") or 0) for row in rows) or 1
    items = []
    for row in rows:
        label = str(row.get("label") or "")
        value = int(row.get("value") or 0)
        width = max(5, round(value / max_value * 100))
        href = row.get("href")
        label_html = f'<a href="{escape(href)}">{escape(label)}</a>' if href else escape(label)
        items.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{label_html}</div>
              <div class="bar-track"><span style="width:{width}%"></span></div>
              <div class="bar-value">{value:,}</div>
            </div>
            """
        )
    return f'<div class="bar-list">{"".join(items)}</div>'


def render_sheet_card(item: Mapping[str, object]) -> str:
    summary = item["summary"]
    return f"""
    <a class="sheet-card" href="{escape(item['file'])}">
      <span>{escape(item['channel'])}</span>
      <strong>{escape(item['title'])}</strong>
      <p>{int(summary.get('unique_feature_rows') or 0):,}개 고유 기능 · {int(summary.get('screen_count') or 0):,}개 화면</p>
    </a>
    """


def page_css() -> str:
    return """
    :root {
      --ink:#141a28;
      --soft:#526174;
      --muted:#78879a;
      --line:#d8e1ed;
      --blue:#2563eb;
      --sky:#e8f0ff;
      --paper:#fff;
      --wash:#eef2f7;
      --navy:#111827;
      --shadow:0 18px 42px rgba(20,26,40,.08);
    }
    * { box-sizing:border-box; }
    body {
      margin:0;
      background:var(--wash);
      color:var(--ink);
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      line-height:1.55;
    }
    .page { width:calc(100% - 24px); margin:0 auto; padding:16px 0 56px; }
    .page-nav {
      display:flex;
      flex-wrap:wrap;
      gap:8px;
      margin-bottom:12px;
    }
    .nav-chip {
      border:1px solid var(--line);
      border-radius:999px;
      background:#fff;
      color:var(--soft);
      padding:8px 11px;
      font-size:12px;
      font-weight:850;
      text-decoration:none;
    }
    .nav-chip.active {
      border-color:#93c5fd;
      background:#eff6ff;
      color:#1d4ed8;
    }
    .hero {
      display:grid;
      grid-template-columns:minmax(0,1fr) 360px;
      gap:22px;
      align-items:stretch;
      border:1px solid var(--line);
      border-radius:8px;
      background:linear-gradient(135deg,#fff 0%,#f8fbff 100%);
      box-shadow:var(--shadow);
      padding:28px 30px;
    }
    .eyebrow {
      color:var(--blue);
      font-size:12px;
      font-weight:950;
      letter-spacing:.16em;
      text-transform:uppercase;
    }
    h1 { margin:10px 0 8px; font-size:32px; line-height:1.18; letter-spacing:0; }
    h2 { margin:0; font-size:22px; line-height:1.25; }
    .lead { max-width:860px; margin:0; color:var(--ink); font-size:16px; font-weight:820; }
    .hero-note {
      border:1px solid #bfdbfe;
      border-radius:8px;
      background:var(--sky);
      padding:16px;
    }
    .hero-note strong { display:block; color:#1d4ed8; font-size:12px; font-weight:950; letter-spacing:.08em; }
    .hero-note span { display:block; margin-top:8px; color:#143d78; font-size:14px; font-weight:780; }
    .kpi-grid {
      display:grid;
      grid-template-columns:repeat(4,minmax(0,1fr));
      gap:12px;
      margin-top:14px;
    }
    .kpi {
      border:1px solid var(--line);
      border-radius:8px;
      background:#fff;
      box-shadow:var(--shadow);
      padding:16px;
    }
    .kpi span { display:block; color:var(--muted); font-size:12px; font-weight:850; }
    .kpi strong { display:block; margin-top:6px; color:var(--navy); font-size:28px; line-height:1.1; }
    .panel {
      border:1px solid var(--line);
      border-radius:8px;
      background:#fff;
      box-shadow:var(--shadow);
      padding:20px;
    }
    .integrated-map {
      display:grid;
      grid-template-columns:minmax(0,1fr) 38px minmax(0,1fr) 38px minmax(0,1fr);
      gap:12px;
      align-items:stretch;
      margin-top:14px;
    }
    .integrated-map article {
      border:1px solid var(--line);
      border-radius:8px;
      background:#fff;
      box-shadow:var(--shadow);
      padding:18px;
    }
    .integrated-map article span {
      color:var(--blue);
      font-size:12px;
      font-weight:950;
      letter-spacing:.08em;
    }
    .integrated-map article strong {
      display:block;
      margin-top:8px;
      color:var(--ink);
      font-size:18px;
      line-height:1.28;
      font-weight:920;
    }
    .integrated-map article p {
      margin:8px 0 0;
      color:var(--ink);
      font-size:14px;
      font-weight:760;
    }
    .map-arrow {
      align-self:center;
      justify-self:center;
      display:grid;
      place-items:center;
      width:34px;
      height:34px;
      border-radius:999px;
      background:var(--navy);
      color:#fff;
      font-size:24px;
      font-weight:900;
      line-height:1;
    }
    .grid-two {
      display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr));
      gap:12px;
      margin-top:14px;
    }
    .wide { margin-top:14px; }
    .section-head {
      display:flex;
      align-items:center;
      gap:10px;
      margin-bottom:14px;
    }
    .section-head span {
      display:grid;
      place-items:center;
      width:30px;
      height:30px;
      border-radius:999px;
      background:var(--navy);
      color:#fff;
      font-size:12px;
      font-weight:950;
      flex:0 0 auto;
    }
    .bar-list { display:grid; gap:10px; }
    .bar-row {
      display:grid;
      grid-template-columns:minmax(120px,1fr) minmax(120px,1.2fr) 64px;
      gap:10px;
      align-items:center;
    }
    .bar-label {
      min-width:0;
      color:var(--ink);
      font-size:13px;
      font-weight:820;
      overflow:hidden;
      text-overflow:ellipsis;
      white-space:nowrap;
    }
    .bar-label a { color:inherit; text-decoration:none; }
    .bar-track {
      height:10px;
      border-radius:999px;
      background:#eef2f7;
      overflow:hidden;
    }
    .bar-track span {
      display:block;
      height:100%;
      border-radius:999px;
      background:linear-gradient(90deg,#2563eb,#22c55e);
    }
    .bar-value { text-align:right; color:var(--soft); font-size:12px; font-weight:900; }
    .question-grid, .sheet-grid {
      display:grid;
      grid-template-columns:repeat(3,minmax(0,1fr));
      gap:12px;
    }
    .integrated-questions { grid-template-columns:repeat(4,minmax(0,1fr)); }
    .question-grid article, .sheet-card {
      border:1px solid var(--line);
      border-radius:8px;
      background:#fbfdff;
      padding:15px;
    }
    .question-grid b, .sheet-card span {
      display:block;
      color:var(--blue);
      font-size:12px;
      font-weight:950;
    }
    .question-grid p { margin:7px 0 0; color:var(--ink); font-size:14px; font-weight:760; }
    .sheet-card {
      color:inherit;
      text-decoration:none;
      transition:transform .16s ease, border-color .16s ease;
    }
    .sheet-card:hover { transform:translateY(-2px); border-color:#93c5fd; }
    .sheet-card strong { display:block; margin-top:7px; font-size:17px; }
    .sheet-card p { margin:6px 0 0; color:var(--soft); font-size:13px; font-weight:760; }
    .empty { margin:0; color:var(--muted); font-size:14px; font-weight:760; }
    @media (max-width:1100px) {
      .hero, .grid-two, .integrated-map { grid-template-columns:1fr; }
      .map-arrow { transform:rotate(90deg); }
      .kpi-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
      .question-grid, .sheet-grid, .integrated-questions { grid-template-columns:1fr; }
    }
    @media (max-width:720px) {
      .page { width:calc(100% - 16px); padding:10px 0 48px; }
      .hero, .panel { padding:16px; }
      h1 { font-size:26px; }
      h2 { font-size:19px; }
      .bar-row { grid-template-columns:1fr 56px; }
      .bar-track { grid-column:1 / -1; grid-row:2; }
      .kpi-grid { grid-template-columns:1fr; }
    }
    """


def escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


if __name__ == "__main__":
    raise SystemExit(main())
