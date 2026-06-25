"""Structured policy document writer for NC integrated-channel policies."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import List, Sequence

try:
    from renderer import build_state_static_diagram
except ImportError:  # pragma: no cover - package import fallback.
    from .renderer import build_state_static_diagram


@dataclass(frozen=True)
class TopicProfile:
    domain: str
    purpose: str
    customer_value: str
    primary_object: str
    action: str
    risk_focus: str
    systems: Sequence[str]
    extra_terms: Sequence[tuple[str, str]]


@dataclass(frozen=True)
class PolicyGroup:
    code: str
    name: str
    description: str
    items: Sequence[tuple[str, str]]


def build_policy_document(ctx, template_html: str, stage_key: str = "04") -> str:
    """Build a policy document body using the uploaded template's CSS."""
    profile = build_topic_profile(ctx.topic)
    style = extract_style(template_html)
    doc_label = "Full" if ctx.template_type == "full" else "간소화"
    stage_rank = section_rank(stage_key)

    body_sections: List[str] = [cover_section(ctx, doc_label)]
    if stage_rank >= 2:
        body_sections.append(history_section(ctx, doc_label))
    if stage_rank >= 3:
        body_sections.append(overview_section(ctx, profile))
    if stage_rank >= 4:
        body_sections.append(terms_section(ctx, profile))
    if stage_rank >= 5:
        body_sections.append(usecase_section(ctx, profile))
    if stage_rank >= 6:
        body_sections.append(process_section(ctx, profile))
    if stage_rank >= 7:
        body_sections.append(functions_section(ctx, profile))
    if stage_rank >= 8:
        body_sections.append(policies_section(ctx, profile))
    if stage_rank >= 9:
        body_sections.append(final_check_section(ctx, profile))

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1" name="viewport"/>
<title>{esc(ctx.topic)} 정책서 {doc_label} {ctx.version}</title>
{style}
{policy_detail_style()}
</head>
<body>
<div class="page">
{''.join(body_sections)}
</div>
</body>
</html>
"""


def section_rank(stage_key: str) -> int:
    if stage_key.isdigit():
        return int(stage_key)
    match = re.match(r"(?P<rank>\d+)_", stage_key)
    if match:
        return int(match.group("rank"))
    return 9 if stage_key == "full" else 4


def extract_style(template_html: str) -> str:
    match = re.search(r"<style>.*?</style>", template_html, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(0)
    return """<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", Arial, sans-serif; margin: 0; background: #f5f7fa; color: #111827; }
