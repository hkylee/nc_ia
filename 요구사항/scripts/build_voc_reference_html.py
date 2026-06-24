#!/usr/bin/env python3
"""Build VoC analysis reference HTML pages from source PDFs.

The first VoC page was hand-curated in the workspace.  This script keeps that
page intact by default and generates the remaining VoC reference pages with the
same visual/reporting structure.
"""

from __future__ import annotations

import argparse
import html
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "input" / "references"
OUTPUT_DIR = ROOT / "output" / "reference_html"
SEED_HTML = OUTPUT_DIR / "voc-auto-payment-apply-change.html"
VOC_SUMMARY = ("voc-summary", "종합")


VOC_DOCUMENTS = [
    ("voc-auto-payment-apply-change", "자동 납부 신청 변경"),
    ("voc-t-universe-subscription", "우주 패스 / T우주 / 구독"),
    ("voc-paper-bill", "우편 청구서"),
    ("voc-add-on-cancel", "부가서비스 해지"),
    ("voc-address-change", "주소 변경"),
    ("voc-lost-device", "분실"),
    ("voc-bundle", "결합"),
    ("voc-bill-info", "청구서 정보"),
    ("voc-contact-change", "연락처 변경"),
    ("voc-membership", "멤버십"),
    ("voc-temporary-suspension", "일시 정지"),
    ("voc-plan-change", "요금제 변경"),
    ("voc-direct-shop", "다이렉트 샵 / 티월드 다이렉트"),
    ("voc-contract-discount", "약정 할인 / 선택 약정"),
    ("voc-bank-transfer-payment", "계좌 이체 요금 납부"),
    ("voc-auto-payment-cancel", "자동 납부 해지"),
    ("voc-card-payment", "신용 카드 요금 납부"),
    ("voc-auto-payment-apply", "자동 납부 신청 / 자동 납부 변경"),
    ("voc-add-on-join", "부가서비스 가입"),
    ("voc-wave-flo", "웨이브 / 플로"),
    ("voc-refill-coupon", "리필 쿠폰"),
    ("voc-discount-change", "할인 변경"),
    ("voc-data-gift", "데이터 선물"),
    ("voc-mobile-cancel", "휴대폰 해지 / 핸드폰 해지 / 번호 해지"),
    ("voc-suspension-release", "정지 해제 / 일시 정지 해제"),
]


POLICY_CONVERSIONS = {
    "탐색": ("진입점", "고객은 어디에서 업무를 시작할 수 있는가?", "통합채널의 홈, 마이, 요금, 상품 영역에서 같은 업무 진입점을 제공하고, 현재 상태에서 가능한 다음 행동을 명확히 보여줘야 한다."),
    "발견": ("진입점", "고객은 어디에서 업무를 시작할 수 있는가?", "통합채널의 홈, 마이, 요금, 상품 영역에서 같은 업무 진입점을 제공하고, 현재 상태에서 가능한 다음 행동을 명확히 보여줘야 한다."),
    "인지": ("사전 고지", "무엇을 처리 전에 알려야 하는가?", "요금, 혜택, 적용 시점, 제한 조건, 후속 영향을 업무 실행 전에 이해 가능한 문장과 비교 정보로 제공해야 한다."),
    "이해": ("사전 고지", "무엇을 처리 전에 알려야 하는가?", "요금, 혜택, 적용 시점, 제한 조건, 후속 영향을 업무 실행 전에 이해 가능한 문장과 비교 정보로 제공해야 한다."),
    "인증": ("권한", "누가 직접 처리하거나 대신 처리할 수 있는가?", "본인, 가족, 법정대리인, 대리인의 처리 가능 범위와 인증, 동의, 위임 조건을 정책 기준으로 분리해야 한다."),
    "권한": ("권한", "누가 직접 처리하거나 대신 처리할 수 있는가?", "본인, 가족, 법정대리인, 대리인의 처리 가능 범위와 인증, 동의, 위임 조건을 정책 기준으로 분리해야 한다."),
    "프로세스": ("연계", "어떤 업무를 한 번에 묶어야 하는가?", "상담, 앱, BSS, 외부 기관에서 끊어진 처리를 고객 과업 기준의 단일 흐름으로 재구성해야 한다."),
    "정책": ("처리 가능 범위", "언제 셀프 처리할 수 있고 언제 제한되는가?", "평일, 야간, 주말, 공휴일, 청구 마감, 개통·해지 시점별 처리 가능 범위와 대체 행동을 정의해야 한다."),
    "시스템": ("상태·오류", "실패와 오류를 어떻게 복구하는가?", "접수, 검증, 반영, 실패, 취소 상태를 고객에게 보여주고 재시도, 대체 경로, 상담 전환 기준을 연결해야 한다."),
    "오류": ("상태·오류", "실패와 오류를 어떻게 복구하는가?", "접수, 검증, 반영, 실패, 취소 상태를 고객에게 보여주고 재시도, 대체 경로, 상담 전환 기준을 연결해야 한다."),
    "불안": ("확인", "처리 결과를 어떻게 확인시키는가?", "처리 결과, 이력, 알림, 예상 청구 또는 사용 가능 상태를 고객이 직접 확인할 수 있어야 한다."),
    "리스크": ("확인", "처리 결과를 어떻게 확인시키는가?", "처리 결과, 이력, 알림, 예상 청구 또는 사용 가능 상태를 고객이 직접 확인할 수 있어야 한다."),
    "시간": ("효율", "반복 입력과 재문의를 어떻게 줄이는가?", "반복 입력, 회선별 재처리, 동일 문의 재접수를 줄이도록 일괄 처리와 저장된 정보 재사용 기준을 설계해야 한다."),
    "노력": ("효율", "반복 입력과 재문의를 어떻게 줄이는가?", "반복 입력, 회선별 재처리, 동일 문의 재접수를 줄이도록 일괄 처리와 저장된 정보 재사용 기준을 설계해야 한다."),
}


