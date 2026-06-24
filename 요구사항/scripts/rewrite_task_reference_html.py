#!/usr/bin/env python3
"""Rewrite TK task definition PDFs into curated HTML reference pages."""

from __future__ import annotations

import html
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "output" / "reference_html" / "task_definitions_manifest.json"
OUT_DIR = ROOT / "output" / "reference_html"
ASSET_DIR = OUT_DIR / "assets"


DOCS = {
    "tk-task-01": {
        "domain": "AI 탐색 · 추천 · 데이터",
        "tagline": "검색, 추천, 비교, 실행, 트래킹을 하나의 AI Agent 여정으로 재구성한다.",
        "interpretation": "원문은 AI 챗봇 고도화가 아니라, 고객 과업의 시작부터 처리 완료와 학습 데이터 확보까지 이어지는 실행형 Agent 체계를 요구한다.",
        "problem": {
            "current": "검색, 챗봇, 추천, 업무처리가 서로 분리되어 고객이 탐색 후 별도 메뉴로 이동해야 한다.",
            "pain": "비교와 판단을 고객이 직접 수행하고, 추천 근거와 후속 행동이 약해 재탐색과 상담 전환이 반복된다.",
            "root": "통합 Agent 진입점, 개인화 추천 기준, Next Action, 행동 데이터 표준이 아직 하나의 운영 체계로 묶이지 않았다.",
            "risk": "전환 기회를 놓치고 AI 서비스 개선을 위한 학습 데이터와 품질 관리 루프가 약해진다.",
        },
        "flow": ["요청 입력", "의도 분해", "비교 · 추천", "실행 연결", "반응 수집", "정책 보정"],
        "nodes": ["고객 맥락", "AI Agent", "추천 가드레일", "Next Action", "성과 트래킹"],
        "pillars": [
            ("End-to-End Agent", "탐색, 비교, 추천, 처리, 문제해결을 단일 대화/카드 흐름으로 묶는다.", "이탈률, Agent 처리 완료율"),
            ("컨시어지형 추천", "고객 상태, 이력, 상품 맥락을 반영해 추천안과 근거를 함께 제시한다.", "추천 수용률, 추천 전환율"),
            ("수익성 가드레일", "고객 적합성과 사업 우선순위를 함께 적용해 노출/비노출/예외 기준을 둔다.", "추천 매출 기여도"),
            ("셀프진화 운영", "반응, 미수용, 과노출 데이터를 기반으로 추천 정책을 실험하고 보정한다.", "정책 반영 리드타임"),
        ],
        "workstreams": [
            ("AI Agent 진입", "홈/MY/검색 접점에서 공통 진입점을 제공하고 예시 질문을 개인화한다.", "발화 유형, 민감정보 예외, 진입 위치"),
            ("의도 분석", "탐색/비교/추천/처리/문제해결로 복합 요청을 분해한다.", "추가 질문 기준, 고위험 업무 분기"),
            ("추천 전시", "추천 대상, 추천 이유, 비교 결과, 대안을 카드/표로 제시한다.", "추천 근거, 노출 우선순위, 제외 조건"),
            ("Next Action", "약정 만료, 데이터 초과 위험, 여정 이탈 등 트리거별 행동 제안을 연결한다.", "노출 빈도, 유효기간, 숨김/저장"),
            ("트래킹", "질문, 추천 반응, 실행, 이탈, 상담 전환을 표준 이벤트로 수집한다.", "이벤트 스키마, 실험/성과 지표"),
        ],
        "policy_focus": [
            "Agent가 직접 실행 가능한 업무와 안내만 가능한 업무를 구분한다.",
            "추천 근거, 우선순위, 제외 조건, 과노출 방지 기준을 정책 항목으로 둔다.",
            "고객 행동 데이터는 수집 목적, 보관 기간, 민감정보 제외 기준을 명확히 한다.",
        ],
        "evidence": [
            ("p.1", "과제 목적과 문제 정의가 AI Agent, 추천 전시, 데이터 트래킹을 하나의 과제로 묶는다."),
            ("p.3", "추천 체계, 수익성 가드레일, 셀프진화형 운영, Next Action이 핵심 지향점으로 제시된다."),
            ("p.4-p.6", "Agent 요청, 의도 분석, 실행 연결, 추천 성과 측정, 개선 인사이트 도출 프로세스가 이어진다."),
        ],
    },
    "tk-task-02": {
        "domain": "결제",
        "tagline": "금액 이해, 할인 적용, 결제수단 선택, 실패 복구를 표준 결제 경험으로 묶는다.",
        "interpretation": "원문은 결제 UI 정비보다 결제 구조의 신뢰 확보를 강조한다. 고객은 왜 이 금액인지 알고, 선호 수단으로, 실패해도 복구 가능한 흐름을 기대한다.",
        "problem": {
            "current": "금액 구조, 결제수단, 결제 고객 정보가 상품과 채널별로 다르게 운영된다.",
            "pain": "고객은 혜택 적용 결과와 최종 금액을 이해하기 어렵고, 선호 결제수단 제한으로 이탈한다.",
            "root": "결제 단계, 용어, UI, 결제 데이터 재사용 기준이 표준화되어 있지 않다.",
            "risk": "결제 완료율 저하, 결제 실패 CS 증가, 매출 기회 손실이 지속된다.",
        },
        "flow": ["결제 진입", "금액 구조 확인", "혜택 적용", "수단 선택", "승인 · 반영", "실패 복구"],
        "nodes": ["주문/상품", "금액 해석", "할인 엔진", "결제수단", "결과 안내"],
        "pillars": [
            ("투명한 금액 구조", "상품 금액, 할인, 포인트, 최종 결제 금액을 같은 순서와 용어로 보여준다.", "결제 전 문의율"),
            ("간편결제 다양성", "네이버페이, 카카오페이, 토스페이 등 선호 수단을 단계적으로 확장한다.", "간편결제 이용률"),
            ("결제정보 재사용", "최근/기본/선호 결제수단을 재사용해 반복 입력을 줄인다.", "평균 결제 소요 시간"),
            ("실패/불안 대응", "이중납부, 자동납부 실패, 미반영 상태를 사전에 설명하고 복구 경로를 제공한다.", "결제 실패 복구율"),
        ],
        "workstreams": [
            ("결제 진입", "주문/상품 단위 결제 요약과 결제 유형을 사전 안내한다.", "후불/선불/청구 반영 표시"),
            ("할인 적용", "포인트, 쿠폰, 제휴카드 적용 결과를 실시간으로 갱신한다.", "중복 불가, 최소 금액, 우선 적용"),
            ("결제수단 선택", "최근/기본/선호 수단을 우선 노출하고 수단별 처리 방식을 안내한다.", "즉시/청구/분할 기준"),
            ("승인 및 결과", "승인, 실패, 반영 대기, 청구 반영 완료 상태를 고객 언어로 안내한다.", "상태 코드, 알림 기준"),
            ("예외 복구", "자동납부 실패, 중복납부 우려, 승인 지연 시 대체 결제와 확인 경로를 제공한다.", "재시도, 환불, 문의 전환"),
        ],
        "policy_focus": [
            "금액 표시 순서와 할인 적용 우선순위를 모든 결제 접점에서 동일하게 둔다.",
            "결제 실패, 승인 지연, 청구 반영 대기 상태의 후속 행동을 상태 전이로 관리한다.",
            "저수수료 수단 추천은 고객 선호와 결제 가능성을 침해하지 않는 범위로 제한한다.",
        ],
        "evidence": [
            ("p.1-p.2", "복잡한 금액/청구 구조와 채널별 결제 방식 차이가 핵심 문제로 정리되어 있다."),
            ("p.2-p.3", "간편결제 확대, 결제수단 재사용, 일관된 결제 UX가 지향점으로 제시된다."),
            ("p.3-p.5", "결제 진입, 할인 적용, 결제수단 선택, 결과 확인과 예외 대응 기능이 나열된다."),
        ],
    },
    "tk-task-03": {
        "domain": "상품 · 할인",
        "tagline": "상품/혜택/할인 데이터를 AI가 이해 가능한 지식 자산으로 표준화한다.",
        "interpretation": "원문의 핵심은 상품 상세 화면 개선이 아니라, 비교, 시뮬레이션, 담기, 추천을 움직이는 공통 상품 지식 체계를 만드는 것이다.",
        "problem": {
            "current": "상품과 할인 정보가 플랫폼과 프로세스별로 분산되어 상세, 비교, 시뮬레이션, 담기가 끊어진다.",
            "pain": "고객은 요금제, 약정, 결합, 혜택의 관계를 이해하기 어렵고 변경 결과를 예측하지 못한다.",
            "root": "공통 스키마와 마스터 데이터가 부족하고, AI가 사용할 구조화된 상품 지식이 없다.",
            "risk": "상품 정보 불일치, 상담 의존, 운영 리드타임 증가, 개인화 추천 역량 부족이 이어진다.",
        },
        "flow": ["상품 등록", "AI 전시정보 생성", "상세 · 비교", "가격 시뮬레이션", "담기", "장바구니"],
        "nodes": ["상품 원장", "지식 스키마", "AI 설명", "시뮬레이터", "전환"],
        "pillars": [
            ("상품 지식자산", "상품명, 조건, 대상, 혜택, 제한사항, 비교 항목을 공통 스키마로 표준화한다.", "정보 탐색 이탈률"),
            ("AI 생산 체계", "AI가 원장 기반 설명, Q&A, 비교 문구를 생성하고 운영자가 검수한다.", "운영 리드타임"),
            ("비교/시뮬레이션", "현재 상품과 후보 상품의 가격, 혜택, 위약/약정 영향을 같은 기준으로 계산한다.", "시뮬레이션 이용률"),
            ("담기/전환 연결", "옵션, 약정, 할인 조건을 담기와 장바구니까지 유지한다.", "담기 후 전환율"),
        ],
        "workstreams": [
            ("상품 등록", "상품 기본 정보, 혜택, 할인, 운영 조건을 구조화해 등록한다.", "필수 속성, 검수 기준"),
            ("AI 전시 생성", "원장 정보를 고객 설명 문구와 비교 요소로 변환한다.", "AI 생성물 승인/반려"),
            ("상품 상세", "상태, 옵션, 추천 상품, 공유 정보를 한 흐름에서 제공한다.", "노출 가능 상태, 옵션 선택"),
            ("시뮬레이션", "고객 정보 기준 실시간 가격/할인 결과를 계산한다.", "계산 기준, 예외 메시지"),
            ("장바구니", "담기 시점 조건을 유지하고 가격/할인 변동을 재검증한다.", "유효기간, 가격 변경 고지"),
        ],
        "policy_focus": [
            "상품/할인 항목은 화면 문구가 아니라 판단 가능한 데이터 속성으로 정의한다.",
            "시뮬레이션 결과는 적용 기준일, 고객 상태, 제한 조건, 변동 가능성을 함께 표시한다.",
            "AI 생성 상품 설명은 원장 불일치, 과장 표현, 제한 조건 누락을 검수해야 한다.",
        ],
        "evidence": [
            ("p.1-p.2", "상품/할인 정보 분산과 비교/시뮬레이션 단절이 문제로 제시된다."),
            ("p.2-p.4", "상품 지식자산, AI 기반 생산, 비교/추천/시뮬레이션이 지향점으로 연결된다."),
            ("p.4-p.5", "상품등록, 전시정보 생성, 상세, 담기, 시뮬레이션, 장바구니 기능이 정리된다."),
        ],
    },
    "tk-task-04": {
        "domain": "상품 · 서비스 자산",
        "tagline": "데이터, 쿠폰, 바코드, 이용권을 고객의 ‘내 자산’ 관점으로 다시 묶는다.",
        "interpretation": "원문은 자산별 기능을 늘리는 것이 아니라, 고객이 보유/사용/만료/공유 상태를 한 번에 이해하고 바로 실행하도록 만드는 과제다.",
        "problem": {
            "current": "가입상품에서 발생하는 자산이 채널별, 유형별로 다른 구조와 이용 방식으로 제공된다.",
            "pain": "고객은 여러 메뉴를 이동해야 하며 자산의 사용 가능 상태, 만료, 공유 가능 여부를 한눈에 알기 어렵다.",
            "root": "자산 속성, 사용 맥락, 공유 맥락을 통합한 정보 구조와 안내 기준이 부족하다.",
            "risk": "혜택 체감도와 자산 이용률이 낮아지고, 핵심 업무 전환과 만족도가 함께 떨어진다.",
        },
        "flow": ["자산 통합 조회", "상태 판단", "사용 · 충전", "공유 · 선물", "이력 확인", "후속 추천"],
        "nodes": ["보유 자산", "상태/만료", "실행 액션", "공유 관계", "활용 추천"],
        "pillars": [
            ("내 자산 대시보드", "데이터, 통화, 쿠폰, 바코드, 이용권을 단일 화면에서 보여준다.", "자산 조회 이용률"),
            ("상황형 퀵액션", "잔여량, 만료, 해외 이용, 가족 여부에 따라 충전/선물/사용을 제안한다.", "퀵액션 전환율"),
            ("공유/관계 반영", "가족, 다회선, 미성년, 대표 회선 같은 관계 기준을 자산 사용에 반영한다.", "공유 성공률"),
            ("이용 후 루프", "사용 결과와 만료 예정, 추가 구매/업그레이드 추천을 이어준다.", "재사용률"),
        ],
        "workstreams": [
            ("데이터·통화", "잔여량, 초과 위험, 예상 소진 시점, 충전/선물 액션을 제공한다.", "실시간성, 초과 고지"),
            ("로밍 쿠폰", "해외 체류/출국 맥락에서 보유 쿠폰과 추가 구매를 안내한다.", "국가/기간/적용 조건"),
            ("혜택 쿠폰", "보유, 사용 가능, 만료 예정, 사용 완료를 상태로 관리한다.", "사용처, 유효기간"),
            ("할인 바코드", "멤버십 등급과 사용 가능 혜택을 즉시 확인하게 한다.", "대표 회선, 제휴 제한"),
            ("이용권", "구독/부가서비스 이용권의 등록, 사용, 만료를 추적한다.", "중복 사용, 양도 가능 여부"),
        ],
        "policy_focus": [
            "자산별 상태값은 보유/사용가능/만료예정/사용완료/제한으로 표준화한다.",
            "공유·선물·충전은 관계, 권한, 잔여량, 유효기간 기준을 함께 판단한다.",
            "고객에게 보이는 자산명과 BSS/제휴 회신 상태의 매핑 기준을 둔다.",
        ],
        "evidence": [
            ("p.1-p.2", "가입상품에서 발생하는 자산의 이용 구조와 경험 재설계가 과제 목적이다."),
            ("p.2-p.3", "분산된 자산 정보와 채널별 이용 방식 차이가 As-Is 문제로 제시된다."),
            ("p.4-p.6", "데이터/통화, 충전, 선물, 쿠폰, 바코드, 이용권 관련 기능이 구체화된다."),
        ],
    },
    "tk-task-05": {
        "domain": "이벤트 · 멤버십 · 리워드",
        "tagline": "혜택 탐색을 방문 트리거와 재방문 루프로 바꾸는 통합 혜택 허브를 만든다.",
        "interpretation": "원문은 이벤트 목록 통합이 아니라, 참여, 보상, 혜택 사용, 상품/서비스 전환으로 이어지는 고객 행동 퍼널 설계를 요구한다.",
        "problem": {
            "current": "이벤트, 멤버십 혜택, 리워드가 채널별로 분산되고 일회성 혜택 중심으로 운영된다.",
            "pain": "고객은 지금 받을 수 있는 혜택을 체감하기 어렵고, 보상이 후속 행동으로 이어지지 않는다.",
            "root": "고객 행동 정의, 개인화 노출, 통합 운영 Admin, 리워드 생태계가 분리되어 있다.",
            "risk": "방문 동기와 멤버십 체감 가치가 약해져 리텐션과 로열티가 낮아진다.",
        },
        "flow": ["혜택 허브", "개인화 탐색", "참여 · 미션", "보상 수령", "혜택 사용", "후속 전환"],
        "nodes": ["혜택 허브", "미션", "리워드", "멤버십", "운영 Admin"],
        "pillars": [
            ("혜택 구조 단순화", "이벤트, 미션, 멤버십, 쿠폰, 포인트를 공통 라벨과 상태로 보여준다.", "혜택 탐색률"),
            ("개인화 추천", "등급, 상품, 행동, 맥락에 맞는 이벤트와 혜택을 우선 노출한다.", "추천 참여율"),
            ("참여-보상 루프", "참여, 달성, 보상 수령, 사용, 후속 상품 탐색을 하나의 흐름으로 연결한다.", "재방문율"),
            ("운영 체계화", "사업 부서와 제휴사 혜택을 빠르게 등록, 검수, 운영, 성과 측정한다.", "운영 리드타임"),
        ],
        "workstreams": [
            ("통합 허브", "이벤트·멤버십·미션을 한 화면에서 탐색하고 상태별로 필터링한다.", "진행/예정/종료 상태"),
            ("개인화 추천", "등급, 보유 상품, 행동 이력으로 참여 가능 혜택을 제안한다.", "추천 제외/우선순위"),
            ("미션 운영", "진행률, 누적 달성, 다음 보상 조건을 시각화한다.", "달성 판정, 부정 참여 제한"),
            ("리워드 관리", "쿠폰, 포인트, 바코드, 제휴 혜택 수령과 사용 상태를 통합한다.", "지급/회수/만료"),
            ("Admin", "이벤트 등록, 대상 설정, 제휴 연동, 성과 모니터링을 운영한다.", "승인, 배포, 긴급 중단"),
        ],
        "policy_focus": [
            "참여 자격, 중복 참여, 보상 지급, 만료, 회수 기준을 분리해 정책화한다.",
            "멤버십 등급/대표 회선/제휴 회신에 따른 노출 가능 여부를 상태로 관리한다.",
            "이벤트 후속 CTA는 고객 이익과 사업 목적의 우선순위 기준을 함께 둔다.",
        ],
        "evidence": [
            ("p.1-p.2", "방문 트리거, Engagement, Retention, 통합 혜택 Hub가 과제 목적이다."),
            ("p.2-p.4", "혜택 인지/사용/확인 경험 부족과 운영 분산 문제가 정리된다."),
            ("p.4-p.6", "허브, 개인화 추천, 미션 진행률, 리워드, Admin 운영 기능이 제시된다."),
        ],
    },
    "tk-task-06": {
        "domain": "전시 관리",
        "tagline": "메뉴와 링크 중심 전시를 고객 목적 기반 실행 허브로 재구성한다.",
        "interpretation": "원문은 홈 화면 개편이 아니라, 확인-이해-실행-완료 흐름으로 모듈을 재조합하는 전시 운영 체계를 요구한다.",
        "problem": {
            "current": "채널별 정보와 기능이 분산되고 메뉴/링크 중심으로 제공되어 시작점을 알기 어렵다.",
            "pain": "고객 맥락과 무관한 정보가 반복 노출되고, 자주 쓰는 기능과 필요한 행동이 전면에 배치되지 않는다.",
            "root": "서비스별 운영, 고정형 전시 방식, 통합 관점의 모듈 설계가 부족하다.",
            "risk": "탐색 피로와 전환 저하가 지속되고, 상품/정책 변화에 대한 운영 대응 속도가 늦어진다.",
        },
        "flow": ["전시 모듈화", "고객 맥락 판단", "우선순위 결정", "노출 · CTA", "실행 연결", "성과 보정"],
        "nodes": ["콘텐츠 모듈", "세그먼트", "우선순위", "홈/상세", "운영 성과"],
        "pillars": [
            ("목적 기반 구조", "상품, 혜택, 관리 화면을 확인-이해-실행-완료 흐름으로 재배치한다.", "탐색 이탈률"),
            ("모듈형 전시", "전시 요소를 최소 단위로 구조화해 위치와 조합을 유연하게 운영한다.", "운영 반영 시간"),
            ("개인화 허브", "홈을 고객별 상태와 우선 행동을 반영한 실행 허브로 전환한다.", "개인화 영역 클릭률"),
            ("성과 기반 운영", "노출, 클릭, 실행, 완료 지표로 전시 정책을 보정한다.", "전시-처리 전환율"),
        ],
        "workstreams": [
            ("홈 탐색", "내 상태, 미완료 업무, 추천 행동을 우선 노출한다.", "우선순위, 중복 노출"),
            ("전시 모듈", "배너, 카드, 리스트, CTA를 목적과 상태 기준으로 구조화한다.", "모듈 속성, 필수 문구"),
            ("세그먼트", "고객 상태, 상품, 이용 패턴, 캠페인 조건에 따라 노출 대상을 정한다.", "대상/제외 기준"),
            ("운영 Admin", "전시 등록, 승인, 배포, 긴급 중단, 실험을 관리한다.", "승인 권한, 배포 시간"),
            ("성과 분석", "노출부터 완료까지 퍼널 데이터를 집계해 전시를 보정한다.", "성과 지표, 실험 기준"),
        ],
        "policy_focus": [
            "전시 우선순위는 고객 긴급도, 업무 가능성, 사업 중요도 순으로 판단 기준을 둔다.",
            "노출/비노출/중복 노출/빈도 제한 정책은 모듈 단위로 관리한다.",
            "전시 클릭이 실제 업무 처리로 이어지는 연결성과 실패 시 대체 경로를 정의한다.",
        ],
        "evidence": [
            ("p.1-p.2", "확인-이해-실행-완료 흐름과 모듈형/운영형/개인화형 전시 체계가 제시된다."),
            ("p.2-p.4", "단순 링크 집합과 고정형 전시가 As-Is 문제로 정리된다."),
            ("p.4-p.6", "홈, 개인화 영역, 전시 운영, 성과 관리 기능이 연결된다."),
        ],
    },
    "tk-task-07": {
        "domain": "주문 경험",
        "tagline": "상품별 주문 화면이 아니라 재조합 가능한 표준 주문 모듈 체계를 만든다.",
        "interpretation": "원문은 가입/주문 화면 통합보다, 상품 유형이 늘어나도 공통 단계와 분기 규칙으로 조립 가능한 주문 운영 기반을 강조한다.",
        "problem": {
            "current": "상품/유형별 주문 단계와 인증 방식이 다르고 앱/웹 이원화와 반복 입력이 발생한다.",
            "pain": "복잡한 단계, 반복 입력, 채널별 흐름 차이로 주문 피로와 이탈이 발생한다.",
            "root": "공통 주문 프로세스, 정책 표준, 고객정보 재활용, 인증 통합 체계가 부족하다.",
            "risk": "셀프처리율 정체, 오프라인 의존, 주문 이탈, 정책 대응 비효율이 심화된다.",
        },
        "flow": ["고객 상태 정의", "가입 가능 확인", "옵션 구성", "인증 · 약관", "결제 · 개통", "완료 · 후속"],
        "nodes": ["표준 모듈", "고객 상태", "자격 검증", "계약/결제", "AI 지원"],
        "pillars": [
            ("표준 주문 모듈", "가입, 인증, 명의 검증, 조건 체크, 약관, 결제, 개통을 공통 모듈로 분리한다.", "신규 상품 적용 리드타임"),
            ("고객정보 재사용", "기보유 정보와 인증 상태를 재활용해 반복 입력을 줄인다.", "입력 단계 수"),
            ("예외 분기 표준화", "개별 화면 추가 대신 표준 모듈 내 분기 규칙으로 예외를 관리한다.", "예외 처리 완료율"),
            ("AI 주문 지원", "상품 선택, 조건 확인, 다음 단계 안내를 AI가 보조한다.", "AI 지원 전환율"),
        ],
        "workstreams": [
            ("로그인 상태 정의", "비로그인/로그인/최근 주문 이어하기 가능 여부를 판단한다.", "로그인 필수 시점"),
            ("자격/조건 확인", "명의, 회선, 약정, 재고, 가입 가능 조건을 사전 검증한다.", "검증 실패 복구"),
            ("옵션/계약 구성", "상품 옵션, 약정, 배송, 설치, 약관을 표준 단계로 구성한다.", "필수/선택 조건"),
            ("결제/개통", "결제, 본인인증, 개통 요청, 결과 반영을 연결한다.", "완료/보류/실패 상태"),
            ("완료 후속", "주문 상태, 배송, 이용 시작, 추천 후속 업무를 안내한다.", "후속 CTA 기준"),
        ],
        "policy_focus": [
            "주문 단계는 상품별 화면명이 아니라 모듈 ID와 상태 전이 기준으로 정의한다.",
            "인증 재사용과 재인증 조건은 업무 위험도와 세션 상태를 기준으로 둔다.",
            "주문 실패/보류/취소 가능 시점과 고객 고지 기준을 상태별로 관리한다.",
        ],
        "evidence": [
            ("p.1-p.2", "주문 프로세스 표준화와 셀프처리 완결성이 과제 목적이다."),
            ("p.2-p.4", "앱/웹 분산, 반복 입력, 인증 방식 차이가 핵심 문제로 정리된다."),
            ("p.4-p.8", "로그인 상태 정의부터 가입 가능 조건, 약관, 결제, 완료 후속까지 모듈형 프로세스가 제시된다."),
        ],
    },
    "tk-task-08": {
        "domain": "주문 사후관리",
        "tagline": "주문 완료 이후 상태 조회와 교환/반품/환불/해지를 하나의 사후관리 흐름으로 연결한다.",
        "interpretation": "원문은 주문내역 화면 보강보다, 주문 완료 후 가능한 행동과 처리 결과를 고객이 스스로 이해하고 끝내게 하는 lifecycle 설계다.",
        "problem": {
            "current": "주문 이후 교환, 반품, 환불, 해지 업무가 기능별로 흩어져 있고 일부는 셀프처리가 어렵다.",
            "pain": "고객은 현재 가능한 행동과 절차를 파악하지 못해 고객센터나 대리점으로 이관된다.",
            "root": "주문 이후 lifecycle 전반을 관통하는 상태/행동/결과 안내 설계가 부족하다.",
            "risk": "셀프 처리율이 낮고 사후 문의가 증가하며 주문 경험의 완결성이 떨어진다.",
        },
        "flow": ["주문내역", "상태 조회", "가능 액션 판단", "사후 처리", "결과 안내", "이력 관리"],
        "nodes": ["주문 상태", "배송/설치", "클레임", "환불/해지", "알림"],
        "pillars": [
            ("통합 상태 노출", "주문, 배송, 설치, 클레임, 상품 연동 상태를 하나의 타임라인으로 보여준다.", "상태 조회 성공률"),
            ("가능 행동 중심", "현재 상태에서 가능한 변경, 취소, 교환, 반품, 환불, 해지를 바로 안내한다.", "셀프 처리율"),
            ("처리 과정 투명화", "접수, 검토, 회수, 환불, 완료 등 진행 상태와 예상 소요 시간을 제공한다.", "문의 감소율"),
            ("사후 이력 관리", "처리 결과, 알림, 증빙, 후속 제한을 이력으로 남긴다.", "재문의율"),
        ],
        "workstreams": [
            ("주문내역 조회", "주문 목록과 상세를 고객 기준으로 제공한다.", "노출 기간, 상태 필터"),
            ("배송관리", "배송 상태, 설치/방문 일정, 주소/수령방식 변경을 제공한다.", "변경 가능 시점"),
            ("교환/반품", "사유, 가능 기간, 회수 방식, 비용, 승인 상태를 안내한다.", "불가 사유, 회수 조건"),
            ("환불/취소", "취소 가능 상태, 환불 금액, 환불 수단, 반영 시점을 제공한다.", "금액 산정, 고지 기준"),
            ("해지/연동 해제", "상품 연동, 인증, 해지 가능 여부와 후속 제한을 안내한다.", "해지 제한, 복구 가능성"),
        ],
        "policy_focus": [
            "주문 이후 상태 코드는 고객이 할 수 있는 다음 행동과 반드시 연결한다.",
            "교환/반품/환불/취소 가능 기간과 불가 사유는 정책 상세로 분리한다.",
            "환불 금액과 반영 시점은 결제수단, 사용 여부, 배송/회수 상태에 따라 산정한다.",
        ],
        "evidence": [
            ("p.1-p.2", "주문 완료 이후 후속 업무와 상태 조회의 일관성이 과제 목적이다."),
            ("p.2-p.3", "사후 업무 분산과 셀프처리 불가가 As-Is 문제로 제시된다."),
            ("p.3-p.4", "주문내역, 배송관리, 교환/반품, 해지/환불/취소 기능이 정리된다."),
        ],
    },
    "tk-task-09": {
        "domain": "통합 가입정보 · MY",
        "tagline": "회선/상품 단위 정보를 고객 중심 MY 허브와 셀프 관리 흐름으로 재구성한다.",
        "interpretation": "원문은 MY 메뉴 통합이 아니라, 가입 서비스와 계약 상태를 고객 목적 기준으로 요약하고 즉시 변경/정지/분실 등 행동으로 연결하는 구조를 말한다.",
        "problem": {
            "current": "T4S 정보가 서비스, 회선, 상품 단위로 흩어져 있고 통합 시 정보 과다 우려가 있다.",
            "pain": "다회선/가족/그룹 가입정보 관리가 어렵고, 채널 이동과 회선 전환으로 탐색 피로가 크다.",
            "root": "서비스/회선/상품 중심 정보 구조와 조회 중심 MY가 액션 연결을 약하게 만든다.",
            "risk": "셀프 처리율 저하, 상담/유통망 의존, 운영 중복과 고객 불만이 지속된다.",
        },
        "flow": ["MY 허브", "가입정보 통합", "상태 알림", "변경 · 정지", "분실 · 복구", "이력 확인"],
        "nodes": ["고객 기준", "가입/계약", "다회선/가족", "셀프 액션", "이력"],
        "pillars": [
            ("개인화 MY 허브", "고객 상태 기반 필요한 메뉴, 정보, 알림, 미완료 업무를 우선 노출한다.", "MY 진입 후 전환율"),
            ("통합 가입정보", "요금제, 결합, 약정, 할부, 부가서비스, 멤버십 상태를 요약한다.", "정보 탐색 시간"),
            ("상태 기반 액션", "변경, 정지, 분실, 복구 등 가능한 행동을 현재 상태에 맞게 제안한다.", "셀프 완료율"),
            ("다회선/가족 관리", "고객 기준 계약 관계와 회선별 상태를 함께 보여준다.", "회선 전환 감소율"),
        ],
        "workstreams": [
            ("MY 허브 진입", "고객 상태, 최근 처리, 미완료 업무, 알림을 우선 제시한다.", "우선 노출 기준"),
            ("가입정보 조회", "요금제, 약정, 결합, 부가서비스, 멤버십을 통합 조회한다.", "계약 관계 매핑"),
            ("상태 관리", "일시정지, 분실, 해제, 복구 가능 여부를 안내한다.", "상태 전이, 제한 조건"),
            ("변경 연결", "요금제/부가서비스/계약 변경 진입과 영향 확인을 연결한다.", "영향도 고지"),
            ("이력/알림", "변경 이력, 예약, 처리 결과, 다음 행동을 안내한다.", "이력 보관, 알림 조건"),
        ],
        "policy_focus": [
            "MY 정보는 회선/서비스 기준이 아니라 고객이 이해하는 계약 관계 기준으로 묶는다.",
            "상태별 허용 액션과 제한 사유를 명확히 두어야 한다.",
            "다회선/가족/대표 회선 권한에 따른 조회/변경 가능 범위를 분리한다.",
        ],
        "evidence": [
            ("p.1-p.2", "가입 서비스, 요금제, 계약 정보 조회와 상태 관리가 핵심 MY로 정의된다."),
            ("p.2-p.4", "정보 과다, 회선 단위 구조, 채널 이동, 상담 의존이 문제로 정리된다."),
            ("p.4-p.9", "MY 허브, 통합 가입정보, 상태 관리, 변경/정지/분실, 이력 기능이 구체화된다."),
        ],
    },
    "tk-task-10": {
        "domain": "청구 · 납부",
        "tagline": "요금을 고객 언어로 해석하고 예측하며 필요한 조치를 즉시 완료하게 한다.",
        "interpretation": "원문은 청구/납부 기능 모음이 아니라, 금액 신뢰와 셀프 해결을 만드는 상태 기반 요금 관리 경험이다.",
        "problem": {
            "current": "요금 조회, 납부, 자동납부, 납부수단 변경, 미납 해결 기능이 분산되어 있다.",
            "pain": "고객은 왜 이 금액인지, 다음 달 얼마인지, 변경 영향과 납부 반영 상태를 이해하기 어렵다.",
            "root": "기능/업무 단위 IA, 청구 항목 중심 정보 설계, 납부/변경/예외 해결 간 연결 부족이 원인이다.",
            "risk": "과금 불신, VOC 증가, 납부 전환율 저하, 미납 장기화와 긴급 문의가 지속된다.",
        },
        "flow": ["요금 허브", "금액 해석", "다음 달 예측", "납부 실행", "예외 해결", "신뢰 회복"],
        "nodes": ["청구 상태", "금액 사유", "예상 요금", "납부 수단", "미납 복구"],
        "pillars": [
            ("고객 언어 청구서", "청구 항목을 고객이 이해하는 사유와 변화 기준으로 재구성한다.", "요금 문의율"),
            ("예상 요금", "변경, 사용량, 할인 만료가 다음 달 요금에 미치는 영향을 예측한다.", "예상 조회 이용률"),
            ("셀프 납부", "현재 상태에 맞는 납부, 자동납부, 수단 변경, 미납 해결을 바로 연결한다.", "납부 전환율"),
            ("예외 대응", "휴일/야간, 자동납부 실패, 정지 직전, 가족/위임 납부 상황을 처리한다.", "미납 복구율"),
        ],
        "workstreams": [
            ("요금/납부 허브", "이번 달 요금, 미납, 자동납부, 납부 예정일을 통합 노출한다.", "핵심 상태값"),
            ("금액 해석", "청구 변동 사유, 할인 반영, 사용량 영향을 고객 언어로 설명한다.", "사유 우선순위"),
            ("예상/영향", "다음 달 예상 금액과 변경 시 영향을 시뮬레이션한다.", "예상 기준일"),
            ("납부 실행", "즉시 납부, 자동납부 설정/변경, 납부수단 변경을 제공한다.", "처리 가능 시간"),
            ("미납/실패 해결", "실패 원인, 재시도, 대체 수단, 정지 위험, 복구 상태를 안내한다.", "복구 경로"),
        ],
        "policy_focus": [
            "청구 상태, 납부 상태, 반영 예정 상태를 고객 노출 상태로 분리한다.",
            "예상 요금은 산정 기준, 포함/제외 항목, 변동 가능성을 반드시 고지한다.",
            "가족/다회선/위임 납부의 권한과 인증 기준을 별도로 둔다.",
        ],
        "evidence": [
            ("p.1-p.2", "청구/납부 정보를 고객 관점으로 해석하고 예측하는 것이 과제 목적이다."),
            ("p.2-p.4", "금액 이해, 변경 영향, 미납/실패 해결, 가족/위임 시나리오가 문제로 제시된다."),
            ("p.4-p.7", "요금 허브, 상태 인지, 예상 요금, 납부 실행, 예외 해결 기능이 정리된다."),
        ],
    },
    "tk-task-11": {
        "domain": "고객지원 · CS",
        "tagline": "FAQ/공지/상담/매장 기능을 문제 해결 중심의 통합 지원 여정으로 묶는다.",
        "interpretation": "원문은 고객센터 메뉴 정리가 아니라, 고객이 문제를 설명하면 검색, 안내, 실행, 상담/매장 전환까지 맥락이 이어지는 해결 체계다.",
        "problem": {
            "current": "상담, FAQ, 이용안내, 공지, 매장찾기 기능이 분산되고 해결 흐름이 끊긴다.",
            "pain": "고객은 어디서 해결해야 하는지 판단해야 하고, FAQ 이후 실행이나 상담 전환이 자연스럽지 않다.",
            "root": "문제 유형 기반 IA와 기능 간 오케스트레이션, AI 역할, 온/오프라인 이력 연계가 부족하다.",
            "risk": "단순/중복 문의, 상담·매장 의존, AI 신뢰 저하, 오연결과 반복 설명이 지속된다.",
        },
        "flow": ["문제 인지", "AI/검색 해석", "안내 · FAQ", "셀프 실행", "상담 · 매장 전환", "이력 연계"],
        "nodes": ["지원 허브", "문제 유형", "AI 해석", "셀프 처리", "상담 맥락"],
        "pillars": [
            ("통합 지원 허브", "상담, FAQ, 공지, 매장, 예약, VoC를 문제 유형 기준 진입점으로 묶는다.", "허브 진입률"),
            ("검색-안내 전환", "통합 검색과 AI가 문제를 해석하고 FAQ/공지/셀프처리/상담을 추천한다.", "검색 후 완료율"),
            ("셀프 해결", "안내에서 끝나지 않고 실행 가능한 업무와 다음 행동으로 연결한다.", "셀프 완료율"),
            ("맥락 유지 전환", "상담/매장 전환 시 이전 검색, 처리 상태, 증상을 전달한다.", "반복 설명 감소율"),
        ],
        "workstreams": [
            ("고객지원 허브", "문의, FAQ, 공지, 매장, 예약, 상담이력을 통합 제공한다.", "문제 유형 분류"),
            ("AI 문제 해석", "자연어 증상과 목적을 업무 카테고리, 긴급도, 경로로 해석한다.", "AI 제안 신뢰도"),
            ("검색/안내", "FAQ, 공지, 이용안내, 실행 기능, 상담 연결을 통합 결과로 제공한다.", "검색 실패 폴백"),
            ("셀프 처리", "가능한 업무는 인증/권한 확인 후 바로 실행으로 연결한다.", "실패/제한 안내"),
            ("상담/매장 전환", "전환 메모, 준비사항, 예약, 처리 이력을 전달한다.", "맥락 전달 기준"),
        ],
        "policy_focus": [
            "고객지원은 기능명이 아니라 문제 유형과 긴급도 기준으로 진입 구조를 정의한다.",
            "셀프 처리 가능/불가, 상담 전환 필요, 매장 방문 필요 조건을 정책으로 분리한다.",
            "상담/매장 전환 시 전달 가능한 고객 정보와 민감정보 제외 기준을 둔다.",
        ],
        "evidence": [
            ("p.1-p.2", "분산된 고객지원 기능 통합과 검색-안내-실행-상담 연결이 목적이다."),
            ("p.2-p.4", "문제 유형 기반 IA 부재와 온/오프라인 맥락 단절이 원인으로 제시된다."),
            ("p.4-p.7", "고객지원 허브, AI 문제 해석, 검색, FAQ/공지, 셀프 처리, 상담/매장 전환 기능이 정리된다."),
        ],
    },
    "tk-task-12": {
        "domain": "회원 · 인증 · 알림 · 약관",
        "tagline": "계정, 인증, 회원정보, 약관, 알림, 설정을 통합 회원 경험으로 묶는다.",
        "interpretation": "원문은 설정 메뉴 통합이 아니라, 통합채널의 기반이 되는 계정/인증/수신/약관 체계를 고객이 직접 관리하게 하는 과제다.",
        "problem": {
            "current": "T월드, 멤버십, 티다, 우주별 계정, 인증, 알림, 약관, 설정 기능이 분산 운영된다.",
            "pain": "로그인/인증 방식이 다르고 약관/알림/회원정보 관리 경로가 흩어져 고객이 일관되게 관리하기 어렵다.",
            "root": "채널별 계정/인증 체계, 회원/약관/알림 데이터, 설정 정책이 통합되어 있지 않다.",
            "risk": "계정 관리 피로, 인증 문의 증가, 개인화 확장 한계, 운영/개발 중복이 지속된다.",
        },
        "flow": ["통합 가입", "로그인 · 세션", "공통 인증", "회원정보 관리", "약관 · 알림", "설정 제어"],
        "nodes": ["CI 계정", "SSO/PASS", "인증 모듈", "약관 이력", "알림 설정"],
        "pillars": [
            ("CI 기반 통합 계정", "가입, 로그인, 탈퇴, 정보 변경을 하나의 계정 체계로 통합한다.", "통합 회원 전환율"),
            ("로그인/인증 최소화", "SSO, PASS, 생체, 소셜 등 수단을 통합하고 세션 내 반복 인증을 줄인다.", "재인증 발생률"),
            ("약관 통합 관리", "약관 조회, 동의, 철회, 재동의, 이력을 한 화면에서 관리한다.", "약관 완료율"),
            ("알림/설정 제어", "채널/유형별 수신 설정과 후속 행동 연결을 고객이 직접 조정한다.", "수신 설정 변경 성공률"),
        ],
        "workstreams": [
            ("통합 계정", "단일 CI 기반 가입, 로그인, 탈퇴, 계정 연동을 관리한다.", "기존 회원 전환"),
            ("로그인/세션", "SSO/PASS/소셜/생체 인증과 세션 유지를 제공한다.", "세션 유지 기준"),
            ("공통 인증", "가입, 변경, 결제 등 업무 위험도에 따라 인증을 차등 적용한다.", "인증 재사용 조건"),
            ("회원정보 CRUD", "프로필, 배송지, 연락처, 결제수단 등 회원정보를 통합 관리한다.", "변경 이력"),
            ("약관/알림/설정", "동의 이력, 수신 권한, 접근성/언어/개인화 설정을 관리한다.", "철회/재동의, 권한"),
        ],
        "policy_focus": [
            "계정 상태, 인증 완료 상태, 약관 동의 상태, 알림 수신 상태를 별도 상태로 관리한다.",
            "업무별 인증 수준과 세션 내 인증 재사용 가능 조건을 명확히 둔다.",
            "약관 철회/재동의와 알림 수신 변경은 이력 저장과 고객 고지 기준이 필요하다.",
        ],
        "evidence": [
            ("p.1-p.2", "계정, 인증, 알림, 약관, 설정을 통합 제공하는 것이 과제 목적이다."),
            ("p.2-p.3", "채널별 분산 운영, 인증 방식 차이, 약관/알림 관리 어려움이 문제로 정리된다."),
            ("p.3-p.5", "통합 계정, 로그인, 인증, 회원정보, 알림, 약관, 설정, 비로그인 가치 제공 기능이 제시된다."),
        ],
    },
}


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def extract_page_texts(pdf_path: Path, pages: int) -> list[str]:
    page_texts: list[str] = []
    for page in range(1, pages + 1):
        result = run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf_path), "-"])
        text = re.sub(r"\s+", " ", result.stdout).strip()
        page_texts.append(text)
    return page_texts