.page { width: 1180px; margin: 28px auto; background: #fff; padding: 52px 60px 64px 60px; box-shadow: 0 6px 24px rgba(0,0,0,.08); border-radius: 12px; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; margin-bottom: 14px; }
th, td { border: 1px solid #d9dde3; padding: 12px 14px; text-align: left; vertical-align: top; word-break: keep-all; line-height: 1.6; }
th { background: #f3f5f7; font-weight: 600; }
.plain-text, .principle-text { font-size: 15px; line-height: 1.75; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; }
.center { text-align: center; font-weight: 600; }
</style>"""


def policy_detail_style() -> str:
    return """<style>
.meta th { width: 180px !important; }
.meta td { width: auto !important; }
.policy-group { margin: 6px 0 22px; }
.policy-item { margin: 0 0 16px; }
.policy-item + .policy-item { margin-top: 14px; }
.policy-item-title { margin: 0 0 6px; font-weight: 700; line-height: 1.55; }
.policy-item-content { margin: 0 0 0 18px; padding-left: 12px; border-left: 2px solid #e5edf7; color: #111827; line-height: 1.72; }
.policy-item-line { display: block; margin: 3px 0; }
</style>"""


def build_topic_profile(topic: str) -> TopicProfile:
    compact = topic.replace(" ", "")

    if any(keyword in compact for keyword in ["AI검색", "추천", "데이터트래킹"]):
        return TopicProfile(
            domain="탐색·추천·데이터",
            purpose=f"{topic}은 고객의 탐색 의도, 이용 맥락, 채널 행동 데이터를 기반으로 적절한 정보와 후속 업무 경로를 제공하는 업무다.",
            customer_value="고객이 메뉴 구조를 몰라도 목적에 맞는 정보와 업무 경로를 빠르게 찾을 수 있게 한다.",
            primary_object="탐색 결과와 추천 기준",
            action="조회·추천·후속 업무 연결",
            risk_focus="개인화 정보 활용, 신뢰도 낮은 답변, 민감정보 노출, 부정확한 업무 연결",
            systems=("AI/추천 시스템", "지식 베이스", "BSS", "채널 업무 시스템", "로그·분석 시스템"),
            extra_terms=(
                ("의도 분류", "고객 입력 또는 행동을 정보 확인, 상품 탐색, 업무 처리, 상담 연결 등 목적 유형으로 나누는 처리"),
                ("신뢰도", "결과가 고객 의도와 근거 정보에 부합하는지 판단하는 내부 기준"),
                ("개인화 기준", "고객 상태, 동의, 권한, 이용 맥락에 따라 결과 노출 범위를 조정하는 기준"),
                ("품질 피드백", "고객 또는 운영자가 결과의 적합성, 정확성, 유용성을 평가하는 정보"),
            ),
        )

    if any(
        keyword in compact
        for keyword in [
            "상품",
            "전시",
            "담기",
            "카트",
            "장바구니",
            "주문",
            "계약",
            "가입",
            "결제",
            "배송",
            "교환",
            "반품",
            "쿠폰",
            "포인트",
            "멤버십",
            "이벤트",
            "미션",
            "할인",
            "선물",
        ]
    ):
        return TopicProfile(
            domain="상품·주문·혜택",
            purpose=f"{topic}은 고객이 상품과 혜택 조건을 확인하고, 선택·신청·주문·결제 등 후속 업무로 이어갈 수 있도록 기준을 정의하는 업무다.",
            customer_value="고객이 상품 조건, 혜택, 비용, 제한 사유를 이해한 뒤 스스로 다음 행동을 결정할 수 있게 한다.",
            primary_object="상품·혜택·주문 대상",
            action="조회·선택·신청·처리",
            risk_focus="가격·혜택 오인, 중복 할인, 재고·가입 조건 불일치, 결제·주문 실패",
            systems=("상품 마스터", "BSS", "주문 시스템", "결제 시스템", "혜택·쿠폰 시스템"),
            extra_terms=(
                ("상품 기준 정보", "상품명, 제공 내용, 가격, 혜택, 제한 조건, 신청 가능 상태를 판단하는 기준 정보"),
                ("적용 가능 혜택", "고객 상태와 상품 조건에 따라 실제 적용 가능한 할인, 쿠폰, 포인트, 멤버십 혜택"),
                ("주문 가능 조건", "고객 상태, 상품 상태, 재고, 인증, 약관, 결제 가능 여부가 모두 충족된 상태"),
                ("가격·혜택 영향도", "선택 또는 변경 전 고객에게 고지해야 하는 요금, 할인, 포인트, 쿠폰, 약정 영향"),
            ),
        )

    if any(
        keyword in compact
        for keyword in ["요금", "납부", "회선", "데이터", "통화", "회원", "알림", "약관", "상담", "문의", "FAQ", "공지", "매장", "설정"]
    ):
        return TopicProfile(
            domain="고객·회선·지원",
            purpose=f"{topic}은 고객의 가입 상태, 회선, 요금, 이용 정보, 문의 흐름을 기준으로 조회·변경·처리 기준을 정의하는 업무다.",
            customer_value="고객이 본인의 상태와 처리 가능 조건을 이해하고, 필요한 조회·변경·상담 업무를 끊김 없이 수행할 수 있게 한다.",
            primary_object="고객·회선·요금 정보",
            action="조회·변경·상담 연결",
            risk_focus="본인확인 누락, 권한 없는 정보 노출, 요금·회선 영향 오안내, 상담 전환 누락",
            systems=("BSS", "인증 시스템", "청구 시스템", "상담 시스템", "알림 시스템"),
            extra_terms=(
                ("고객 상태", "정상, 제한, 해지, 일시정지, 미납, 인증 필요 등 업무 가능 여부에 영향을 주는 고객 조건"),
                ("회선 기준", "업무 대상이 되는 이동전화, 인터넷, IPTV, 결합, 부가서비스 등 가입 단위 기준"),
                ("청구·납부 기준", "요금 안내, 납부, 미납, 실시간 이용 요금, 납부 수단 처리에 적용하는 기준"),
                ("상담 전환", "셀프 처리로 완료하기 어렵거나 정책상 제한되는 경우 상담 채널로 연결하는 처리"),
            ),
        )

    return TopicProfile(
        domain="공통·운영·품질",
        purpose=f"{topic}은 통합채널 전반에 공통으로 적용되는 운영 기준, 품질 기준, 관리 기준을 정의하는 업무다.",
        customer_value="고객이 채널 전반에서 일관된 기준과 품질로 정보를 확인하고 업무를 완료할 수 있게 한다.",
        primary_object="공통 운영 기준",
        action="기준 관리·검증·모니터링",
        risk_focus="기준 불일치, 품질 저하, 운영 변경 이력 누락, 데이터 추적 기준 불명확",
        systems=("채널 관리 시스템", "BSS", "운영 관리 시스템", "로그·분석 시스템", "품질 모니터링 시스템"),
        extra_terms=(
            ("공통 기준", "여러 업무에 반복 적용되는 표시, 검증, 인증, 이력, 운영 관리 기준"),
            ("품질 기준", "정확성, 완결성, 응답성, 접근성, 안정성을 판단하기 위한 관리 기준"),
            ("적응형 처리", "고객 상태, 기기, 채널 맥락, 업무 조건에 따라 안내와 처리 경로를 조정하는 방식"),
            ("운영 변경 이력", "기준값, 노출 조건, 품질 기준, 관리 정책이 바뀐 내역을 추적하기 위한 기록"),
        ),
    )


def cover_section(ctx, doc_label: str) -> str:
    version_label = f"{doc_label} {ctx.version}" if doc_label == "Full" else f"간소화 {ctx.version}"
    authoring_basis_row = tr(th("작성 기준"), td(authoring_basis_text(ctx)))

    return f"""
<div class="eyebrow">통합채널 정책서 {doc_label} 버전</div>
<h1>{esc(ctx.topic)} 정책서</h1>
<table class="meta">
{tr(th("정책서 ID"), td(f"POL-{ctx.business_code}", 'mono'))}
{tr(th("문서 구분"), td(f"{doc_label} 버전"))}
{tr(th("문서 상태"), td(esc(ctx.status)))}
{tr(th("버전"), td(version_label, 'mono'))}
{tr(th("작성자"), td(f"SK Telecom 플랫폼기획 2팀 / {esc(ctx.author)}"))}
{tr(th("작성일"), td(ctx.today))}
{authoring_basis_row}
</table>
"""


def history_section(ctx, doc_label: str) -> str:
    brief = f" 작성 요청 메모는 “{esc(ctx.brief)}”로 기록한다." if ctx.brief.strip() else ""
    requirement_note = " 요구사항 통합 list를 검토해 정의해야 할 처리 기준을 분석한다." if requirements_for(ctx) else " 매칭된 요구사항이 없으면 공통 작성 기준을 우선 적용한다."
    reference_note = " references 자료를 검토해 채널 전략, 고객 불편, IA, 벤치마킹 관점을 반영한다." if references_for(ctx) else " references 자료가 없으면 AGENTS.md와 샘플 기준을 우선 적용한다."
    return f"""
<h2>0. 문서 히스토리</h2>
<table>
<thead>{tr(th("버전", style="width: 90px;"), th("변경 내용"), th("변경일자", style="width: 120px;"), th("변경자", style="width: 180px;"))}</thead>
<tbody>
{tr(td(f"{doc_label} {ctx.version}" if doc_label == "Full" else f"간소화 {ctx.version}"), td(f"{esc(ctx.topic)} 정책서 초안 작성. 표지, 문서 히스토리, 개요, 주요 용어, 액터, 유즈케이스, 상태 전이, 프로세스, 기능, 정책 목록, 정책 상세를 작성한다.{requirement_note}{reference_note}{brief}"), td(ctx.today), td(esc(ctx.author)))}
</tbody>
</table>
"""


def overview_section(ctx, profile: TopicProfile) -> str:
    topic = esc(ctx.topic)
    return f"""
<h2>1. 개요</h2>
<h3>가. 범위</h3>
<p class="plain-text">본 정책서는 통합채널에서 제공하는 <b>{topic}</b> 업무에 대한 처리 기준을 정의한다.<br/>{esc(profile.purpose)}</p>
<p class="plain-text">대상 채널은 앱·웹 FO를 기준으로 하며, 고객이 직접 조회·선택·신청·변경·확인하는 셀프 처리 흐름을 우선 범위로 한다.<br/>대상 고객은 통합채널을 이용하는 고객으로 하며, 로그인 여부, 본인확인 여부, 보유 회선, 가입 상품, 약관 동의, 고객 상태에 따라 노출 범위와 처리 가능 범위를 다르게 적용한다.</p>
<p class="plain-text">본 문서는 {topic}의 유즈케이스, 상태 전이, 프로세스, 주요 기능, 정책 목록, 정책 상세를 정의한다.<br/>화면 UI 상세, 문구 상세, API 필드, DB 컬럼, 배치 설계, 운영자 화면 상세, 비기능 상세는 본 문서에서 다루지 않는다.<br/>다만 처리 가능 여부, 고객 고지, 인증·동의, 이력 저장, 연계 결과 반영처럼 정책 판단에 직접 영향을 주는 기준은 본 문서에 포함한다.</p>
<p class="plain-text">{esc(profile.customer_value)}<br/>따라서 {topic}은 채널 화면의 단순 기능이 아니라 고객 과업을 완료시키기 위한 업무 구조, 시스템 판단, 정책 기준이 함께 정의되어야 한다.</p>
<h3>나. 설계 원칙</h3>
<p class="principle-text">• <b>고객 과업 중심</b>: {topic}은 내부 시스템 단위가 아니라 고객이 해결하려는 목적과 완료 상태를 기준으로 구성한다.</p>
<p class="principle-text">• <b>셀프 처리 우선</b>: 고객이 앱·웹에서 직접 확인하고 처리할 수 있는 업무는 상담 전환보다 셀프 처리 경로를 우선 제공한다.</p>
<p class="principle-text">• <b>BSS 판단 통합</b>: 고객 상태, 가입 상품, 요금, 혜택, 제한 조건, 처리 결과처럼 BSS 또는 연계 시스템의 판단이 필요한 정보는 프로세스와 정책에 포함한다.</p>
<p class="principle-text">• <b>영향도 사전 고지</b>: 고객의 비용, 혜택, 약정, 포인트, 쿠폰, 회선, 주문 상태에 영향이 있는 경우 처리 전에 예상 영향과 제한 사유를 안내한다.</p>
<p class="principle-text">• <b>권한·보안 우선</b>: 개인정보, 청구, 결제, 회선, 가입 정보처럼 민감한 정보는 로그인, 본인확인, 동의, 권한 기준을 충족한 경우에만 노출하거나 처리한다.</p>
<p class="principle-text">• <b>이력 추적 가능성</b>: 주요 조회, 검증, 신청, 변경, 실패, 예외, 운영 변경 결과는 추적 가능한 이력으로 저장한다.</p>
{requirement_analysis_section(ctx)}
{reference_analysis_section(ctx)}
"""


def terms_section(ctx, profile: TopicProfile) -> str:
    rows = []
    terms = [
        (ctx.topic, f"통합채널에서 고객이 {ctx.topic}을 조회, 확인, 선택, 신청, 변경 또는 관리하기 위해 수행하는 업무 단위"),
        ("대상 고객", f"{ctx.topic} 업무를 이용하는 고객. 로그인 여부와 고객 상태는 액터가 아니라 권한 조건과 상태 기준으로 관리한다."),
        (profile.primary_object, f"{ctx.topic} 업무에서 조회, 검증, 처리, 고지의 기준이 되는 핵심 대상 정보"),
        ("처리 가능 상태", f"고객 상태와 {profile.primary_object} 조건이 {ctx.topic} 업무 진행 기준을 충족한 상태"),
        ("처리 제한 상태", f"정책 조건, 권한, 인증, 시스템 응답, 고객 상태 때문에 {ctx.topic} 업무를 완료할 수 없는 상태"),
        ("본인확인", "개인정보, 청구, 결제, 가입 정보, 회선 정보처럼 민감한 정보 노출 또는 변경 전에 고객 본인 여부를 확인하는 절차"),
        ("동의", "약관, 개인정보 활용, 혜택 적용, 제3자 제공, 마케팅 수신 등 고객의 명시적 승인이 필요한 처리"),
        ("BSS 검증 결과", "BSS가 고객 상태, 가입 상품, 청구, 혜택, 약정, 제한 조건, 처리 가능 여부를 판정해 채널에 회신한 결과"),
        ("연계 처리 결과", "외부 BP, 결제, 쿠폰, 주문, 물류, 상담, 인증 등 연계 시스템에서 회신한 성공, 실패, 보류, 제한 결과"),
        ("영향도 고지", "고객이 처리 전에 알아야 하는 비용, 혜택, 약정, 쿠폰, 포인트, 회선, 주문 상태, 이용 제한 영향을 안내하는 기준"),
        ("처리 이력", "고객 요청, 시스템 검증, 처리 결과, 실패 사유, 상담 전환, 운영 변경을 추적하기 위해 저장하는 기록"),
        ("운영 기준", f"{ctx.topic}의 기준 정보, 노출 조건, 제한 조건, 품질 기준, 변경 이력을 운영자가 관리하기 위한 기준"),
        ("품질 모니터링", "정확성, 완결성, 오류, 지연, 고객 피드백, 상담 전환율을 기준으로 업무 품질을 점검하는 활동"),
    ]
    terms.extend(profile.extra_terms)

    for index, (name, description) in enumerate(terms, start=1):
        rows.append(tr(td(f"TM-{ctx.business_code}-{index:03d}", "mono"), td(esc(name)), td(esc(description))))

    return f"""
<h2>2. 주요 용어</h2>
<p class="plain-text">본 장의 용어는 {esc(ctx.topic)} 정책서 전반에서 동일한 의미로 사용한다.<br/>용어는 단순 설명이 아니라 프로세스, 기능, 정책 판단에 쓰이는 기준으로 정의한다.</p>
<table>
<thead>{tr(th("용어 ID", style="width: 130px;"), th("용어", style="width: 220px;"), th("설명"))}</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
"""


def usecase_section(ctx, profile: TopicProfile) -> str:
    actor_rows = [
        tr(td(f"ACT-{ctx.business_code}-001", "mono"), td("고객"), td(f"{esc(ctx.topic)} 정보를 확인하고 조건을 판단한 뒤 필요한 후속 업무를 직접 수행하는 주체")),
        tr(td(f"ACT-{ctx.business_code}-002", "mono"), td("운영자"), td(f"{esc(ctx.topic)} 기준 정보, 노출 조건, 제한 기준, 운영 변경 이력, 품질 지표를 관리하는 내부 담당자")),
        tr(td(f"ACT-{ctx.business_code}-003", "mono"), td("BSS"), td("고객 상태, 가입 상품, 요금, 혜택, 약정, 회선, 제한 조건, 처리 결과를 판정하고 채널에 회신하는 시스템")),
        tr(td(f"ACT-{ctx.business_code}-004", "mono"), td("연계 시스템"), td(f"{esc(', '.join(profile.systems))} 등 {esc(ctx.topic)} 업무 처리에 필요한 기준 정보와 연계 결과를 제공하는 시스템")),
        tr(td(f"ACT-{ctx.business_code}-005", "mono"), td("채널 업무 시스템"), td("고객 입력, 화면 흐름, 세션, 처리 요청, 결과 안내, 이력 저장을 담당하는 채널 시스템")),
    ]
    usecase_rows = [
        usecase_row(ctx, "CS", 1, "고객", f"{ctx.topic} 정보 확인", f"고객이 {ctx.topic}의 대상 정보, 주요 조건, 이용 가능 여부를 확인하는 유즈케이스", "Y"),
        usecase_row(ctx, "CS", 2, "고객", f"{ctx.topic} 조건 확인", f"고객이 본인 상태와 {profile.primary_object} 조건에 따라 처리 가능 여부와 제한 사유를 확인하는 유즈케이스", "Y"),
        usecase_row(ctx, "CS", 3, "고객", f"{ctx.topic} 처리 요청", f"고객이 조건 충족 후 {profile.action}을 요청하고 완료 결과를 확인하는 유즈케이스", "Y"),
        usecase_row(ctx, "CS", 4, "고객", "처리 결과 확인", "고객이 성공, 실패, 보류, 제한 결과와 후속 조치 경로를 확인하는 유즈케이스", "Y"),
        usecase_row(ctx, "OPR", 1, "운영자", f"{ctx.topic} 운영 기준 관리", "운영자가 기준 정보, 노출 조건, 제한 기준, 품질 지표, 변경 이력을 관리하는 유즈케이스", "Y"),
        usecase_row(ctx, "BSS", 1, "BSS", "고객 상태 및 가능 여부 제공", "BSS가 고객 상태와 업무 가능 여부를 판정하여 채널에 회신하는 유즈케이스", "N"),
        usecase_row(ctx, "EXT", 1, "연계 시스템", f"{ctx.topic} 기준 정보 제공", f"연계 시스템이 {ctx.topic} 처리에 필요한 기준 정보와 연계 결과를 제공하는 유즈케이스", "N"),
        usecase_row(ctx, "SYS", 1, "채널 업무 시스템", "처리 이력 및 결과 안내", "채널 업무 시스템이 요청, 검증, 처리, 실패, 상담 전환 이력을 저장하고 고객에게 결과를 안내하는 유즈케이스", "N"),
    ]

    return f"""
<h2>3. 유즈케이스 정의</h2>
<h3>가. 액터</h3>
<p class="plain-text">본 장은 {esc(ctx.topic)} 업무에 참여하는 독립 책임 주체만 정의한다.<br/>로그인 고객, 비로그인 고객, 정상 고객, 제한 고객처럼 같은 고객의 상태 차이는 액터로 분리하지 않고 상태와 정책 조건에서 관리한다.</p>
<table>
<thead>{tr(th("액터 ID", style="width: 130px;"), th("액터명", style="width: 170px;"), th("설명"))}</thead>
<tbody>{''.join(actor_rows)}</tbody>
</table>
<h3>나. 유즈케이스</h3>
<p class="plain-text">고객과 운영자가 직접 수행하는 유즈케이스는 프로세스 정의 대상으로 관리한다.<br/>BSS와 연계 시스템의 조회·검증·저장 처리는 고객 또는 운영자 프로세스를 지원하는 보조 유즈케이스로 관리한다.</p>
<table>
<thead>{tr(th("유즈케이스 ID", style="width: 140px;"), th("액터", style="width: 150px;"), th("유즈케이스명", style="width: 190px;"), th("설명"), th("프로세스 정의 대상", style="width: 110px;"))}</thead>
<tbody>{''.join(usecase_rows)}</tbody>
</table>
<h3>다. 유즈케이스 다이어그램</h3>
<div class="diagram-wrap">
<div>
[고객] → ({esc(ctx.topic)} 정보 확인) → include: 기준 정보 조회, 고객 상태 확인<br/>
[고객] → ({esc(ctx.topic)} 조건 확인) → include: BSS 가능 여부 검증, 제한 사유 확인<br/>
[고객] → ({esc(ctx.topic)} 처리 요청) → include: 인증·동의, 영향도 고지, 처리 결과 저장<br/>
[운영자] → ({esc(ctx.topic)} 운영 기준 관리) → include: 기준 등록, 변경 이력 저장, 품질 모니터링<br/>
[BSS/연계 시스템] → 기준 정보·검증 결과 제공
</div>
</div>
{state_section(ctx)}
"""


def usecase_row(ctx, area: str, index: int, actor: str, name: str, description: str, target: str) -> str:
    return tr(
        td(f"US-{ctx.business_code}-{area}-{index:03d}", "mono"),
        td(esc(actor)),
        td(esc(name)),
        td(esc(description)),
        td(target, "center"),
    )


def state_section(ctx) -> str:
    states = [
        ("001", "진입 전", f"고객이 {ctx.topic} 업무를 시작하기 전 상태", "업무 진입 경로와 기본 안내를 제공한다."),
        ("002", "조회 가능", "기본 기준 정보와 공통 안내를 조회할 수 있는 상태", "공통 정보와 로그인 필요 여부를 안내한다."),
        ("003", "인증 필요", "개인화 정보 또는 처리 요청에 본인확인이 필요한 상태", "로그인, 본인확인, 추가 인증 경로를 제공한다."),
        ("004", "처리 가능", "고객 상태와 업무 조건이 처리 기준을 충족한 상태", "신청, 변경, 선택, 저장, 결제 등 후속 처리를 허용한다."),
        ("005", "처리 중", "채널 또는 연계 시스템이 고객 요청을 처리 중인 상태", "중복 요청을 제한하고 처리 결과를 대기한다."),
        ("006", "처리 완료", "요청이 정상 반영되고 고객에게 결과 안내가 가능한 상태", "완료 결과, 적용 시점, 이력을 안내한다."),
        ("007", "처리 제한", "정책 조건, 고객 상태, 연계 실패로 업무를 완료할 수 없는 상태", "제한 사유와 대체 경로를 안내한다."),
        ("008", "운영 확인 필요", "기준 정보 불일치, 반복 오류, 품질 저하로 운영자 확인이 필요한 상태", "운영 확인 큐에 등록하고 고객에게 지연 또는 상담 경로를 안내한다."),
    ]
    state_rows = [
        tr(td(f"ST-{ctx.business_code}-{code}", "mono"), td(name), td(desc), td(next_action))
        for code, name, desc, next_action in states
    ]
    transition_rows = [
        ("진입 전", "고객이 업무 메뉴 또는 검색 결과에서 진입", "조회 가능", "공통 기준 정보를 조회하고 로그인 또는 인증 필요 여부를 판단한다."),
        ("조회 가능", "개인화 정보 또는 처리 요청 선택", "인증 필요", "권한 확인이 필요한 경우 본인확인 경로로 전환한다."),
        ("인증 필요", "본인확인 성공", "처리 가능", "인증 성공 이력을 저장하고 가능 여부 검증을 수행한다."),
        ("인증 필요", "본인확인 실패 또는 시간 초과", "처리 제한", "실패 사유를 안내하고 재시도 기준을 적용한다."),
        ("처리 가능", "고객이 처리 요청 확정", "처리 중", "중복 요청을 제한하고 BSS 또는 연계 시스템에 처리 요청을 전달한다."),
        ("처리 중", "연계 시스템 성공 회신", "처리 완료", "처리 결과, 적용 시점, 고객 안내 이력을 저장한다."),
        ("처리 중", "연계 시스템 실패 또는 제한 회신", "처리 제한", "실패 사유, 복구 가능 여부, 상담 전환 기준을 안내한다."),
        ("처리 제한", "고객이 조건 보완 또는 재시도", "조회 가능", "재조회 후 처리 가능 여부를 다시 판단한다."),
        ("처리 제한", "반복 실패 또는 기준 정보 불일치", "운영 확인 필요", "오류 이력과 고객 영향을 운영 확인 대상으로 등록한다."),
        ("운영 확인 필요", "운영자가 기준 보정 완료", "조회 가능", "변경 이력을 저장하고 고객 재시도 가능 상태로 전환한다."),
    ]
    transition_html = [tr(td(a), td(b), td(c), td(d)) for a, b, c, d in transition_rows]
    state_spec = {
        "meta": {"topic": ctx.topic},
        "states": [
            {
                "id": f"ST-{ctx.business_code}-{code}",
                "name": name,
                "description": desc,
                "next_action": next_action,
            }
            for code, name, desc, next_action in states
        ],
        "state_transitions": [
            {
                "current_state": current,
                "event": event,
                "next_state": next_state,
                "criteria": criteria,
            }
            for current, event, next_state, criteria in transition_rows
        ],
    }
    state_diagram = build_state_static_diagram(state_spec)

    return f"""
<h3>라. 상태 전이표</h3>
<p class="plain-text">본 장은 {esc(ctx.topic)}의 주요 상태와 상태 전이 기준을 정의한다.<br/>상태 전이표에서 사용하는 상태명은 상태 코드 목록의 상태명과 일치해야 한다.</p>
<h4>1) 상태 코드</h4>
<table>
<thead>{tr(th("상태 코드", style="width: 160px;"), th("상태명", style="width: 150px;"), th("정의"), th("대표 후속 처리", style="width: 230px;"))}</thead>
<tbody>{''.join(state_rows)}</tbody>
</table>
<h4>2) 상태 전이 기준</h4>
<table>
<thead>{tr(th("현재 상태", style="width: 150px;"), th("전이 이벤트", style="width: 220px;"), th("다음 상태", style="width: 150px;"), th("처리 기준 및 후속 처리"))}</thead>
<tbody>{''.join(transition_html)}</tbody>
</table>
<h4>3) 상태 전이 다이어그램</h4>
{state_diagram}
"""


def process_section(ctx, profile: TopicProfile) -> str:
    processes = process_rows(ctx, profile)
    grouped = []
    for group_index, (title, usecase_id, rows) in enumerate(processes, start=1):
        grouped.append(f"""
<h4>{group_index}) {esc(title)}</h4>
<table>
<thead>{tr(th("프로세스 ID", style="width: 150px;"), th("프로세스명", style="width: 170px;"), th("설명"), th("관련 기능", style="width: 230px;"), th("관련 정책", style="width: 230px;"))}</thead>
<tbody>{''.join(rows)}</tbody>
</table>
""")

    full_detail = process_detail_section(ctx, profile) if ctx.template_type == "full" else ""
    return f"""