@dataclass
class PainPoint:
    title: str
    category: str
    rate: str
    pain: str
    hidden: str
    trigger: str
    trend: str


@dataclass
class QuickWin:
    rank: str
    item: str
    frequency: str
    effect: str


@dataclass
class VocData:
    doc_id: str
    title: str
    pdf_path: Path
    analysis_period: str
    report_count: str
    counseling_count: str
    sample_count: str
    special_note: str
    pain_points: list[PainPoint]
    hidden_needs: list[str]
    triggers: list[str]
    quick_wins: list[QuickWin]


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def compact(value: str) -> str:
    value = nfc(value)
    value = value.replace("\u00a0", " ")
    value = value.replace("", " ")
    value = re.sub(r"[📊⚠🔴🟠🟡🟢🔵🟣⚫⚡🛠🚀]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def topic_key(value: str) -> str:
    value = nfc(value)
    value = value.replace("_", "/")
    value = re.sub(r"\s+", "", value)
    return value


def source_topic(path: Path) -> str:
    name = nfc(path.name)
    return name.split(" - 고객 VoC 분석")[0].replace(" _ ", " / ")


def load_style() -> str:
    seed = SEED_HTML.read_text(encoding="utf-8")
    match = re.search(r"<style>(.*?)</style>", seed, flags=re.S)
    if not match:
        raise RuntimeError(f"Cannot locate style block in {SEED_HTML}")
    return normalize_trigger_list_style(match.group(1).strip())


def normalize_trigger_list_style(style: str) -> str:
    if "grid-auto-flow:column;" not in style:
        style = style.replace(
            """    .trigger-list {
      display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr));
      gap:8px;""",
            """    .trigger-list {
      display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr));
      grid-template-rows:repeat(10,auto);
      grid-auto-flow:column;
      gap:8px;""",
        )
    if "grid-auto-flow:row;" not in style:
        style = style.replace(
            """      .cover-main { border-right:0; border-bottom:1px solid var(--line); }""",
            """      .trigger-list {
        grid-template-rows:auto;
        grid-auto-flow:row;
      }
      .cover-main { border-right:0; border-bottom:1px solid var(--line); }""",
        )
    return style


def read_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def find_source_pdfs() -> dict[str, Path]:
    pdfs: dict[str, Path] = {}
    for path in SOURCE_DIR.glob("*.pdf"):
        name = nfc(path.name)
        if "고객 VoC 분석" not in name:
            continue
        pdfs[topic_key(source_topic(path))] = path
    return pdfs


def between(text: str, start: str, end: str) -> str:
    start_match = re.search(start, text, flags=re.S)
    if not start_match:
        return ""
    rest = text[start_match.end() :]
    end_match = re.search(end, rest, flags=re.S)
    if end_match:
        rest = rest[: end_match.start()]
    return rest.strip()


def pick(pattern: str, text: str, default: str = "-") -> str:
    match = re.search(pattern, text, flags=re.S)
    if not match:
        return default
    return clean(match.group(1))


def clean(value: str, limit: int | None = None) -> str:
    value = compact(value)
    value = value.strip(" -—:;,.")
    value = value.replace("Pain Point 영역", "Pain Point")
    value = re.sub(r"\s+([,.)%])", r"\1", value)
    value = re.sub(r"([(])\s+", r"\1", value)
    if limit and len(value) > limit:
        cut = value[:limit].rsplit(" ", 1)[0] or value[:limit]
        value = f"{cut}..."
    return value


def sentence_html(value: str) -> str:
    value = clean(value)
    escaped = html.escape(value)
    escaped = re.sub(r"([.!?])\s+", r"\1<br/>", escaped)
    escaped = escaped.replace(" / ", " · ")
    if escaped and not escaped.endswith("<br/>"):
        escaped += "<br/>"
    return escaped


def inline_html(value: str) -> str:
    return html.escape(clean(value))


def parse_meta(text: str) -> tuple[str, str, str, str, str]:
    period = pick(r"분석\s*기간\s+(.+?)\s+주제\s*영역", text)
    reports = pick(r"수집\s*보고서\s*수\s+(.+?)\s+전체\s*상담", text)
    counseling = pick(r"전체\s*상담\s*건수\s*합계\s+(.+?)\s+전체\s*샘플", text)
    samples = pick(r"전체\s*샘플\s*분석\s*건수\s*합계\s+(.+?)\s+분석\s*기간\s*특이사항", text)
    note = pick(r"분석\s*기간\s*특이사항:\s*(.+?)\s+1\.\s*주제", text)
    return period, reports, counseling, samples, note


def parse_pain_points(text: str) -> list[PainPoint]:
    section = between(text, r"1\.\s*주제\s*영역별\s*Pain\s*Point\s*통합\s*분석", r"2\.\s*Pain\s*Point")
    if not section:
        section = text
    markers = list(re.finditer(r"영역\s+(\d+)\.", section))
    points: list[PainPoint] = []
    for index, marker in enumerate(markers):
        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(section)
        chunk = section[start:end].strip()
        header_match = re.search(r"(.+?)\s+누적\s*(?:건수\s*및\s*)?비율:\s*(.+?)(?=Pain\s*Point\s*\(\s*표면\s*\):)", chunk, flags=re.S)
        if not header_match:
            continue
        raw_title = clean(header_match.group(1))
        category = ""
        category_match = re.search(r"\(([^()]+)\)$", raw_title)
        if category_match:
            category = clean(category_match.group(1))
            raw_title = clean(raw_title[: category_match.start()])
        tail = chunk[header_match.end() :]
        pain = pick(r"Pain\s*Point\s*\(\s*표면\s*\):\s*(.+?)(?=Hidden\s*Needs\s*\(\s*심층\s*\):)", tail, "")
        hidden = pick(r"Hidden\s*Needs\s*\(\s*심층\s*\):\s*(.+?)(?=주요\s*Trigger:)", tail, "")
        trigger = pick(r"주요\s*Trigger:\s*(.+?)(?=디지털\s*이탈\s*원인:|트렌드:|$)", tail, "")
        trend = pick(r"트렌드:\s*(.+?)$", tail, "")
        if not pain or not hidden or not trigger:
            continue
        points.append(
            PainPoint(
                title=raw_title,
                category=category,
                rate=clean(header_match.group(2), 120),
                pain=clean(pain, 260),
                hidden=clean(hidden, 220),
                trigger=clean(trigger, 220),
                trend=clean(trend, 180),
            )
        )
    return points


def parse_numbered_items(section: str, max_items: int = 20) -> list[str]:
    items: list[str] = []
    numbered_pattern = re.compile(r"(?<!\d)(\d{1,2})\.\s+(.+?)(?=(?<!\d)\d{1,2}\.\s+|$)", flags=re.S)
    for match in numbered_pattern.finditer(section):
        item = clean(match.group(2), 240)
        if item:
            items.append(item)
        if len(items) >= max_items:
            break
    return items


def parse_hidden_needs(text: str, pain_points: list[PainPoint]) -> list[str]:
    section = between(text, r"3\.\s*Top\s*Hidden\s*Needs", r"4\.\s*주요\s*Trigger")
    items = parse_numbered_items(section, 6)
    if items:
        return items
    return [point.hidden for point in pain_points[:6] if point.hidden]


def parse_triggers(text: str, pain_points: list[PainPoint]) -> list[str]:
    section = between(text, r"4\.\s*주요\s*Trigger", r"5\.\s*Quick\s*Win")
    items = parse_numbered_items(section, 20)
    if items:
        return items
    fallback: list[str] = []
    for point in pain_points:
        fallback.extend([clean(item, 160) for item in re.split(r"\s*/\s*", point.trigger) if clean(item)])
    return fallback[:20]


def parse_quick_wins(text: str) -> list[QuickWin]:
    section = between(text, r"5\.\s*Quick\s*Win", r"6\.\s*전략적")
    section = re.sub(r"^기회\s*통합.+?우선순위\s*개선\s*항목\s*등장\s*빈도\s*기대\s*효과", "", section).strip()
    rank_candidates = [
        (int(match.group(1)), match.start(), match.end())
        for match in re.finditer(r"(?<![\d/.-])\b(\d{1,2})\s+", section)
        if 1 <= int(match.group(1)) <= 10
    ]
    row_starts: list[tuple[int, int, int]] = []
    search_from = 0
    for expected_rank in range(1, 11):
        candidate = next(
            (
                (rank, start, end)
                for rank, start, end in rank_candidates
                if rank == expected_rank and start >= search_from
            ),
            None,
        )
        if candidate is None:
            break
        row_starts.append(candidate)
        search_from = candidate[1] + 1
    frequency_pattern = re.compile(
        r"(전\s*기간\s*전체|전\s*기간\s*지속|전\s*기간\s*최다|전\s*기간\s*1\s*위|전\s*기간\s*주말\s*·\s*공휴일|"
        r"3\s*월\s*초\s*급증|연휴\s*기간\s*집중|설\s*연휴\s*기간\s*집중|삼일절\s*연휴\s*기간\s*집중|"
        r"연휴\s*·\s*주말\s*기간\s*집중|번호이동\s*시즌\s*집중|공휴일\s*·?\s*주말\s*집중|주말\s*·\s*공휴일\s*집중|"
        r"평일\s*복귀\s*시\s*집중|[0-9]{1,2}\s*/\s*[0-9]{1,2}\s*이후\s*매일|"
        r"[0-9]{1,2}\s*일\s*이상|[0-9]{1,2}\s*일\s*전\s*기간)"
        r"|([0-9]{1,2}\s*일\s*전체)"
    )
    wins: list[QuickWin] = []
    for index, (rank, _start, end) in enumerate(row_starts):
        next_start = row_starts[index + 1][1] if index + 1 < len(row_starts) else len(section)
        row = clean(section[end:next_start], 420)
        if not row:
            continue
        frequency = "전 기간"
        effect = "상담 전환과 반복 문의를 줄인다."
        item = row
        freq_match = frequency_pattern.search(row)
        if freq_match:
            item = clean(row[: freq_match.start()], 320)
            frequency = clean(freq_match.group(1) or freq_match.group(2)) or "전 기간"
            effect = clean(row[freq_match.end() :], 160) or effect
        wins.append(QuickWin(rank=str(rank), item=item, frequency=frequency, effect=effect))
        if len(wins) >= 10:
            break
    return wins


def build_voc_data(doc_id: str, title: str, pdf_path: Path) -> VocData:
    text = compact(read_pdf_text(pdf_path))
    period, reports, counseling, samples, note = parse_meta(text)
    pain_points = parse_pain_points(text)
    hidden_needs = parse_hidden_needs(text, pain_points)
    triggers = parse_triggers(text, pain_points)
    quick_wins = parse_quick_wins(text)
    return VocData(
        doc_id=doc_id,
        title=title,
        pdf_path=pdf_path,
        analysis_period=period,
        report_count=reports,
        counseling_count=counseling,
        sample_count=samples,
        special_note=note,
        pain_points=pain_points,
        hidden_needs=hidden_needs,
        triggers=triggers,
        quick_wins=quick_wins,
    )


def conversion_cards(data: VocData) -> list[tuple[str, str, str]]:
    cards: list[tuple[str, str, str]] = []
    used: set[str] = set()
    for point in data.pain_points:
        basis = f"{point.category} {point.title}"
        for keyword, card in POLICY_CONVERSIONS.items():
            if keyword in basis and card[0] not in used:
                cards.append(card)
                used.add(card[0])
                break
        if len(cards) >= 6:
            break
    defaults = [
        ("상태", "처리 상태를 어디까지 보여줘야 하는가?", f"{data.title} 업무의 접수, 진행, 완료, 실패, 취소 상태를 고객이 직접 확인하도록 정의해야 한다."),
        ("알림", "어떤 조건에서 고객에게 먼저 알려야 하는가?", f"{data.title} 관련 변경, 실패, 혜택 영향, 추가 조치 필요 시점을 알림 기준으로 전환해야 한다."),
        ("이력", "고객과 운영자는 무엇을 추적해야 하는가?", f"{data.title} 처리 이력과 고객 고지 이력을 남겨 재문의와 책임 공백을 줄여야 한다."),
        ("예외", "처리 불가 상황에서 어떤 대체 행동을 제공하는가?", "업무 제한 조건을 단순 안내로 끝내지 않고 가능한 대체 처리, 예약, 상담 연결 기준으로 연결해야 한다."),
        ("일괄 처리", "반복 처리를 어떻게 줄이는가?", "동일 고객, 가족, 회선, 상품 단위 반복 업무는 묶음 처리와 공통 결과 확인 기준을 검토해야 한다."),
        ("신뢰", "고객 불안을 어떻게 낮출 것인가?", "예상 결과, 영향 범위, 완료 증적, 실패 복구 경로를 한 흐름 안에 제시해야 한다."),
    ]
    for card in defaults:
        if card[0] not in used:
            cards.append(card)
            used.add(card[0])
        if len(cards) >= 6:
            break
    return cards


def percent_summary(point: PainPoint) -> str:
    matches = re.findall(r"\d+(?:\.\d+)?\s*~\s*\d+(?:\.\d+)?%|\d+(?:\.\d+)?%", point.rate)
    if matches:
        return matches[0].replace(" ", "")
    return clean(point.rate, 24)


def render_metric(value: str, label: str) -> str:
    return f'<div class="metric"><b>{inline_html(value)}</b><span>{inline_html(label)}</span></div>'


def render(data: VocData, style: str) -> str:
    top_points = data.pain_points[:5]
    while len(top_points) < 5:
        top_points.append(PainPoint("반복 상담 구조", "운영", "-", f"{data.title} 업무가 전화 상담으로 반복 이탈한다", f"{data.title} 업무를 셀프 처리 가능한 흐름으로 전환해야 한다", "", ""))

    main_message = (
        f"{data.title} VoC의 핵심은 단일 기능 부족보다 고객이 처리 조건, 영향, 결과를 스스로 확인하지 못해 상담으로 전환되는 데 있다."
    )
    if data.pain_points:
        main_message += f" 가장 큰 병목은 {data.pain_points[0].title}이며, 통합채널은 이를 탐색, 판단, 실행, 확인, 복구가 연결된 업무 경험으로 재설계해야 한다."

    trend_message = data.special_note or f"{data.title} 상담은 업무 가능 시간, 상태 확인, 권한 조건, 결과 고지의 빈틈에서 반복적으로 발생한다."

    metrics = [
        render_metric(percent_summary(top_points[0]), clean(top_points[0].title, 18)),
        render_metric(percent_summary(top_points[1]), clean(top_points[1].title, 18)),
        render_metric(percent_summary(top_points[2]), clean(top_points[2].title, 18)),
        render_metric(percent_summary(top_points[3]), clean(top_points[3].title, 18)),
    ]

    signal_cards = []
    tones = ["", " t2", " t3", " t4", " t5"]
    for idx, point in enumerate(top_points[:5], start=1):
        signal_cards.append(
            f'''          <article class="signal{tones[idx - 1]}">
            <span>{idx:02d}</span>
            <h3>{inline_html(point.title)}</h3>
            <p>{sentence_html(point.hidden or point.pain)}</p>
          </article>'''
        )

    pain_rows = []
    for point in data.pain_points:
        label_html = inline_html(point.title)
        if point.category:
            label_html += f"<br/><small>{inline_html(point.category)}</small>"
        policy_meaning = conversion_cards(VocData(data.doc_id, data.title, data.pdf_path, "", "", "", "", "", [point], [], [], []))[0][2]
        pain_rows.append(
            f'''            <tr>
              <td>{label_html}</td>
              <td><span class="rate">{inline_html(percent_summary(point))}</span></td>
              <td>{sentence_html(point.pain)}</td>
              <td>{sentence_html(policy_meaning)}</td>
            </tr>'''
        )

    hidden_cards = []
    labels = ["안심", "통제", "즉시", "이해", "연계", "복구"]
    for idx, need in enumerate(data.hidden_needs[:6]):
        title = clean(need.split("→", 1)[0], 140)
        desc = clean(need.split("→", 1)[1] if "→" in need else need, 180)
        hidden_cards.append(
            f'''          <article class="card">
            <b>{inline_html(labels[idx] if idx < len(labels) else f"Need {idx + 1}")}</b>
            <h3>{inline_html(title)}</h3>
            <p>{sentence_html(desc)}</p>
          </article>'''
        )

    trigger_items = []
    for idx, trigger in enumerate(data.triggers[:20], start=1):
        trigger_items.append(f'          <li><b>{idx:02d}</b><span>{inline_html(trigger)}</span></li>')

    quick_rows = []
    for win in data.quick_wins[:10]:
        quick_rows.append(
            f'''            <tr>
              <td>{inline_html(win.rank)}</td>
              <td>{inline_html(win.item)}</td>
              <td>{inline_html(win.frequency)}</td>
              <td>{inline_html(win.effect)}</td>
            </tr>'''
        )
    if not quick_rows:
        quick_rows.append(
            f'''            <tr>
              <td>1</td>
              <td>{inline_html(data.title)} 업무의 진입점, 상태 확인, 처리 결과 안내를 한 화면에서 제공</td>
              <td>전 기간</td>
              <td>탐색 실패와 처리 결과 확인 상담을 줄인다.</td>
            </tr>'''
        )

    policy_cards = []
    for label, question, desc in conversion_cards(data):
        policy_cards.append(
            f'''          <article class="card">
            <b>{inline_html(label)}</b>
            <h3>{inline_html(question)}</h3>
            <p>{sentence_html(desc)}</p>
          </article>'''
        )

    return f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{inline_html(data.title)} · VoC 분석</title>
  <style>
{style}
  </style>
</head>
<body>
  <main class="page">
    <div class="cover">
      <header class="cover-main">
        <div class="kicker">VOC analysis readout</div>
        <h1>{inline_html(data.title)} VoC 분석</h1>
        <p class="lead">{sentence_html(main_message)}</p>
        <div class="chips">
          <span>분석 기간 {inline_html(data.analysis_period)}</span>
          <span>보고서 {inline_html(data.report_count)}</span>
          <span>상담 {inline_html(data.counseling_count)}</span>
          <span>샘플 {inline_html(data.sample_count)}</span>
        </div>
      </header>
      <aside class="cover-side">
        <div class="side-head">
          <b>Executive readout</b>
          <span>인지 · 탐색 · 권한 · 복구</span>
        </div>
        <div class="side-body">
          <strong>{inline_html(data.title)} 상담은 고객이 직접 끝내지 못하는 확인과 예외 처리 지점에서 반복된다.</strong>
          <p>{sentence_html(trend_message)}</p>
          <div class="metric-strip">
            {chr(10).join(metrics)}
          </div>
        </div>
      </aside>
    </div>

    <section>
      <div class="section-head">
        <div>
          <h2>1. 핵심 신호</h2>
          <p>{data.title} VoC는 고객이 업무를 시작하고, 조건을 이해하고, 결과를 확인하고, 실패를 복구하는 전체 흐름을 정책 기준으로 재설계해야 함을 보여준다.<br/></p>
        </div>
        <span class="section-label">Core signals</span>
      </div>
      <div class="content">
        <div class="signal-grid">
{chr(10).join(signal_cards)}
        </div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>2. Pain Point 포트폴리오</h2>
          <p>상담 유형은 단순 문의가 아니라 탐색 실패, 이해 부족, 권한 제약, 시스템 단절, 처리 결과 불안으로 반복된다.<br/></p>
        </div>
        <span class="section-label">Pain portfolio</span>
      </div>
      <div class="content">
        <table class="heat-table">
          <thead>
            <tr>
              <th>유형</th>
              <th>누적 비율</th>
              <th>고객이 겪는 문제</th>
              <th>통합채널 설계 의미</th>
            </tr>
          </thead>
          <tbody>
{chr(10).join(pain_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>3. Hidden Needs</h2>
          <p>표면 요청 뒤에는 고객이 직접 판단하고 처리 결과를 신뢰하고 싶은 요구가 숨어 있다.<br/></p>
        </div>
        <span class="section-label">Hidden needs</span>
      </div>
      <div class="content">
        <div class="need-grid">
{chr(10).join(hidden_cards)}
        </div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>4. Trigger Top 20</h2>
          <p>아래 계기는 고객이 셀프 채널을 이탈해 상담으로 전환하는 실제 출발점이다.<br/></p>
        </div>
        <span class="section-label">Triggers</span>
      </div>
      <div class="content">
        <ol class="trigger-list">
{chr(10).join(trigger_items)}
        </ol>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>5. Quick Win</h2>
          <p>즉시 개선 가능한 항목은 진입점 노출, 완료 안내, 상태 조회, 권한 처리, 실패 복구를 중심으로 정리된다.<br/></p>
        </div>
        <span class="section-label">Immediate actions</span>
      </div>
      <div class="content">
        <table class="heat-table quick-table">
          <thead>
            <tr>
              <th>순위</th>
              <th>개선 항목</th>
              <th>등장 빈도</th>
              <th>기대 효과</th>
            </tr>
          </thead>
          <tbody>
{chr(10).join(quick_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>6. 요구사항·정책서 전환 질문</h2>
          <p>VoC 분석 결과는 {data.title} 정책서에서 아래 질문에 답할 수 있는 기능과 정책 항목으로 전환되어야 한다.<br/></p>
        </div>
        <span class="section-label">Policy conversion</span>
      </div>
      <div class="content">
        <div class="policy-grid">
{chr(10).join(policy_cards)}
        </div>
      </div>
    </section>
  </main>
</body>
</html>
'''


def classify_pain_point(point: PainPoint) -> str:
    basis = f"{point.title} {point.category}"
    rules = [
        ("탐색·발견", ["탐색", "발견", "경로", "메뉴", "조회", "찾"]),
        ("인지·이해", ["인지", "이해", "혼란", "구조", "금액", "요금", "혜택", "정책"]),
        ("인증·권한", ["인증", "권한", "명의", "가족", "대리", "미성년", "법인"]),
        ("프로세스 단절", ["프로세스", "단절", "채널", "부서", "연계", "통합"]),
        ("정책 제약", ["정책", "제약", "휴일", "야간", "주말", "공휴일", "불가"]),
        ("시스템·오류", ["시스템", "오류", "미수신", "실패", "반영", "복구"]),
        ("불안·리스크", ["불안", "리스크", "분실", "미납", "정지", "해지", "피해"]),
        ("시간·노력", ["시간", "노력", "반복", "일괄", "다회선", "복합"]),
    ]
    for label, keywords in rules:
        if any(keyword in basis for keyword in keywords):
            return label
    return "기타"


def render_summary(datasets: list[VocData], style: str) -> str:
    total_pain = sum(len(data.pain_points) for data in datasets)
    total_triggers = sum(min(20, len(data.triggers)) for data in datasets)
    total_quick = sum(min(10, len(data.quick_wins)) for data in datasets)

    category_counts: Counter[str] = Counter()
    category_examples: dict[str, list[str]] = defaultdict(list)
    for data in datasets:
        for point in data.pain_points:
            category = classify_pain_point(point)
            category_counts[category] += 1
            if len(category_examples[category]) < 3:
                category_examples[category].append(f"{data.title}: {point.title}")

    top_categories = category_counts.most_common()
    pain_rows = []
    for category, count in top_categories:
        examples = "<br/>".join(inline_html(example) for example in category_examples[category])
        pain_rows.append(
            f'''            <tr>
              <td>{inline_html(category)}</td>
              <td><span class="rate">{count}개</span></td>
              <td>{examples}</td>
              <td>{sentence_html(summary_policy_meaning(category))}</td>
            </tr>'''
        )

    signal_cards = [
        ("01", "탐색 실패가 상담의 시작점이다.", "업무 메뉴를 찾지 못하거나 현재 상태에서 가능한 다음 행동이 보이지 않아 상담으로 전환된다."),
        ("02", "적용 시점과 영향도 설명이 부족하다.", "요금, 혜택, 할인, 납부, 정지, 구독처럼 고객 손익에 영향을 주는 변화가 처리 전에 충분히 설명되지 않는다."),
        ("03", "가족·대리·법인 처리가 반복적으로 막힌다.", "본인 외 처리 수요가 크지만 권한, 동의, 인증 경로가 업무별로 끊겨 있다."),
        ("04", "휴일·야간·부서 분리가 이탈을 만든다.", "처리 불가 시간대와 조직 분리로 고객은 가능한 업무와 불가능한 업무를 구분하지 못한다."),
        ("05", "처리 결과 확인 부재가 불안을 키운다.", "접수, 반영, 실패, 취소, 재처리 상태를 볼 수 없어 고객은 같은 문의를 반복한다."),
    ]
    signal_html = []
    tones = ["", " t2", " t3", " t4", " t5"]
    for idx, (number, title, desc) in enumerate(signal_cards):
        signal_html.append(
            f'''          <article class="signal{tones[idx]}">
            <span>{number}</span>
            <h3>{inline_html(title)}</h3>
            <p>{sentence_html(desc)}</p>
          </article>'''
        )

    hidden_cards = [
        ("정보 통제", "처리 전 영향도를 알고 싶다.", "고객은 신청, 변경, 해지, 정지 전에 요금, 혜택, 제한, 적용 시점을 먼저 확인하고 싶어 한다."),
        ("즉시 처리", "전화 없이 바로 끝내고 싶다.", "반복 문의의 상당수는 앱에서 직접 처리할 수 있는 진입점과 완료 확인이 부족해서 발생한다."),
        ("가족 관리", "가족 회선을 한 번에 관리하고 싶다.", "자녀, 배우자, 부모 회선의 권한 위임과 동의 처리가 통합채널 공통 과제로 반복된다."),
        ("안심 확인", "처리 결과를 증적으로 보고 싶다.", "완료 화면, 알림, 이력, 상태 타임라인이 없으면 고객은 정상 처리 여부를 상담으로 확인한다."),
        ("복구", "실패 후 다음 행동을 알고 싶다.", "오류, 미납, 결제 실패, 인증 실패는 원인 안내보다 재시도와 대체 경로 제공이 중요하다."),
        ("일관성", "채널마다 말이 달라지지 않길 원한다.", "앱, 상담, 대리점, 외부기관 안내가 같은 기준으로 연결되어야 한다."),
    ]
    hidden_html = [
        f'''          <article class="card">
            <b>{inline_html(label)}</b>
            <h3>{inline_html(title)}</h3>
            <p>{sentence_html(desc)}</p>
          </article>'''
        for label, title, desc in hidden_cards
    ]

    trigger_pool: list[str] = []
    for offset in range(3):
        for data in datasets:
            if len(data.triggers) > offset:
                trigger_pool.append(f"{data.title}: {data.triggers[offset]}")
            if len(trigger_pool) >= 20:
                break
        if len(trigger_pool) >= 20:
            break
    trigger_items = [
        f'          <li><b>{idx:02d}</b><span>{inline_html(trigger)}</span></li>'
        for idx, trigger in enumerate(trigger_pool[:20], start=1)
    ]

    quick_rows = []
    for idx, data in enumerate(datasets[:12], start=1):
        win = data.quick_wins[0] if data.quick_wins else QuickWin(str(idx), f"{data.title} 업무의 상태 확인과 완료 안내 강화", "전 기간", "반복 상담 감소")
        quick_rows.append(
            f'''            <tr>
              <td>{idx}</td>
              <td>{inline_html(data.title)} · {inline_html(win.item)}</td>
              <td>{inline_html(win.frequency)}</td>
              <td>{inline_html(win.effect)}</td>
            </tr>'''
        )

    policy_cards = [
        ("공통 진입점", "업무별 시작점은 어디에 놓을 것인가?", "요금, 상품, 가입, 주문, 고객지원 업무의 대표 진입점을 통합채널 홈과 마이 영역에서 일관되게 제공해야 한다."),
        ("영향도 확인", "처리 전에 무엇을 비교해야 하는가?", "요금 변동, 혜택 소멸, 할인 변화, 약정, 납부, 정지 영향을 처리 전 미리보기로 제공해야 한다."),
        ("권한·동의", "누가 대신 처리할 수 있는가?", "가족, 법정대리인, 법인, 타인 명의 결제수단의 권한 기준을 업무별로 분리하지 말고 공통 정책으로 설계해야 한다."),
        ("상태·이력", "고객에게 어디까지 보여줄 것인가?", "접수, 처리 중, 반영 완료, 실패, 취소, 재처리 상태와 고객 고지 이력을 남겨야 한다."),
        ("예외·복구", "처리 불가 시 어떤 대체 행동을 줄 것인가?", "휴일, 야간, 인증 실패, 외부 연동 실패 시 예약, 재시도, 대체 납부, 상담 연결 기준을 제공해야 한다."),
        ("채널 정합성", "앱·상담·대리점 안내는 어떻게 맞출 것인가?", "동일 업무의 정책값과 안내 문구가 채널마다 달라지지 않도록 기준 데이터와 설명을 통합 관리해야 한다."),
    ]
    policy_html = [
        f'''          <article class="card">
            <b>{inline_html(label)}</b>
            <h3>{inline_html(question)}</h3>
            <p>{sentence_html(desc)}</p>
          </article>'''
        for label, question, desc in policy_cards
    ]

    return f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>종합 · VoC 분석</title>
  <style>
{style}
  </style>
</head>
<body>
  <main class="page">
    <div class="cover">
      <header class="cover-main">
        <div class="kicker">VOC integrated readout</div>
        <h1>VoC 분석 종합</h1>
        <p class="lead">25개 VoC 분석을 통합하면 고객 상담은 단일 기능 부족보다 탐색, 이해, 권한, 상태 확인, 실패 복구가 끊어지는 지점에서 반복된다.<br/>통합채널은 각 업무를 별도 메뉴로 늘리는 방식이 아니라 고객 과업의 시작, 판단, 실행, 확인, 복구를 하나의 운영 기준으로 묶어야 한다.<br/></p>
        <div class="chips">
          <span>분석 주제 {len(datasets)}개</span>
          <span>Pain Point {total_pain}개</span>
          <span>Trigger {total_triggers}개</span>
          <span>Quick Win {total_quick}개</span>
        </div>
      </header>
      <aside class="cover-side">
        <div class="side-head">
          <b>Executive readout</b>
          <span>탐색 · 이해 · 권한 · 복구</span>
        </div>
        <div class="side-body">
          <strong>반복 상담을 줄이려면 업무별 화면보다 공통 처리 기준을 먼저 설계해야 한다.</strong>
          <p>상담을 유발하는 패턴은 주제별로 달라도 원인은 유사하다.<br/>고객은 어디서 시작할지 모르고, 처리 전 영향을 이해하지 못하며, 결과를 확인하지 못할 때 다시 상담으로 돌아온다.<br/></p>
          <div class="metric-strip">
            {render_metric(str(len(datasets)), "분석 주제")}
            {render_metric(str(total_pain), "Pain Point")}
            {render_metric(str(total_triggers), "Trigger")}
            {render_metric(str(total_quick), "Quick Win")}
          </div>
        </div>
      </aside>
    </div>

    <section>
      <div class="section-head">
        <div>
          <h2>1. 종합 핵심 신호</h2>
          <p>전체 VoC는 고객이 업무를 시작하기 전과 완료한 후의 확인 지점이 약할수록 상담이 반복된다는 공통 신호를 보인다.<br/></p>
        </div>
        <span class="section-label">Core signals</span>
      </div>
      <div class="content">
        <div class="signal-grid">
{chr(10).join(signal_html)}
        </div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>2. Pain Point 통합 분포</h2>
          <p>주제는 다르지만 상담 발생 구조는 탐색, 이해, 권한, 프로세스 단절, 정책 제약, 오류 복구로 수렴한다.<br/></p>
        </div>
        <span class="section-label">Pain portfolio</span>
      </div>
      <div class="content">
        <table class="heat-table">
          <thead>
            <tr>
              <th>유형</th>
              <th>건수</th>
              <th>대표 사례</th>
              <th>정책서 전환 의미</th>
            </tr>
          </thead>
          <tbody>
{chr(10).join(pain_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>3. 공통 Hidden Needs</h2>
          <p>주제별 요청은 달라도 고객의 심층 요구는 정보 통제, 즉시 처리, 가족 관리, 안심 확인, 실패 복구로 반복된다.<br/></p>
        </div>
        <span class="section-label">Hidden needs</span>
      </div>
      <div class="content">
        <div class="need-grid">
{chr(10).join(hidden_html)}
        </div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>4. 반복 Trigger</h2>
          <p>상담을 직접 유발하는 계기는 변경 후 문자, 미반영 불안, 혜택 소멸, 앱 경로 부재, 가족 처리 실패로 반복된다.<br/></p>
        </div>
        <span class="section-label">Triggers</span>
      </div>
      <div class="content">
        <ol class="trigger-list">
{chr(10).join(trigger_items)}
        </ol>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>5. Quick Win 포트폴리오</h2>
          <p>즉시 개선 후보는 주제별 1순위 항목을 기준으로 정리했다.<br/>대부분 진입점 노출, 완료 안내, 상태 조회, 영향도 고지에 집중된다.<br/></p>
        </div>
        <span class="section-label">Immediate actions</span>
      </div>
      <div class="content">
        <table class="heat-table quick-table">
          <thead>
            <tr>
              <th>순위</th>
              <th>개선 항목</th>
              <th>등장 빈도</th>
              <th>기대 효과</th>
            </tr>
          </thead>
          <tbody>
{chr(10).join(quick_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>6. 요구사항·정책서 전환 관점</h2>
          <p>VoC 종합 결과는 개별 요구사항을 화면 기능으로만 옮기지 말고 공통 정책 축으로 전환해야 한다.<br/></p>
        </div>
        <span class="section-label">Policy conversion</span>
      </div>
      <div class="content">
        <div class="policy-grid">
{chr(10).join(policy_html)}
        </div>
      </div>
    </section>
  </main>
</body>
</html>
'''


def summary_policy_meaning(category: str) -> str:
    mapping = {
        "탐색·발견": "업무 진입점, 검색어, 홈·마이 노출 기준을 공통 정책으로 정의해야 한다.",
        "인지·이해": "처리 전 영향도, 예상 금액, 혜택 변화, 적용 시점을 고객 언어로 설명해야 한다.",
        "인증·권한": "본인, 가족, 대리, 법인, 미성년자 처리 권한과 동의 기준을 분리해 정의해야 한다.",
        "프로세스 단절": "앱, 상담, 대리점, 외부기관의 처리 상태를 하나의 업무 흐름으로 연결해야 한다.",
        "정책 제약": "야간, 휴일, 공휴일, 마감 시점의 처리 가능 범위와 대체 행동을 정해야 한다.",
        "시스템·오류": "오류와 실패를 안내로 끝내지 않고 재시도, 대체 경로, 상태 추적까지 연결해야 한다.",
        "불안·리스크": "고객 손실 가능성이 있는 업무는 결과 확인, 이력, 알림 기준을 강화해야 한다.",
        "시간·노력": "반복 입력과 회선별 반복 처리를 줄이는 일괄 처리 기준을 검토해야 한다.",
    }
    return mapping.get(category, "주제별 예외를 공통 정책 항목으로 전환할지 검토해야 한다.")


def build(include_first: bool = False) -> list[Path]:
    style = load_style()
    source_pdfs = find_source_pdfs()
    written: list[Path] = []
    all_data: list[VocData] = []
    for doc_id, title in VOC_DOCUMENTS:
        pdf = source_pdfs.get(topic_key(title))
        if not pdf:
            raise FileNotFoundError(f"Cannot find VoC PDF for {title}")
        all_data.append(build_voc_data(doc_id, title, pdf))

    summary_path = OUTPUT_DIR / f"{VOC_SUMMARY[0]}.html"
    summary_path.write_text(render_summary(all_data, style), encoding="utf-8")
    written.append(summary_path)

    for doc_id, title in VOC_DOCUMENTS:
        if not include_first and doc_id == "voc-auto-payment-apply-change":
            continue
        data = next(item for item in all_data if item.doc_id == doc_id)
        if len(data.pain_points) < 3:
            raise RuntimeError(f"{title}: only {len(data.pain_points)} pain points parsed")
        if len(data.triggers) < 10:
            raise RuntimeError(f"{title}: only {len(data.triggers)} triggers parsed")
        output_path = OUTPUT_DIR / f"{doc_id}.html"
        output_path.write_text(render(data, style), encoding="utf-8")
        written.append(output_path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-first", action="store_true", help="also regenerate the first hand-curated VoC page")
    args = parser.parse_args()
    written = build(include_first=args.include_first)
    for path in written:
        print(path.relative_to(ROOT))
    print(f"generated {len(written)} file(s)")


if __name__ == "__main__":
    main()