def render_cover(pdf_path: Path, doc_id: str) -> str:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    out_base = ASSET_DIR / f"{doc_id}-cover"
    out_file = out_base.with_suffix(".png")
    if not out_file.exists():
        run(["pdftoppm", "-f", "1", "-l", "1", "-png", "-singlefile", "-scale-to", "620", str(pdf_path), str(out_base)])
    return f"assets/{doc_id}-cover.png"


def render_svg(nodes: list[str]) -> str:
    safe_nodes = [escape(node) for node in nodes[:5]]
    while len(safe_nodes) < 5:
        safe_nodes.append("")
    x_positions = [80, 240, 400, 560, 720]
    node_markup = []
    arrow_markup = []
    colors = ["#eef5ff", "#ecfdf5", "#fff7ed", "#fef2f2", "#f8fafc"]
    strokes = ["#3182f6", "#10b981", "#f59e0b", "#ef4444", "#64748b"]
    for index, (x, label) in enumerate(zip(x_positions, safe_nodes)):
        node_markup.append(
            f'<g><rect x="{x-62}" y="40" width="124" height="74" rx="18" fill="{colors[index]}" '
            f'stroke="{strokes[index]}" stroke-width="1.5"/>'
            f'<circle cx="{x}" cy="36" r="14" fill="{strokes[index]}"/>'
            f'<text x="{x}" y="41" text-anchor="middle" font-size="12" font-weight="900" fill="#fff">{index+1}</text>'
            f'<text x="{x}" y="79" text-anchor="middle" font-size="13" font-weight="800" fill="#172033">{label}</text></g>'
        )
        if index < len(x_positions) - 1:
            arrow_markup.append(
                f'<path d="M{x+68} 77 H{x_positions[index+1]-76}" stroke="#94a3b8" stroke-width="2.2" '
                f'stroke-linecap="round" marker-end="url(#arrow)"/>'
            )
    return (
        '<svg class="map-svg" viewBox="0 0 800 150" role="img" aria-label="과제 전환 구조도">'
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">'
        '<path d="M0,0 L8,4 L0,8 Z" fill="#94a3b8"/></marker></defs>'
        + "".join(arrow_markup)
        + "".join(node_markup)
        + "</svg>"
    )