<h2>4. 프로세스 정의</h2>
<h3>가. 프로세스 목록</h3>
<p class="plain-text">프로세스는 고객 또는 운영자가 경험하는 순서대로 작성한다.<br/>각 프로세스는 관련 기능과 정책 목록의 정책 ID·정책명을 연결한다.</p>
{''.join(grouped)}
<h3>나. 전체 업무 흐름도</h3>
<div class="diagram-wrap">
<div>
고객 진입 → 기본 정보 조회 → 고객 상태 확인 → 처리 가능 여부 검증 → 영향도 고지 → 인증·동의 → 처리 요청 → 결과 반영 → 완료 안내<br/>
예외 흐름: 검증 실패 → 제한 사유 안내 → 재시도 또는 상담 전환<br/>
운영 흐름: 기준 정보 변경 → 검수 → 배포 → 품질 모니터링 → 변경 이력 저장
</div>
</div>
{full_detail}
"""


def process_rows(ctx, profile: TopicProfile) -> List[tuple[str, str, List[str]]]:
    code = ctx.business_code
    topic = ctx.topic
    analysis = requirement_analysis(ctx)
    reference_cats = reference_categories(ctx)
    rows_1 = [
        process_row(code, "CS-001-01", "업무 진입", f"고객이 {topic} 업무에 진입하면 채널은 공통 기준 정보와 로그인 필요 여부를 확인한다.", "업무 진입 조건 확인<br/>기준 정보 조회", "접근·권한 정책<br/>대상 정보 노출 정책"),
        process_row(code, "CS-001-02", "대상 정보 조회", f"채널은 {profile.primary_object}와 고객에게 노출 가능한 기본 정보를 조회한다.", "기준 정보 조회<br/>결과 구성", "대상 정보 노출 정책"),
    ]
    rows_2 = [
        process_row(code, "CS-002-01", "고객 상태 확인", "BSS는 고객 상태, 보유 상품, 제한 조건, 인증 필요 여부를 판정한다.", "고객 상태 조회<br/>가능 여부 검증", "가능 여부 검증 정책<br/>접근·권한 정책"),
        process_row(code, "CS-002-02", "영향도 산정", f"{topic} 처리에 따른 비용, 혜택, 약정, 포인트, 쿠폰, 주문 상태 영향을 산정한다.", "영향도 산정<br/>고객 고지 생성", "영향도 고지 정책"),
    ]
    rows_3 = [
        process_row(code, "CS-003-01", "인증·동의 확인", "민감정보 노출 또는 처리 요청이 필요한 경우 본인확인, 약관 동의, 최종 확인을 수행한다.", "인증 처리<br/>동의 저장", "인증·동의 정책"),
        process_row(code, "CS-003-02", "처리 요청", "고객 최종 확인 후 채널은 BSS 또는 연계 시스템에 처리 요청을 전달한다.", "처리 요청 연계<br/>중복 요청 제한", "처리 결과·이력 정책"),
    ]
    rows_4 = [
        process_row(code, "CS-004-01", "결과 반영", "연계 시스템 회신 결과에 따라 성공, 실패, 보류, 제한 상태를 반영한다.", "결과 수신<br/>상태 반영", "처리 결과·이력 정책"),
        process_row(code, "CS-004-02", "결과 안내", "고객에게 처리 결과, 적용 시점, 제한 사유, 후속 조치 경로를 안내한다.", "결과 안내<br/>알림 발송", "처리 결과·이력 정책<br/>예외·상담 전환 정책"),
    ]
    rows_5 = [
        process_row(code, "OPR-001-01", "운영 기준 관리", f"운영자는 {topic} 기준 정보, 노출 조건, 제한 기준을 등록·수정·비활성화한다.", "운영 기준 관리<br/>변경 이력 저장", "운영 관리 정책"),
        process_row(code, "OPR-001-02", "품질 모니터링", "운영자는 오류, 지연, 실패, 상담 전환, 고객 피드백을 확인하고 보정 대상을 관리한다.", "품질 지표 수집<br/>운영 확인 등록", "품질 관리 정책<br/>개인정보·로그 보호 정책"),
    ]
    if analysis:
        if has_requirement_category(analysis, "information"):
            rows_1.append(process_row(code, "CS-001-03", "핵심 정보 구조화", "요구사항 분석에서 도출된 핵심 정보, 비교 기준, 상태 정보를 고객 과업 순서에 맞게 구성한다.", "기준 정보 조회<br/>결과 구성", "대상 정보 노출 정책<br/>요구사항 분석 보강 정책"))
        if has_requirement_category(analysis, "benefit"):
            rows_2.append(process_row(code, "CS-002-03", "혜택·비용 영향 확인", "혜택, 할인, 쿠폰, 포인트, 재고, 적용 조건의 고객 영향을 산정하고 제한 조건을 사전에 분류한다.", "영향도 산정<br/>가능 여부 검증", "영향도 고지 정책<br/>가능 여부 검증 정책"))
        if has_requirement_category(analysis, "payment"):
            rows_3.append(process_row(code, "CS-003-03", "결제·청구 조건 확정", "결제 방식, 청구 방식, 납부 조건, 할부 조건처럼 고객 선택이 필요한 처리 조건을 확정한다.", "처리 요청 연계<br/>중복 요청 제한", "처리 결과·이력 정책<br/>인증·동의 정책"))
        if has_requirement_category(analysis, "auth"):
            rows_3.append(process_row(code, "CS-003-04", "권한·동의 기준 확인", "민감 정보 노출, 개인화 처리, 변경·결제성 처리에 필요한 본인확인과 동의 조건을 확정한다.", "인증 처리<br/>동의 저장", "접근·권한 정책<br/>인증·동의 정책"))
        if has_requirement_category(analysis, "data"):
            rows_1.append(process_row(code, "CS-001-04", "개인화·데이터 기준 확인", "개인화, 추천, 검색, 데이터 활용이 필요한 경우 활용 범위와 신뢰도 기준을 확인한다.", "기준 정보 조회<br/>고객 상태 조회", "대상 정보 노출 정책<br/>개인정보·로그 보호 정책"))
        if has_requirement_category(analysis, "operation"):
            rows_5.append(process_row(code, "OPR-001-03", "전시·운영 기준 검수", "전시 기준, 템플릿, 문구, 기준 정보 변경은 배포 전 검수하고 변경 이력을 남긴다.", "운영 기준 관리<br/>변경 이력 저장", "운영 관리 정책<br/>품질 관리 정책"))
        if has_requirement_category(analysis, "exception"):
            rows_4.append(process_row(code, "CS-004-03", "예외 후속 경로 결정", "오류, 장애, 제한, 상담 전환이 필요한 경우 고객 영향과 대체 경로를 기준으로 후속 처리를 결정한다.", "예외·상담 전환<br/>결과 안내", "예외·상담 전환 정책<br/>처리 결과·이력 정책"))
    if reference_cats:
        if has_reference_category(reference_cats, "strategy"):
            rows_1.append(process_row(code, "CS-001-05", "목적 기반 진입 분기", "참고자료에서 확인한 채널 통합 방향을 반영해 고객 목적별 진입 경로와 다음 행동을 분기한다.", "업무 진입 조건 확인<br/>참고자료 기반 경험 보강", "참고자료 분석 보강 정책<br/>접근·권한 정책"))
        if has_reference_category(reference_cats, "voc") or has_reference_category(reference_cats, "research"):
            rows_2.append(process_row(code, "CS-002-04", "고객 불편 요인 점검", "고객 조사와 VoC에서 반복되는 혼란, 오인, 인증 마찰, 상담 전환 요인을 조건 확인 단계에서 점검한다.", "고객 상태 조회<br/>가능 여부 검증", "참고자료 분석 보강 정책<br/>예외·상담 전환 정책"))
        if has_reference_category(reference_cats, "ia"):
            rows_1.append(process_row(code, "CS-001-06", "IA 경로 정합성 확인", "IA 참고자료를 기준으로 고객이 진입한 메뉴, 탐색 경로, 후속 업무 연결이 주제 범위와 일치하는지 확인한다.", "기준 정보 조회<br/>결과 구성", "참고자료 분석 보강 정책<br/>대상 정보 노출 정책"))
        if has_reference_category(reference_cats, "ai"):
            rows_2.append(process_row(code, "CS-002-05", "AI·개인화 판단 검증", "AI, 검색, 추천, 개인화가 사용되는 경우 신뢰도, 고객 동의, 실행 가능성을 확인한 뒤 결과를 제공한다.", "개인화·데이터 활용 기준 확인<br/>가능 여부 검증", "참고자료 분석 보강 정책<br/>개인정보·로그 보호 정책"))
        if has_reference_category(reference_cats, "benchmark"):
            rows_2.append(process_row(code, "CS-002-06", "비교·선택 기준 보강", "벤치마킹 관점에서 고객이 선택 전에 확인해야 하는 비교 기준, 기대 수준, 제한 조건을 보강한다.", "기준 정보 조회<br/>영향도 산정", "참고자료 분석 보강 정책<br/>영향도 고지 정책"))
    return [
        (f"{topic} 정보 확인", f"US-{code}-CS-001", rows_1),
        (f"{topic} 조건 확인", f"US-{code}-CS-002", rows_2),
        (f"{topic} 처리 요청", f"US-{code}-CS-003", rows_3),
        ("처리 결과 확인", f"US-{code}-CS-004", rows_4),
        (f"{topic} 운영 기준 관리", f"US-{code}-OPR-001", rows_5),
    ]


def process_row(code: str, suffix: str, name: str, description: str, functions: str, policies: str) -> str:
    return tr(td(f"PR-{code}-{suffix}", "mono"), td(esc(name)), td(esc(description)), td(functions), td(format_policy_refs(code, policies)))


POLICY_REF_SUFFIX_BY_NAME = {
    "접근·권한 정책": "ACC-001",
    "대상 정보 노출 정책": "INF-001",
    "가능 여부 검증 정책": "VAL-001",
    "인증·동의 정책": "AUT-001",
    "영향도 고지 정책": "IMP-001",
    "처리 결과·이력 정책": "RSLT-001",
    "예외·상담 전환 정책": "ERR-001",
    "운영 관리 정책": "OPR-001",
    "개인정보·로그 보호 정책": "PRV-001",
    "품질 관리 정책": "QUL-001",
    "요구사항 분석 보강 정책": "ANL-001",
    "참고자료 분석 보강 정책": "REF-001",
}


def format_policy_refs(code: str, policies: str) -> str:
    parts = [part.strip() for part in re.split(r"<br\s*/?>", policies) if part.strip()]
    refs = []
    for name in parts:
        suffix = POLICY_REF_SUFFIX_BY_NAME.get(name)
        refs.append(f"PG-{code}-{suffix} {name}" if suffix else name)
    return "<br/>".join(refs)


def process_detail_section(ctx, profile: TopicProfile) -> str:
    details = [
        ("CS-001-01", "업무 진입", "고객이 메뉴, 검색 결과, 알림, 외부 링크에서 진입한다.", "고객이 기본 안내 또는 다음 단계로 이동할 수 있다.", "접근 권한 확인, 진입 경로 저장, 로그인 필요 여부 판단"),
        ("CS-002-01", "고객 상태 확인", "고객 식별 또는 세션이 확인된다.", "처리 가능, 인증 필요, 처리 제한 중 하나로 판단된다.", "BSS 고객 상태 조회, 가입 상품 조회, 제한 조건 판정"),
        ("CS-003-01", "인증·동의 확인", "개인화 정보 노출 또는 처리 요청이 선택된다.", "인증·동의 이력이 저장되고 처리 요청이 가능해진다.", "본인확인, 약관 동의, 영향도 고지, 최종 확인"),
        ("CS-003-02", "처리 요청", "고객이 최종 확인을 완료한다.", "BSS 또는 연계 시스템에 요청이 전달되고 처리 중 상태가 된다.", "중복 요청 제한, 연계 요청, 타임아웃 관리"),
        ("CS-004-02", "결과 안내", "연계 시스템 처리 결과가 수신된다.", "고객에게 완료, 실패, 보류, 상담 전환 경로가 안내된다.", "결과 메시지 생성, 이력 저장, 알림 발송"),
    ]
    rows = [
        tr(
            td(f"PR-{ctx.business_code}-{suffix}", "mono"),
            td(esc(name)),
            td(esc(entry)),
            td(esc(exit_)),
            td(esc(logic)),
        )
        for suffix, name, entry, exit_, logic in details
    ]
    return f"""
<h3>다. 프로세스 상세</h3>
<p class="plain-text">Full 버전에서는 주요 프로세스의 진입 조건, 종료 조건, 수행 로직을 상세 설계 기준으로 작성한다.<br/>화면 버튼이나 API 필드가 아니라 업무 처리 기준과 판단 흐름을 중심으로 정의한다.</p>
<table>
<thead>{tr(th("프로세스 ID", style="width: 150px;"), th("프로세스명", style="width: 160px;"), th("진입 조건"), th("종료 조건"), th("수행 로직"))}</thead>
<tbody>{''.join(rows)}</tbody>
</table>
"""


def functions_section(ctx, profile: TopicProfile) -> str:
    functions = function_definitions(ctx, profile)
    rows = [
        tr(td(fid, "mono"), td(esc(name)), td(esc(description)), td("<br/>".join(esc(item) for item in details)))
        for fid, name, description, details in functions
    ]
    full_detail = function_detail_section(ctx, functions) if ctx.template_type == "full" else ""
    return f"""
<h2>5. 기능 정의</h2>
<h3>가. 기능 목록</h3>
<p class="plain-text">기능은 화면 단위가 아니라 {esc(ctx.topic)} 프로세스를 수행하기 위한 처리 단위로 작성한다.<br/>각 기능은 관련 정책을 실행하는 수단이며, 정책값은 6. 정책 정의에서 관리한다.</p>
<table>
<thead>{tr(th("기능 ID", style="width: 150px;"), th("기능명", style="width: 190px;"), th("설명"), th("세부 기능 구성", style="width: 270px;"))}</thead>
<tbody>{''.join(rows)}</tbody>
</table>
{full_detail}
"""


def function_definitions(ctx, profile: TopicProfile) -> List[tuple[str, str, str, Sequence[str]]]:
    code = ctx.business_code
    topic = ctx.topic
    functions = [
        (f"FN-{code}-ENT-001", "업무 진입 조건 확인", f"{topic} 진입 경로와 고객 세션을 확인하여 기본 안내와 로그인 필요 여부를 판단한다.", ("진입 경로 식별", "세션 확인", "로그인 필요 여부 판단", "진입 이력 저장")),
        (f"FN-{code}-INF-001", "기준 정보 조회", f"{profile.primary_object}의 공통 기준 정보와 고객에게 노출 가능한 정보를 조회한다.", ("기준 정보 조회", "노출 가능 항목 필터링", "기준일 표시", "조회 실패 처리")),
        (f"FN-{code}-BSS-001", "고객 상태 조회", "BSS에서 고객 상태, 가입 상품, 회선, 요금, 혜택, 제한 조건을 조회한다.", ("고객 식별", "가입 상태 조회", "제한 조건 조회", "검증 결과 수신")),
        (f"FN-{code}-VAL-001", "가능 여부 검증", f"{topic} 처리 가능 여부와 제한 사유를 정책 기준에 따라 판단한다.", ("처리 조건 검증", "제한 사유 분류", "인증 필요 여부 판단", "상담 전환 여부 판단")),
        (f"FN-{code}-NTC-001", "영향도 고지 생성", "처리 전 고객에게 고지해야 하는 비용, 혜택, 약정, 포인트, 쿠폰, 상태 영향을 생성한다.", ("영향 항목 산정", "고객 고지 구성", "고지 확인 이력 저장", "고지 미확인 처리 제한")),
        (f"FN-{code}-AUT-001", "인증·동의 처리", "본인확인, 약관 동의, 개인정보 활용 동의, 최종 확인을 처리하고 이력을 저장한다.", ("본인확인 요청", "동의 항목 표시", "동의 결과 저장", "인증 만료 처리")),
        (f"FN-{code}-REQ-001", "처리 요청 연계", "고객 최종 확인 후 BSS 또는 연계 시스템에 처리 요청을 전달한다.", ("중복 요청 제한", "연계 요청 생성", "타임아웃 관리", "응답 결과 수신")),
        (f"FN-{code}-RST-001", "결과 안내 및 이력 저장", "처리 결과, 적용 시점, 실패 사유, 후속 조치 경로를 안내하고 이력을 저장한다.", ("결과 메시지 생성", "처리 이력 저장", "알림 발송", "후속 경로 제공")),
        (f"FN-{code}-EXC-001", "예외·상담 전환", "처리 제한, 반복 실패, 운영 확인 필요 상황에서 대체 경로와 상담 전환을 제공한다.", ("예외 사유 분류", "재시도 기준 적용", "상담 연결", "운영 확인 등록")),
        (f"FN-{code}-OPR-001", "운영 기준 관리", f"운영자가 {topic} 기준 정보, 노출 조건, 제한 기준, 품질 지표를 관리한다.", ("기준 등록·수정", "검수·승인", "배포", "변경 이력 저장")),
    ]
    analysis = requirement_analysis(ctx)
    if has_requirement_category(analysis, "information"):
        functions.append((f"FN-{code}-ANL-INF-001", "요구사항 기반 정보 구조화", "요구사항 분석에서 도출한 핵심 정보, 비교 속성, 고객 이해 요소를 화면 흐름과 정책 판단 기준으로 구조화한다.", ("핵심 정보 분류", "비교 기준 구성", "고객 상태별 노출 범위 결정", "정보 최신성 확인")))
    if has_requirement_category(analysis, "benefit"):
        functions.append((f"FN-{code}-ANL-BEN-001", "혜택·조건 영향 분석", "혜택, 할인, 쿠폰, 포인트, 재고, 제한 조건을 고객 영향 기준으로 산정하고 사전 고지 항목을 생성한다.", ("혜택 조건 조회", "중복·제한 조건 검증", "예상 영향 산정", "고지 항목 구성")))
    if has_requirement_category(analysis, "payment"):
        functions.append((f"FN-{code}-ANL-PAY-001", "결제·청구 조건 분석", "결제, 청구, 납부, 할부 조건을 고객 선택 가능 범위와 처리 제한 기준으로 분석한다.", ("결제 가능 수단 확인", "청구 조건 확인", "실패 후속 처리 분류", "민감정보 마스킹")))
    if has_requirement_category(analysis, "auth"):
        functions.append((f"FN-{code}-ANL-AUT-001", "권한·동의 기준 분석", "개인화 정보, 민감정보, 변경·결제성 처리에 필요한 인증과 동의 기준을 분석한다.", ("권한 조건 확인", "본인확인 필요 여부 판단", "동의 항목 분류", "권한 실패 경로 제공")))
    if has_requirement_category(analysis, "operation"):
        functions.append((f"FN-{code}-ANL-OPR-001", "전시·운영 기준 검수", "운영 기준, 문구, 템플릿, 기준 정보 변경이 고객 노출과 처리 판단에 미치는 영향을 검수한다.", ("운영 기준 검수", "배포 가능 여부 판단", "변경 이력 저장", "롤백 기준 확인")))
    if has_requirement_category(analysis, "data"):
        functions.append((f"FN-{code}-ANL-DAT-001", "개인화·데이터 활용 기준 확인", "검색, 추천, 개인화, 데이터 활용이 필요한 경우 데이터 범위, 동의, 신뢰도, 폴백 기준을 확인한다.", ("활용 데이터 범위 확인", "동의 상태 확인", "신뢰도 판단", "폴백 경로 제공")))
    if has_requirement_category(analysis, "exception"):
        functions.append((f"FN-{code}-ANL-EXC-001", "예외 후속 처리 분석", "오류, 제한, 장애, 반복 실패 상황에서 재시도, 대체 경로, 상담 전환 기준을 분석한다.", ("오류 유형 분류", "재시도 가능 여부 판단", "상담 전환 기준 적용", "운영 확인 등록")))
    reference_cats = reference_categories(ctx)
    if has_reference_category(reference_cats, "strategy"):
        functions.append((f"FN-{code}-REF-STR-001", "채널 전략 반영 기준 확인", "채널 통합 방향, 목적 기반 UX, 셀프 처리 확대 관점을 기능 범위와 처리 흐름에 반영한다.", ("목적 기반 진입 판단", "셀프 처리 우선순위 확인", "채널 경량화 기준 확인", "후속 업무 분기")))
    if has_reference_category(reference_cats, "voc") or has_reference_category(reference_cats, "research"):
        functions.append((f"FN-{code}-REF-CUS-001", "고객 불편 분석 반영", "고객 조사와 VoC에서 반복되는 혼란, 오인, 실패 요인을 안내, 검증, 예외 기준으로 전환한다.", ("불편 요인 분류", "오인 가능 조건 확인", "안내 보강 항목 생성", "상담 전환 기준 확인")))
    if has_reference_category(reference_cats, "ia"):
        functions.append((f"FN-{code}-REF-IA-001", "IA 정합성 확인", "IA 구조와 탐색 경로를 기준으로 메뉴 진입, 후속 업무 연결, 노출 우선순위를 검증한다.", ("메뉴 경로 확인", "후속 업무 연결", "중복 경로 정리", "탐색 실패 경로 보정")))
    if has_reference_category(reference_cats, "benchmark"):
        functions.append((f"FN-{code}-REF-BMK-001", "비교·선택 경험 보강", "벤치마킹 자료에서 확인한 비교, 선택, 확인 기대 수준을 고객 고지와 처리 기준으로 반영한다.", ("비교 기준 구성", "선택 전 확인 항목 생성", "외부 기대 수준 점검", "고객 안내 보강")))
    if has_reference_category(reference_cats, "ai"):
        functions.append((f"FN-{code}-REF-AI-001", "AI·개인화 신뢰도 확인", "AI, 검색, 추천, 개인화 적용 시 정확성, 신뢰도, 실행 가능성, 폴백 기준을 확인한다.", ("신뢰도 기준 확인", "동의 상태 확인", "실행 가능 여부 검증", "폴백 결과 제공")))
    return functions


def function_detail_section(ctx, functions: Sequence[tuple[str, str, str, Sequence[str]]]) -> str:
    rows = []
    for fid, name, description, details in functions[:7]:
        rows.append(
            tr(
                td(fid, "mono"),
                td(esc(name)),
                td(esc(description)),
                td("고객 식별값<br/>세션 정보<br/>기준일시<br/>연계 시스템 응답"),
                td("<br/>".join(esc(item) for item in details)),
                td("화면 안내<br/>처리 결과<br/>저장 이력<br/>연계 회신"),
                td("조회 실패: 재시도 안내<br/>연계 실패: 제한 사유 안내<br/>중복 요청: 기존 처리 상태 안내"),
            )
        )
    return f"""