def render_list(items: list[str]) -> str:
    return "".join(f"<li>{escape(item)}</li>" for item in items)


SECTION_DEFINITIONS = [
    ("과제 목적", ["과제 목적"], ["문제 정의 요약"]),
    ("문제 정의 요약", ["문제 정의 요약"], ["과제 정의"]),
    ("과제 정의", ["과제 정의"], ["As Is 문제점", "As-is 문제점", "As-Is 문제점", "지향점 및 기대 효과"]),
    ("As-Is 문제점", ["As Is 문제점", "As-is 문제점", "As-Is 문제점"], ["지향점 및 기대 효과"]),
    ("지향점 및 기대 효과", ["지향점 및 기대 효과"], ["정량적 효과", "주요 프로세스 및 기능"]),
    ("주요 프로세스 및 기능", ["주요 프로세스 및 기능"], ["타 과제 영향도", "과제 정의서 상세", "상세 PPT", "끌어다 놓기", "레이블 없음"]),
    ("타 과제 영향도", ["타 과제 영향도"], ["관계 유형 분류", "목차 Level", "상세 PPT", "끌어다 놓기", "레이블 없음"]),
]


def normalize_source_text(text: str) -> str:
    cleaned = re.sub(r"https?://\S+", "", text)
    cleaned = re.sub(r"[-]", " ", cleaned)
    cleaned = re.sub(r"\b26\.\s*5\.\s*7\.\s*오후\s*\d+:\d+.*?Confluence", " ", cleaned)
    cleaned = re.sub(r"\b\d+/\d+\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.replace(" .", ".").replace(" ,", ",").replace(" / ", "/")
    cleaned = re.sub(r"\s+([.)])", r"\1", cleaned)
    return cleaned.strip()


def find_any_marker(text: str, markers: list[str], start: int = 0) -> tuple[int, str]:
    matches = [(text.find(marker, start), marker) for marker in markers]
    matches = [(index, marker) for index, marker in matches if index >= 0]
    if not matches:
        return -1, ""
    return min(matches, key=lambda value: value[0])


def extract_between_markers(text: str, starts: list[str], ends: list[str], start_at: int = 0) -> tuple[str, int]:
    start, marker = find_any_marker(text, starts, start_at)
    if start < 0:
        return "", start_at
    content_start = start + len(marker)
    end, _ = find_any_marker(text, ends, content_start) if ends else (-1, "")
    content_end = end if end >= 0 else len(text)
    content = normalize_source_text(text[content_start:content_end])
    return content, content_end


def original_detail_sections(page_texts: list[str]) -> list[tuple[str, str]]:
    source_text = normalize_source_text(" ".join(page_texts))
    sections: list[tuple[str, str]] = []
    cursor = 0
    for label, starts, ends in SECTION_DEFINITIONS:
        content, next_cursor = extract_between_markers(source_text, starts, ends, cursor)
        if not content and label in {"과제 정의", "As-Is 문제점"}:
            content, next_cursor = extract_between_markers(source_text, starts, ends, 0)
        if content:
            sections.append((label, content))
            cursor = max(cursor, next_cursor)
    return sections


def split_original_paragraphs(text: str) -> list[str]:
    marked = text
    for marker in [
        "현 상태",
        "Pain Point",
        "Root Cause",
        "미해결 시 Risk",
        "포함 모듈",
        "번호",
        "핵심 지향점",
        "To Do",
        "기대 효과",
        "측정 지표",
        "프로세스 명",
        "주요 기능",
    ]:
        marked = marked.replace(marker, f"@@{marker}")
    marked = re.sub(r"\s(?=\d{1,2}\s+[가-힣A-Za-z])", "@@", marked)
    chunks = [chunk.strip(" @") for chunk in marked.split("@@") if len(chunk.strip(" @")) > 0]
    paragraphs: list[str] = []
    for chunk in chunks:
        if len(chunk) <= 620:
            paragraphs.append(chunk)
            continue
        sentences = re.split(r"(?<=[.])\s+|(?<=다)\s+", chunk)
        buffer = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(buffer) + len(sentence) > 620 and buffer:
                paragraphs.append(buffer.strip())
                buffer = sentence
            else:
                buffer = f"{buffer} {sentence}".strip()
        if buffer:
            paragraphs.append(buffer.strip())
    return paragraphs


def render_original_detail_sections(page_texts: list[str]) -> str:
    sections = original_detail_sections(page_texts)
    if not sections:
        return '<p class="original-empty">원문 상세 섹션을 추출하지 못했습니다.</p>'
    details: list[str] = []
    for index, (label, content) in enumerate(sections, 1):
        paragraphs = "".join(f"<p>{escape(paragraph)}</p>" for paragraph in split_original_paragraphs(content))
        details.append(
            f'<details class="original-detail" {"open" if index <= 3 else ""}>'
            f"<summary><span>{index:02d}</span><strong>{escape(label)}</strong></summary>"
            f'<div class="original-copy">{paragraphs}</div>'
            "</details>"
        )
    return "".join(details)


def render_doc(item: dict[str, object], source: dict[str, object], page_texts: list[str], cover_url: str) -> str:
    title = str(source["title"])
    pages = int(source["pages"])
    source_name = Path(str(source["source"])).name
    total_chars = sum(len(text) for text in page_texts)
    problem = item["problem"]
    assert isinstance(problem, dict)
    keyword_summary = [
        ("원문 페이지", f"{pages}p"),
        ("추출 본문", f"{total_chars:,}자"),
        ("재작성 관점", "정책서 작성 참고"),
        ("산출 유형", "분석 재작성본"),
    ]
    keyword_markup = "".join(f"<div><b>{escape(k)}</b><span>{escape(v)}</span></div>" for k, v in keyword_summary)
    diagnosis_markup = "".join(
        f'<article class="diagnosis-card {escape(key)}"><span>{escape(label)}</span><p>{escape(problem[key])}</p></article>'
        for key, label in [("current", "현 상태"), ("pain", "고객 Pain"), ("root", "Root Cause"), ("risk", "미해결 Risk")]
    )
    flow_markup = "".join(f"<li><span>{index:02d}</span><strong>{escape(step)}</strong></li>" for index, step in enumerate(item["flow"], 1))
    pillar_markup = "".join(
        f"<article><small>{escape(kpi)}</small><strong>{escape(title_)}</strong><p>{escape(body)}</p></article>"
        for title_, body, kpi in item["pillars"]
    )
    workstream_rows = "".join(
        "<tr>"
        f"<th>{escape(name)}</th><td>{escape(focus)}</td><td>{escape(policy)}</td>"
        "</tr>"
        for name, focus, policy in item["workstreams"]
    )
    policy_rows = "".join(
        f"<tr><td>{index}</td><td>{escape(text)}</td></tr>"
        for index, text in enumerate(item["policy_focus"], 1)
    )
    evidence_markup = "".join(
        f"<li><strong>{escape(page)}</strong><span>{escape(note)}</span></li>"
        for page, note in item["evidence"]
    )
    original_detail_markup = render_original_detail_sections(page_texts)
    page_notes = "".join(
        f"<article><strong>Page {index}</strong><p>{escape(summarize_page(text))}</p></article>"
        for index, text in enumerate(page_texts, 1)
        if text
    )
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{escape(title)} · 분석 재작성본</title>
  <style>
    :root {{
      --ink:#172033; --soft:#667085; --muted:#8a94a6; --line:#dde6f2; --panel:#ffffff;
      --blue:#3182f6; --green:#10b981; --orange:#f59e0b; --red:#ef4444; --bg:#f5f8fc;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; line-height:1.62; }}
    .page {{ width:min(1180px, calc(100% - 48px)); margin:0 auto; padding:44px 0 72px; }}
    .hero {{ display:grid; grid-template-columns:minmax(0,1.1fr) 360px; gap:24px; align-items:stretch; }}
    .hero-main, .source-card, section {{ border:1px solid rgba(209,218,230,.88); border-radius:28px; background:rgba(255,255,255,.94); box-shadow:0 18px 46px rgba(31,42,68,.08); }}
    .hero-main {{ padding:34px; overflow:hidden; position:relative; }}
    .eyebrow {{ color:var(--blue); font-size:12px; font-weight:950; letter-spacing:.18em; text-transform:uppercase; }}
    h1 {{ margin:12px 0 14px; font-size:34px; line-height:1.16; letter-spacing:0; }}
    .tagline {{ max-width:760px; margin:0; color:#405064; font-size:17px; font-weight:780; }}
    .interpretation {{ margin-top:24px; border-left:4px solid var(--blue); border-radius:16px; background:#eef5ff; padding:16px 18px; color:#24466f; font-weight:780; }}
    .keyword-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin-top:24px; }}
    .keyword-grid div {{ border:1px solid #e5edf7; border-radius:16px; background:#fff; padding:12px; }}
    .keyword-grid b {{ display:block; color:var(--muted); font-size:11px; font-weight:900; }}
    .keyword-grid span {{ display:block; margin-top:3px; font-size:14px; font-weight:950; }}
    .source-card {{ display:grid; grid-template-rows:auto 1fr auto; gap:14px; padding:18px; }}
    .source-card img {{ width:100%; max-height:360px; object-fit:contain; border:1px solid #e7edf5; border-radius:18px; background:#fff; }}
    .source-card strong {{ font-size:15px; }}
    .source-card p {{ margin:0; color:var(--soft); font-size:12px; font-weight:760; word-break:break-word; }}
    section {{ margin-top:24px; padding:26px; }}
    h2 {{ margin:0 0 18px; font-size:22px; line-height:1.24; }}
    .diagnosis-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; }}
    .diagnosis-card {{ min-height:168px; border:1px solid #e5edf7; border-radius:20px; padding:18px; background:#fff; }}
    .diagnosis-card span {{ display:inline-flex; border-radius:999px; padding:6px 10px; font-size:11px; font-weight:950; }}
    .diagnosis-card p {{ margin:13px 0 0; color:#36455a; font-weight:760; }}
    .diagnosis-card.current span {{ background:#eef5ff; color:var(--blue); }}
    .diagnosis-card.pain span {{ background:#fff7ed; color:#b45309; }}
    .diagnosis-card.root span {{ background:#ecfdf5; color:#047857; }}
    .diagnosis-card.risk span {{ background:#fef2f2; color:#b42318; }}
    .map-wrap {{ overflow:auto; border:1px solid #e5edf7; border-radius:24px; background:linear-gradient(180deg,#fff,#f8fbff); padding:18px; }}
    .map-svg {{ display:block; min-width:800px; width:100%; height:auto; }}
    .flow-list {{ display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:10px; list-style:none; margin:18px 0 0; padding:0; }}
    .flow-list li {{ border:1px solid #dfebf8; border-radius:18px; background:#fff; padding:14px 12px; }}
    .flow-list span {{ display:block; color:var(--blue); font-size:11px; font-weight:950; }}
    .flow-list strong {{ display:block; margin-top:6px; font-size:14px; line-height:1.35; }}
    .pillars {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; }}
    .pillars article {{ border:1px solid #e5edf7; border-radius:20px; background:#fff; padding:18px; }}
    .pillars small {{ display:inline-flex; border-radius:999px; background:#f4f7fb; color:var(--soft); padding:5px 9px; font-size:10px; font-weight:900; }}
    .pillars strong {{ display:block; margin-top:12px; font-size:16px; }}
    .pillars p {{ margin:8px 0 0; color:#405064; font-weight:730; }}
    .original-detail-list {{ display:grid; gap:12px; }}
    .original-detail {{ border:1px solid #e1eaf5; border-radius:20px; background:#fff; overflow:hidden; }}
    .original-detail summary {{ display:flex; align-items:center; gap:10px; min-height:52px; cursor:pointer; list-style:none; padding:14px 18px; }}
    .original-detail summary::-webkit-details-marker {{ display:none; }}
    .original-detail summary span {{ display:inline-flex; width:34px; height:28px; align-items:center; justify-content:center; border-radius:999px; background:#eef5ff; color:var(--blue); font-size:11px; font-weight:950; }}
    .original-detail summary strong {{ font-size:15px; font-weight:950; }}
    .original-detail[open] summary {{ border-bottom:1px solid #edf2f8; background:linear-gradient(180deg,#fff,#f8fbff); }}
    .original-copy {{ display:grid; gap:9px; padding:16px 18px 18px; }}
    .original-copy p {{ margin:0; border-left:3px solid #dbeafe; border-radius:12px; background:#f8fbff; color:#334155; font-size:13px; font-weight:730; line-height:1.65; padding:10px 12px; }}
    .original-empty {{ margin:0; color:var(--muted); font-weight:800; }}
    table {{ width:100%; border-collapse:separate; border-spacing:0; overflow:hidden; border:1px solid #dce7f3; border-radius:18px; background:#fff; }}
    th, td {{ border-bottom:1px solid #e7edf5; padding:14px 16px; text-align:left; vertical-align:top; }}
    th {{ width:22%; background:#f6f9fd; font-size:13px; font-weight:950; }}
    td {{ color:#3a495d; font-size:14px; font-weight:730; }}
    tr:last-child th, tr:last-child td {{ border-bottom:0; }}
    .policy-table td:first-child {{ width:56px; color:var(--blue); font-weight:950; text-align:center; }}
    .evidence-list {{ display:grid; gap:10px; list-style:none; margin:0; padding:0; }}
    .evidence-list li {{ display:grid; grid-template-columns:86px minmax(0,1fr); gap:12px; border:1px solid #e5edf7; border-radius:16px; background:#fff; padding:13px 14px; }}
    .evidence-list strong {{ color:var(--blue); font-weight:950; }}
    .evidence-list span {{ color:#405064; font-weight:740; }}
    .page-notes {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }}
    .page-notes article {{ border:1px solid #e5edf7; border-radius:18px; background:#fff; padding:14px; }}
    .page-notes strong {{ color:#0f172a; font-size:13px; }}
    .page-notes p {{ margin:7px 0 0; color:var(--soft); font-size:12px; font-weight:730; }}
    footer {{ margin-top:26px; color:var(--muted); font-size:12px; font-weight:750; text-align:center; }}
    @media (max-width: 900px) {{
      .page {{ width:min(100% - 24px, 1180px); padding-top:24px; }}
      .hero {{ grid-template-columns:1fr; }}
      .keyword-grid, .diagnosis-grid, .pillars, .page-notes {{ grid-template-columns:1fr; }}
      .flow-list {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
      h1 {{ font-size:28px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <div class="hero">
      <article class="hero-main">
        <div class="eyebrow">Task Definition · Rewritten Reference</div>
        <h1>{escape(title)}</h1>
        <p class="tagline">{escape(item["tagline"])}</p>
        <div class="interpretation">{escape(item["interpretation"])}</div>
        <div class="keyword-grid">{keyword_markup}</div>
      </article>
      <aside class="source-card">
        <strong>원문 PDF 스냅샷</strong>
        <img src="{escape(cover_url)}" alt="{escape(title)} 원문 첫 페이지"/>
        <p>출처: {escape(source_name)}</p>
      </aside>
    </div>

    <section>
      <h2>1. 원문 진단을 정책서 관점으로 재구성</h2>
      <div class="diagnosis-grid">{diagnosis_markup}</div>
    </section>

    <section>
      <h2>2. 원문 주요 내용 상세</h2>
      <div class="original-detail-list">{original_detail_markup}</div>
    </section>

    <section>
      <h2>3. To-Be 전환 구조도</h2>
      <div class="map-wrap">{render_svg(item["nodes"])}</div>
      <ol class="flow-list">{flow_markup}</ol>
    </section>

    <section>
      <h2>4. 핵심 지향점</h2>
      <div class="pillars">{pillar_markup}</div>
    </section>

    <section>
      <h2>5. 업무 흐름과 정책 판단축</h2>
      <table>
        <thead><tr><th>업무 축</th><th>재작성한 기능 의미</th><th>정책서에서 남겨야 할 판단 기준</th></tr></thead>
        <tbody>{workstream_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>6. 정책서 작성 포인트</h2>
      <table class="policy-table">
        <tbody>{policy_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>7. 원문 근거와 읽은 범위</h2>
      <ul class="evidence-list">{evidence_markup}</ul>
    </section>

    <section>
      <h2>8. 페이지별 핵심 메모</h2>
      <div class="page-notes">{page_notes}</div>
    </section>

    <footer>PDF 원문을 단순 HTML 변환하지 않고, 정책서 작성 참고 화면으로 재구성한 버전입니다.</footer>
  </main>
</body>
</html>
"""


def summarize_page(text: str) -> str:
    cleaned = re.sub(r"https?://\S+", "", text)
    cleaned = re.sub(r"[-]", "", cleaned)
    sentences = re.split(r"(?<=[.。])\s+|(?<=다)\s+", cleaned)
    sentences = [s.strip(" .") for s in sentences if len(s.strip()) > 18]
    if not sentences:
        return cleaned[:180]
    summary = " / ".join(sentences[:2])
    return summary[:220]


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for source in manifest:
        doc_id = source["id"]
        item = DOCS[doc_id]
        pdf_path = ROOT / source["source"]
        pages = int(source["pages"])
        page_texts = extract_page_texts(pdf_path, pages)
        cover_url = render_cover(pdf_path, doc_id)
        html_text = render_doc(item, source, page_texts, cover_url)
        (OUT_DIR / f"{doc_id}.html").write_text(html_text, encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