<h3>나. 기능 상세</h3>
<table>
<thead>{tr(th("기능 ID", style="width: 140px;"), th("기능명", style="width: 160px;"), th("설명"), th("입력 정보", style="width: 170px;"), th("처리 로직", style="width: 190px;"), th("출력 정보", style="width: 170px;"), th("실패·예외 기준", style="width: 190px;"))}</thead>
<tbody>{''.join(rows)}</tbody>
</table>
"""


def policies_section(ctx, profile: TopicProfile) -> str:
    groups = policy_groups(ctx, profile)
    list_rows = [
        tr(
            td(f"PG-{ctx.business_code}-{group.code}", "mono"),
            td(esc(group.name)),
            td(esc(group.description)),
            td("<br/>".join(esc(item_name) for item_name, _ in group.items)),
        )
        for group in groups
    ]
    detail_blocks = []
    for index, group in enumerate(groups, start=1):
        items = []
        for item_index, (item_name, content) in enumerate(group.items, start=1):
            items.append(f"""
<div class="policy-item">
<div class="policy-item-title">• {esc(item_name)} <span class="mono">(PI-{ctx.business_code}-{group.code}-{item_index:02d})</span></div>
<div class="policy-item-content">{policy_item_content(content)}</div>
</div>
""")
        detail_blocks.append(f"""
<h4>{index}) {esc(group.name)} (PG-{ctx.business_code}-{group.code})</h4>
<div class="policy-group">
{''.join(items)}
</div>
""")

    return f"""
<h2>6. 정책 정의</h2>
<h3>가. 정책 목록</h3>
<p class="plain-text">정책은 기능 설명이 아니라 기능 동작 기준이다.<br/>프로세스에서 인증 수단, 가능 횟수, 유효시간, 권한, 제한, 고지, 저장, 예외, 운영 판단이 필요한 항목은 정책으로 분리한다.</p>
<table>
<thead>{tr(th("정책 ID", style="width: 150px;"), th("정책명", style="width: 210px;"), th("설명"), th("정책 항목", style="width: 280px;"))}</thead>
<tbody>{''.join(list_rows)}</tbody>
</table>
<h3>나. 정책 상세</h3>
{''.join(detail_blocks)}
"""


def policy_groups(ctx, profile: TopicProfile) -> List[PolicyGroup]:
    topic = ctx.topic
    groups = [
        PolicyGroup(
            "AUT-001",
            "접근·권한 정책",
            f"{topic} 정보와 처리 기능에 접근할 수 있는 고객, 세션, 권한 기준을 정의한다.",
            (
                ("공통 정보 접근", "공통 안내와 비개인화 정보는 비로그인 고객에게도 제공할 수 있으나 개인별 상태, 요금, 가입, 결제, 회선 정보는 제공하지 않는다."),
                ("개인화 정보 접근", "개인화 정보는 로그인 세션이 유효하고 고객 본인 또는 위임 권한이 확인된 경우에만 제공한다."),
                ("인증 유효시간", "본인확인 기반 인증은 완료 후 10분 동안 동일 업무 흐름에서 유효하며, 민감정보 변경 또는 결제성 처리 전에는 재확인을 요구한다."),
                ("권한 실패 처리", "권한이 확인되지 않으면 상세 정보 대신 로그인, 본인확인, 상담 연결 중 가능한 경로를 안내한다."),
            ),
        ),
        PolicyGroup(
            "INF-001",
            "대상 정보 노출 정책",
            f"{profile.primary_object}의 노출 범위, 기준일, 우선순위, 제한 기준을 정의한다.",
            (
                ("노출 대상", "고객에게 노출하는 정보는 현재 유효한 기준 정보와 고객이 이해해야 하는 핵심 조건으로 제한한다."),
                ("기준일 표시", "가격, 혜택, 요금, 약정, 쿠폰, 포인트, 주문 상태처럼 변동 가능한 정보는 조회 기준일시 또는 적용 예정일을 함께 표시한다."),
                ("비노출 대상", "내부 판정 코드, API 필드, DB 값, 운영자 메모, 제휴사 내부 정산 정보는 고객 화면과 정책서 본문에 노출하지 않는다."),
                ("정보 불일치 처리", "채널 기준 정보와 BSS 또는 연계 시스템 기준 정보가 다르면 고객 처리를 중단하고 운영 확인 필요 상태로 등록한다."),
            ),
        ),
        PolicyGroup(
            "VAL-001",
            "가능 여부 검증 정책",
            f"{topic} 처리 가능 여부와 제한 사유를 판단하는 기준을 정의한다.",
            (
                ("검증 필수 항목", "고객 상태, 대상 정보 상태, 가입 가능 여부, 제한 조건, 약관 동의, 인증 필요 여부, 연계 시스템 응답을 검증한다."),
                ("제한 사유 분류", "제한 사유는 고객 상태 제한, 대상 정보 제한, 기간 제한, 중복 요청, 연계 실패, 운영 중단, 정책상 불가로 구분한다."),
                ("중복 요청 제한", "동일 고객, 동일 대상, 동일 업무의 처리 중 요청이 있으면 신규 요청을 생성하지 않고 기존 처리 상태를 안내한다."),
                ("재검증 기준", "고객이 조건을 변경하거나 일정 시간이 경과한 뒤 재시도하면 기준 정보를 다시 조회하여 가능 여부를 재판정한다."),
            ),
        ),
        PolicyGroup(
            "CFM-001",
            "인증·동의 정책",
            f"{topic} 처리 전 필요한 본인확인, 약관 동의, 최종 확인 기준을 정의한다.",
            (
                ("인증 수단", "휴대폰 본인확인, PASS 인증, 공동인증서, 간편인증 중 업무 보안 수준에 맞는 수단을 제공한다."),
                ("인증 가능 횟수", "동일 업무 세션 기준 최대 5회까지 허용한다."),
                ("인증번호 유효시간", "인증번호는 발송 후 3분 동안 유효하다."),
                ("동의 저장 항목", "약관, 개인정보 활용, 제3자 제공, 혜택 적용, 결제성 처리 동의는 항목별 동의 여부와 동의 일시를 저장한다."),
                ("최종 확인", "비용, 혜택, 약정, 포인트, 쿠폰, 회선 상태에 영향이 있으면 고객이 최종 확인을 완료해야 처리 요청을 보낼 수 있다."),
            ),
        ),
        PolicyGroup(
            "NTC-001",
            "영향도 고지 정책",
            f"{topic} 처리 전 고객에게 반드시 안내해야 하는 영향 범위를 정의한다.",
            (
                ("고지 필수 항목", f"{topic} 처리로 요금, 할인, 쿠폰, 포인트, 혜택, 약정, 주문, 배송, 회선, 서비스 이용 가능 상태가 바뀌면 사전 고지한다."),
                ("고지 방식", "고지는 처리 요청 전 한 번 이상 표시하고, 고객이 확인하지 않으면 처리 요청 버튼 또는 다음 단계를 활성화하지 않는다."),
                ("예상값 기준", "예상 요금, 예상 혜택, 예상 적용일처럼 변동 가능성이 있는 값은 예상값임을 표시하고 기준일시를 함께 안내한다."),
                ("불확실 영향 처리", "영향 산정이 불가능하거나 연계 결과가 불확실하면 처리를 중단하고 상담 또는 재시도 경로를 안내한다."),
            ),
        ),
        PolicyGroup(
            "RST-001",
            "처리 결과·이력 정책",
            f"{topic} 요청의 결과 안내, 이력 저장, 알림 기준을 정의한다.",
            (
                ("결과 유형", "처리 결과는 성공, 실패, 처리 중, 보류, 제한, 운영 확인 필요로 구분한다."),
                ("고객 안내", "결과 안내에는 처리 결과, 적용 시점, 실패 사유, 재시도 가능 여부, 상담 연결 가능 여부를 포함한다."),
                ("이력 저장", "요청자, 요청 일시, 대상 정보, 검증 결과, 처리 결과, 실패 사유, 연계 시스템 응답, 고지 확인 이력을 저장한다."),
                ("알림 발송", "처리 완료, 실패, 보류, 고객 후속 조치 필요 상태는 앱 알림, 문자, 이메일 중 업무 기준에 맞는 채널로 안내할 수 있다."),
            ),
        ),
        PolicyGroup(
            "EXC-001",
            "예외·상담 전환 정책",
            f"{topic} 업무에서 셀프 처리로 완료할 수 없는 상황의 후속 기준을 정의한다.",
            (
                ("상담 전환 대상", "반복 실패, 권한 불명확, 고객 피해 가능성, 연계 시스템 장애, 운영 기준 불일치가 있으면 상담 전환 또는 운영 확인으로 연결한다."),
                ("재시도 기준", "일시적 조회 실패와 네트워크 오류는 고객 재시도를 허용하되, 동일 오류가 3회 반복되면 상담 또는 운영 확인을 안내한다."),
                ("장애 안내", "연계 시스템 장애나 운영 중단이 확인되면 처리 가능 시간, 대체 경로, 고객 영향 범위를 안내한다."),
                ("예외 이력", "예외 발생 시 오류 유형, 고객 영향, 연계 시스템, 재시도 횟수, 상담 전환 여부를 이력으로 저장한다."),
            ),
        ),
        PolicyGroup(
            "OPR-001",
            "운영 관리 정책",
            f"{topic} 기준 정보와 운영 변경을 관리하는 기준을 정의한다.",
            (
                ("기준 등록", "운영 기준은 등록자, 검수자, 승인자, 적용 시작일, 적용 종료일, 변경 사유를 포함해 관리한다."),
                ("검수·승인", "고객 노출 조건, 가격·혜택·요금 영향, 제한 기준 변경은 운영 검수와 승인 후 배포한다."),
                ("변경 이력", "기준값, 노출 조건, 제한 조건, 품질 기준, 연계 대상이 변경되면 이전 값과 변경 후 값을 모두 저장한다."),
                ("롤백 기준", "변경 후 오류, 고객 영향, 품질 저하가 확인되면 직전 정상 기준으로 롤백하고 변경 이력을 남긴다."),
            ),
        ),
        PolicyGroup(
            "PRV-001",
            "개인정보·로그 보호 정책",
            f"{topic} 업무의 개인정보, 민감정보, 로그 저장과 열람 기준을 정의한다.",
            (
                ("민감정보 제한", "주민등록번호, 인증번호, 결제 전체 정보, 계좌 전체 번호, 상세 상담 내용 등 민감정보는 정책서와 고객 안내에 원문으로 노출하지 않는다."),
                ("마스킹 기준", "휴대폰 번호, 이메일, 계좌, 카드, 주소 등 식별 정보는 업무상 필요한 최소 범위만 표시하고 나머지는 마스킹한다."),
                ("로그 보관", "서비스 이용 로그는 운영 분석 목적 1년, 계약·청구·결제 증적은 관련 법령 및 SKT 보관 기준에 따라 최대 5년 범위에서 보관한다."),
                ("운영자 열람", "운영자 열람은 업무상 필요한 권한자에게만 허용하고, 열람자, 열람 일시, 열람 목적을 감사 이력으로 저장한다."),
            ),
        ),
        PolicyGroup(
            "QUL-001",
            "품질 관리 정책",
            f"{topic} 업무의 정확성, 완결성, 안정성, 고객 이해 가능성을 관리하는 기준을 정의한다.",
            (
                ("품질 지표", "성공률, 실패율, 처리 지연, 상담 전환율, 재시도율, 고객 피드백, 오류 유형을 품질 지표로 관리한다."),
                ("모니터링 주기", "핵심 처리 오류와 연계 장애는 상시 모니터링하고, 기준 정보 품질과 고객 피드백은 최소 주 1회 점검한다."),
                ("보정 대상", "반복 실패, 정보 불일치, 고객 오인 가능 문구, 정책값 누락, 상담 전환 급증은 보정 대상으로 등록한다."),
                ("개선 반영", "품질 개선 사항은 요구사항 분석 결과 또는 운영 변경 이력에 반영하고, 적용 후 지표 변화를 확인한다."),
            ),
        ),
    ]
    analysis_items = requirement_analysis_policy_items(ctx)
    if analysis_items:
        groups.append(
            PolicyGroup(
                "ANL-001",
                "요구사항 분석 보강 정책",
                f"{topic} 관련 요구사항을 분석해 추가로 정의해야 하는 노출, 검증, 운영, 예외 기준을 정의한다.",
                tuple(analysis_items),
            )
        )
    reference_items = reference_analysis_policy_items(ctx)
    if reference_items:
        groups.append(
            PolicyGroup(
                "REF-001",
                "참고자료 분석 보강 정책",
                f"{topic} 관련 참고자료에서 학습한 채널 전략, 고객 불편, IA, 벤치마킹, AI 관점을 정책 기준으로 정의한다.",
                tuple(reference_items),
            )
        )
    return groups


def final_check_section(ctx, profile: TopicProfile) -> str:
    checks = [
        ("범위 정합성", f"{ctx.topic} 업무의 포함 범위와 제외 범위가 고객 과업 기준으로 구분되어 있는지 확인한다."),
        ("고객 완결성", "고객이 앱·웹에서 조회, 조건 확인, 처리 요청, 결과 확인을 완료할 수 있는지 확인한다."),
        ("BSS·연계 시스템 포함성", "BSS와 연계 시스템이 수행하는 검증, 판정, 상태 변경, 결과 회신이 프로세스와 기능에 포함되어 있는지 확인한다."),
        ("상태 전이 정합성", "상태 전이표의 현재 상태와 다음 상태가 상태 코드 목록에 존재하는지 확인한다."),
        ("프로세스-기능-정책 연결성", "모든 프로세스에 관련 기능과 정책 목록의 정책 ID·정책명이 연결되어 있는지 확인한다."),
        ("정책 구체성", "정책 상세가 실제 기능 동작값, 허용 목록, 횟수, 시간, 제한 조건, 채널, 예외 기준, 이력 저장 기준을 포함하는지 확인한다."),
        ("개인정보·로그 보호", "민감정보 마스킹, 로그 보관, 운영자 열람 제한, 감사 이력 기준이 포함되어 있는지 확인한다."),
        ("운영 관리 가능성", "운영 기준 등록, 검수, 승인, 배포, 롤백, 품질 모니터링 기준이 포함되어 있는지 확인한다."),
        ("요구사항 분석 반영", "요구사항 통합 list에서 확인한 고객 과업, 검증 조건, 운영 기준, 예외 기준이 정책 판단 기준으로 재구성되어 있는지 확인한다."),
    ]
    if references_for(ctx):
        checks.append(("참고자료 분석 반영", "references 자료에서 확인한 채널 전략, 고객 불편, IA, 벤치마킹, AI 관점이 프로세스, 기능, 정책 기준으로 재구성되어 있는지 확인한다."))
    items = "".join(f'<div class="guide-section-title">{index}. {esc(title)}</div>{esc(body)}<br/>' for index, (title, body) in enumerate(checks, start=1))
    return f"""
<h2>최종 점검 기준</h2>
<div class="guide">
<div class="guide-title">{esc(ctx.topic)} 정책서 제출 전 점검</div>
{items}
</div>
"""


def requirements_for(ctx) -> Sequence[object]:
    return getattr(ctx, "requirements", ()) or ()


def references_for(ctx) -> Sequence[object]:
    return getattr(ctx, "references", ()) or ()


def authoring_basis_text(ctx) -> str:
    basis = []
    if requirements_for(ctx):
        basis.append("요구사항 통합 list의 관련 4depth 항목을 검토해 정책 판단 기준으로 재구성한다.")
    else:
        basis.append("매칭된 요구사항이 없으면 AGENTS.md 공통 작성 기준과 샘플 정책서 구조를 기준으로 작성한다.")

    if references_for(ctx):
        basis.append(f"references 폴더의 관련 참고자료 {len(references_for(ctx))}건을 분석해 채널 전략, 고객 불편, IA, 벤치마킹 관점을 반영한다.")
    else:
        basis.append("references 자료가 없으면 AGENTS.md와 샘플 기준을 우선 적용한다.")
    return "<br/>".join(esc(item) for item in basis)


def requirements_cover_text(ctx) -> str:
    if not requirements_for(ctx):
        return "AGENTS.md 공통 작성 기준과 샘플 정책서 구조를 기준으로 작성한다."
    return "요구사항 통합 list의 관련 4depth 항목을 검토해 정책 판단 기준으로 재구성한다."


def requirement_analysis_section(ctx) -> str:
    analysis = requirement_analysis(ctx)
    if not analysis:
        return ""

    rows = [
        tr(
            td(esc(item["label"]), style="width: 160px;"),
            td(esc(item["definition"])),
            td(esc(item["policy_focus"])),
        )
        for item in analysis
    ]
    return f"""
<h3>다. 요구사항 분석 반영 방향</h3>
<p class="plain-text">요구사항 통합 list의 관련 4depth 항목을 검토해 본 정책서에서 추가로 정의해야 할 기준을 도출한다.<br/>요구사항 문구를 그대로 나열하지 않고 고객 과업, 시스템 판단, 운영 기준, 예외 처리 기준으로 재구성해 이후 장에 반영한다.</p>
<table>
<thead>{tr(th("분석 영역", style="width: 160px;"), th("정의해야 할 내용"), th("정책서 반영 방향"))}</thead>
<tbody>{''.join(rows)}</tbody>
</table>
"""


def requirement_analysis(ctx) -> List[dict]:
    requirements = requirements_for(ctx)
    if not requirements:
        return []

    categories = []
    for requirement in requirements:
        category = requirement_category(requirement)
        if category not in categories:
            categories.append(category)

    order = ["information", "benefit", "payment", "auth", "data", "operation", "exception"]
    categories.sort(key=lambda category: order.index(category) if category in order else 99)
    return [requirement_category_insight(category) for category in categories]


def requirement_category_insight(category: str) -> dict:
    return {
        "information": {
            "category": "information",
            "label": "정보 구조·노출",
            "definition": "고객이 판단에 필요한 핵심 정보, 비교 기준, 상태 정보, 기준일시, 노출 우선순위를 정의해야 한다.",
            "policy_focus": "대상 정보 노출 정책, 가능 여부 검증 정책, 결과 안내 기준에 반영한다.",
        },
        "benefit": {
            "category": "benefit",
            "label": "혜택·조건·영향",
            "definition": "혜택, 할인, 쿠폰, 포인트, 재고, 적용 가능 조건, 중복 또는 제외 조건을 고객 영향 기준으로 정의해야 한다.",
            "policy_focus": "영향도 고지 정책, 가능 여부 검증 정책, 예외·상담 전환 정책에 반영한다.",
        },
        "payment": {
            "category": "payment",
            "label": "결제·청구·납부",
            "definition": "결제 방식, 청구 방식, 할부 또는 납부 조건, 결제 실패 후속 처리를 정의해야 한다.",
            "policy_focus": "인증·동의 정책, 처리 결과·이력 정책, 개인정보·로그 보호 정책에 반영한다.",
        },
        "auth": {
            "category": "auth",
            "label": "인증·동의·권한",
            "definition": "개인화 정보 노출, 민감정보 처리, 본인확인, 약관 동의, 권한 실패 기준을 정의해야 한다.",
            "policy_focus": "접근·권한 정책, 인증·동의 정책, 개인정보·로그 보호 정책에 반영한다.",
        },
        "data": {
            "category": "data",
            "label": "검색·추천·데이터",
            "definition": "검색, 추천, 개인화, 데이터 활용 범위, 신뢰도, 폴백, 로그 저장 기준을 정의해야 한다.",
            "policy_focus": "대상 정보 노출 정책, 개인정보·로그 보호 정책, 품질 관리 정책에 반영한다.",
        },
        "operation": {
            "category": "operation",
            "label": "전시·운영 관리",
            "definition": "템플릿, 문구, 기준 정보, 상품 또는 혜택 관계, 운영 변경, 검수·승인·배포 기준을 정의해야 한다.",
            "policy_focus": "운영 관리 정책, 품질 관리 정책, 대상 정보 노출 정책에 반영한다.",
        },
        "exception": {
            "category": "exception",
            "label": "예외·상담·장애",
            "definition": "오류, 제한, 장애, 반복 실패, 상담 전환, 대체 경로와 고객 안내 기준을 정의해야 한다.",
            "policy_focus": "예외·상담 전환 정책, 처리 결과·이력 정책, 품질 관리 정책에 반영한다.",
        },
    }[category]


def has_requirement_category(analysis: Sequence[dict], category: str) -> bool:
    return any(item.get("category") == category for item in analysis)


def requirement_analysis_policy_items(ctx) -> List[tuple[str, str]]:
    items: List[tuple[str, str]] = []
    for item in requirement_analysis(ctx):
        category = item.get("category")
        if category == "information":
            items.extend(
                [
                    ("핵심 정보 우선순위", "고객이 판단에 필요한 가격, 혜택, 조건, 상태, 비교 기준은 업무 흐름 상단 또는 주요 확인 단계에서 우선 제공한다."),
                    ("변동 정보 기준일", "가격, 혜택, 가능 상태처럼 변동 가능한 정보는 조회 기준일시 또는 적용 예정일을 함께 제공한다."),
                ]
            )
        elif category == "benefit":
            items.extend(
                [
                    ("혜택 적용 가능성 판정", "혜택, 할인, 쿠폰, 포인트 적용 가능성은 고객 상태, 대상 조건, 사용 기간, 중복 제한을 기준으로 사전 검증한다."),
                    ("중복·제외 조건 고지", "중복 사용 제한, 제외 대상, 소멸 가능성, 적용 순서는 고객이 확정하기 전에 이해할 수 있도록 안내한다."),
                ]
            )
        elif category == "payment":
            items.extend(
                [
                    ("결제·청구 선택 기준", "결제, 청구, 납부 방식은 상품 특성, 고객 상태, 인증 조건, 연계 시스템 가능 여부를 기준으로 선택 가능 범위를 제한한다."),
                    ("결제 실패 후속 처리", "결제 실패 또는 청구 제한이 발생하면 실패 사유, 재시도 가능 여부, 대체 수단, 상담 전환 기준을 함께 안내한다."),
                ]
            )
        elif category == "auth":
            items.extend(
                [
                    ("권한·동의 선행 조건", "개인화 정보 노출, 민감정보 조회, 변경·결제성 처리는 본인확인과 필수 동의가 완료된 경우에만 허용한다."),
                    ("권한 실패 대체 경로", "권한 또는 동의 조건을 충족하지 못하면 상세 정보 대신 로그인, 본인확인, 동의 갱신, 상담 연결 중 가능한 경로를 안내한다."),
                ]
            )
        elif category == "data":
            items.extend(
                [
                    ("데이터 활용 범위 제한", "검색, 추천, 개인화 결과는 고객 동의, 이용 맥락, 데이터 신뢰도, 업무 목적에 부합하는 범위에서만 생성한다."),
                    ("개인화 폴백 기준", "개인화 판단 근거가 부족하거나 신뢰도가 낮으면 공통 결과, 기본 정렬, 상담 연결처럼 안전한 대체 경로로 전환한다."),
                ]
            )
        elif category == "operation":
            items.extend(
                [
                    ("운영 기준 검수", "전시 기준, 문구, 템플릿, 기준 정보, 상품 관계 변경은 고객 영향 검수와 승인 후 배포한다."),
                    ("운영 변경 회수 기준", "배포 후 오류, 고객 오인, 기준 불일치가 확인되면 노출 중단, 직전 기준 복구, 변경 이력 저장을 수행한다."),
                ]
            )
        elif category == "exception":
            items.extend(
                [
                    ("제한·오류 후속 처리", "오류, 장애, 제한, 반복 실패는 고객 영향도에 따라 재시도, 대체 경로, 상담 전환, 운영 확인으로 분류한다."),
                    ("예외 안내 완결성", "예외 안내에는 실패 사유, 고객이 할 수 있는 다음 행동, 예상 처리 시간, 추가 문의 경로를 포함한다."),
                ]
            )
    return items


def reference_analysis_section(ctx) -> str:
    analysis = reference_analysis(ctx)
    if not analysis:
        return ""

    rows = []
    for item in analysis:
        label = f'{esc(item["label"])}<br/><span class="mono">{item["count"]}건</span>'
        rows.append(
            tr(
                td(label, style="width: 170px;"),
                td(esc(item["summary"])),
                td(esc(item["policy_focus"])),
            )
        )
    return f"""
<h3>라. 참고자료 분석 반영 방향</h3>
<p class="plain-text">references 폴더의 관련 자료를 검토해 {esc(ctx.topic)} 정책서에서 강화해야 할 채널 전략, 고객 불편, IA, 벤치마킹, AI 적용 관점을 도출한다.<br/>참고자료 원문을 그대로 옮기지 않고 고객 과업, 탐색 흐름, 검증 기준, 예외 안내, 운영 기준으로 재구성해 이후 장에 반영한다.</p>
<table>
<thead>{tr(th("참고 관점", style="width: 170px;"), th("학습한 작성 방향"), th("정책서 반영 기준"))}</thead>
<tbody>{''.join(rows)}</tbody>
</table>
"""


def reference_analysis(ctx) -> List[dict]:
    references = references_for(ctx)
    if not references:
        return []

    rows = []
    for category in reference_categories(ctx):
        category_refs = [reference for reference in references if getattr(reference, "category", "") == category]
        signals = reference_signals(category_refs)
        rows.append(
            {
                "category": category,
                "label": reference_category_label(category),
                "count": len(category_refs),
                "summary": "; ".join(signals[:3]) or reference_category_summary(category),
                "policy_focus": reference_category_policy_focus(category),
            }
        )
    return rows


def reference_categories(ctx) -> List[str]:
    order = ["strategy", "research", "voc", "ia", "benchmark", "ai", "general"]
    categories = []
    for reference in references_for(ctx):
        category = getattr(reference, "category", "general") or "general"
        if category not in categories:
            categories.append(category)
    categories.sort(key=lambda category: order.index(category) if category in order else 99)
    return categories


def has_reference_category(categories: Sequence[str], category: str) -> bool:
    return category in categories


def reference_signals(references: Sequence[object]) -> List[str]:
    signals: List[str] = []
    for reference in references:
        for signal in getattr(reference, "signals", ()) or ():
            if signal not in signals:
                signals.append(signal)
    if not signals:
        for reference in references:
            summary = getattr(reference, "summary", "")
            if summary and summary not in signals:
                signals.append(summary)
    return signals


def reference_category_label(category: str) -> str:
    return {
        "strategy": "채널 전략",
        "research": "고객 조사",
        "voc": "VoC",
        "ia": "IA·탐색 구조",
        "benchmark": "벤치마킹",
        "ai": "AI·개인화",
        "general": "업무 참고",
    }.get(category, "업무 참고")


def reference_category_summary(category: str) -> str:
    return {
        "strategy": "채널 통합 방향, 목적 기반 진입, 셀프 처리 확대, 경량화 관점을 확인한다.",
        "research": "고객 조사에서 드러난 이해도, 신뢰, 불편 요인을 확인한다.",
        "voc": "반복되는 문의, 혼란, 실패, 상담 전환 요인을 확인한다.",
        "ia": "메뉴 구조, 탐색 경로, 업무 연결 기준을 확인한다.",
        "benchmark": "비교·선택·처리 기대 수준과 외부 서비스 관점을 확인한다.",
        "ai": "AI, 검색, 추천, 개인화 적용 시 정확성, 신뢰도, 폴백 기준을 확인한다.",
        "general": "관련 참고자료의 업무 맥락을 확인한다.",
    }.get(category, "관련 참고자료의 업무 맥락을 확인한다.")


def reference_category_policy_focus(category: str) -> str:
    return {
        "strategy": "목적 기반 진입, 셀프 처리 우선, 채널 경량화 기준을 프로세스와 정책에 반영한다.",
        "research": "고객 이해도, 신뢰, 불편 요인을 안내, 검증, 예외 처리 기준에 반영한다.",
        "voc": "고객 문의와 실패 원인을 제한 사유, 고지, 상담 전환 기준에 반영한다.",
        "ia": "IA 경로와 후속 업무 연결을 유즈케이스, 프로세스, 기능 기준에 반영한다.",
        "benchmark": "비교·선택 기준과 처리 기대 수준을 대상 정보 노출, 영향도 고지 기준에 반영한다.",
        "ai": "AI·개인화는 정확성, 동의, 실행 가능성, 폴백 기준에 반영한다.",
        "general": "참고자료 맥락을 누락 방지와 정책 상세 보강 기준에 반영한다.",
    }.get(category, "참고자료 맥락을 누락 방지와 정책 상세 보강 기준에 반영한다.")


def reference_analysis_policy_items(ctx) -> List[tuple[str, str]]:
    items: List[tuple[str, str]] = []
    categories = reference_categories(ctx)
    if has_reference_category(categories, "strategy"):
        items.extend(
            [
                ("목적 기반 진입", "고객 진입은 내부 메뉴 구조가 아니라 고객이 해결하려는 목적을 기준으로 분기하고, 다음 행동을 명확히 제공한다."),
                ("셀프 처리 우선", "조회, 조건 확인, 신청, 변경, 결과 확인이 앱·웹에서 완료 가능한 경우 상담 전환보다 셀프 처리 경로를 우선 제공한다."),
            ]
        )
    if has_reference_category(categories, "research") or has_reference_category(categories, "voc"):
        items.extend(
            [
                ("고객 불편 사전 제거", "고객 조사와 VoC에서 반복되는 혼란, 오인, 실패 요인은 처리 전 안내, 제한 사유, 예외 기준으로 선반영한다."),
                ("상담 전환 명확화", "셀프 처리로 해결하기 어려운 경우 고객이 해야 할 다음 행동, 상담 연결 사유, 준비 정보를 함께 안내한다."),
            ]
        )
    if has_reference_category(categories, "ia"):
        items.extend(
            [
                ("IA 경로 일관성", "메뉴, 검색, 알림, 외부 링크로 진입하더라도 동일한 업무 기준과 상태 판단을 적용한다."),
                ("후속 업무 연결", "고객이 확인 후 수행해야 하는 신청, 변경, 결제, 상담, 관리 업무는 단절 없이 연결한다."),
            ]
        )
    if has_reference_category(categories, "benchmark"):
        items.extend(
            [
                ("비교·선택 기준 명료화", "고객이 여러 상품, 혜택, 조건을 비교해야 하는 경우 핵심 비교 기준과 제한 조건을 같은 기준으로 제공한다."),
                ("외부 기대 수준 점검", "외부 서비스에서 일반화된 확인, 비교, 변경, 결제 경험 수준을 고객 안내와 처리 기준 보강에 활용한다."),
            ]
        )
    if has_reference_category(categories, "ai"):
        items.extend(
            [
                ("AI 정확성 우선", "AI, 검색, 추천, 개인화 결과는 신뢰도와 실행 가능성이 기준을 충족할 때만 고객 업무 경로로 연결한다."),
                ("AI 폴백 기준", "AI 판단 근거가 부족하거나 결과가 불확실하면 공통 안내, 직접 검색, 상담 전환 같은 안전한 대체 경로를 제공한다."),
            ]
        )
    if has_reference_category(categories, "general"):
        items.append(("참고자료 기반 누락 점검", "관련 참고자료에서 확인한 업무 맥락은 정책 범위, 예외, 운영 기준 누락 점검에 활용한다."))
    return items


def requirement_text(requirement) -> str:
    values = (
        getattr(requirement, "parent_name", ""),
        getattr(requirement, "parent_description", ""),
        getattr(requirement, "detail_name", ""),
        getattr(requirement, "detail_description", ""),
    )
    return " ".join(values)


def requirement_category(requirement) -> str:
    text = requirement_text(requirement)
    if contains_any(text, ("검색", "추천", "개인화", "AI", "데이터", "트래킹", "로그")):
        return "data"
    if contains_any(text, ("결제", "납부", "청구", "할부", "수납", "카드", "계좌")):
        return "payment"
    if contains_any(text, ("쿠폰", "혜택", "할인", "포인트", "멤버십", "이벤트", "미션")):
        return "benefit"
    if contains_any(text, ("인증", "동의", "본인", "권한", "회원", "개인정보")):
        return "auth"
    if contains_any(text, ("운영", "관리", "템플릿", "문구", "전시", "노출", "카탈로그", "Catalog", "NOVA", "EPC")):
        return "operation"
    if contains_any(text, ("오류", "실패", "장애", "상담", "문의", "CS", "FAQ", "공지")):
        return "exception"
    return "information"


def contains_any(text: str, keywords: Sequence[str]) -> bool:
    normalized = text.casefold()
    return any(keyword.casefold() in normalized for keyword in keywords)


def tr(*cells: str) -> str:
    return "<tr>" + "".join(cells) + "</tr>"


def th(content: str, style: str = "") -> str:
    style_attr = f' style="{style}"' if style else ""
    return f"<th{style_attr}>{content}</th>"


def td(content: str, class_name: str = "", style: str = "") -> str:
    attrs = ""
    if class_name:
        attrs += f' class="{class_name}"'
    if style:
        attrs += f' style="{style}"'
    return f"<td{attrs}>{content}</td>"


def policy_item_content(value: object) -> str:
    lines = policy_item_content_lines(value)
    if not lines:
        return "-"
    return "".join(
        f'<span class="policy-item-line">- {html.escape(line, quote=False)}</span>'
        for line in lines
    )


def policy_item_content_lines(value: object) -> List[str]:
    text = html.unescape(str(value or ""))
    text = re.sub(r"</?br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    lines: List[str] = []
    for raw_line in re.split(r"\n+", text):
        raw_line = re.sub(r"\s+", " ", raw_line).strip()
        raw_line = re.sub(r"^[-•]\s*", "", raw_line).strip()
        if not raw_line:
            continue
        start = 0
        for match in re.finditer(r"(?<!\d)([.!?])\s+(?=\S)", raw_line):
            line = raw_line[start : match.start(1) + 1].strip()
            if line:
                lines.append(line)
            start = match.end()
        tail = raw_line[start:].strip()
        if tail:
            lines.append(tail)
    return lines


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)
