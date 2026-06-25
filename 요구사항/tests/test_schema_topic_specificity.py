import json
import re
import unittest
from types import SimpleNamespace

from src.chapter_agents import default_usecase_for_actor, is_step_like_usecase_name, process_templates_for_usecase
from src.schema import build_policy_spec
from src.validator import validate_policy_specificity


class FakeRequirement:
    def __init__(self, detail_name, detail_description="", *, depth4="테스트 정책서"):
        self.source_number = "1"
        self.depth3 = "테스트"
        self.depth4 = depth4
        self.requirement_id = detail_name
        self.parent_name = ""
        self.parent_description = ""
        self.detail_name = detail_name
        self.detail_description = detail_description
        self.requirement_type = ""
        self.priority = ""
        self.required = "Y"
        self.source = ""
        self.owner_team = ""
        self.owner = ""
        self.edit_status = ""
        self.review_status = ""


def build_ctx(topic, requirements):
    return SimpleNamespace(
        topic=topic,
        topic_slug=topic,
        business_code="TST",
        template_type="simple",
        status="작성중",
        version="v0.1",
        author="test",
        today="2026-05-07",
        requirements=requirements,
        references=[],
        brief="",
    )


class SchemaTopicSpecificityTest(unittest.TestCase):
    def test_usecase_skeleton_uses_detail_requirement_themes(self):
        requirements = [
            FakeRequirement("카테고리 전시(탭/필터)", "고객이 상품군별 카테고리와 필터를 이용해 목록을 탐색한다."),
            FakeRequirement("전시 목록 카드 표준 정의", "목록 카드에는 고객 판단에 필요한 핵심 정보를 표준화해 노출한다."),
            FakeRequirement("전시 내 정렬/필터", "고객은 목록 안에서 정렬과 필터 조건을 적용한다."),
            FakeRequirement("즐겨찾기/찜", "고객은 관심 상품을 저장하고 다시 확인한다."),
            FakeRequirement("빈 화면/에러 폴백", "결과 없음 또는 오류 상황에서는 대체 경로를 안내한다."),
        ]

        spec = build_policy_spec(build_ctx("상품목록", requirements))
        names = [row["name"] for row in spec["usecases"] if row.get("process_target") == "Y"]
        serialized = json.dumps(spec, ensure_ascii=False)

        self.assertFalse(any("상품목록 신청·처리" in name for name in names))
        self.assertTrue(any("상품목록 정보 탐색" in name for name in names))
        self.assertFalse(any(is_step_like_usecase_name(name) for name in names))
        self.assertTrue("필터" in serialized or "정렬" in serialized)
        self.assertTrue("빈 화면" in serialized or "폴백" in serialized)

    def test_member_signup_does_not_pick_account_unlink_as_primary_entry(self):
        requirements = [
            FakeRequirement("멤버십 회원 가입 대상 조건 검증", "고객의 가입 가능 대상과 제한 조건을 확인한다."),
            FakeRequirement("부정가입/도용 방지(리스크 룰)", "부정 가입과 도용 의심 조건을 제한한다."),
            FakeRequirement("인앱브라우저 기반 인증/로그인 공통 플로우", "고객 인증과 로그인 세션을 공통 처리한다."),
            FakeRequirement("계정 연결/해제(외부 연동)", "외부 계정 연결과 해제 기준을 관리한다."),
            FakeRequirement("회원탈퇴 단계형 처리", "탈퇴 안내, 확인, 상태 변경을 단계형으로 처리한다."),
        ]

        spec = build_policy_spec(build_ctx("회원 가입/탈퇴", requirements))
        names = [row["name"] for row in spec["usecases"] if row.get("process_target") == "Y"]

        self.assertIn("회원 가입·탈퇴 대상 판단", names[0])
        self.assertTrue(any("신청 실행" in name for name in names))
        self.assertTrue(any("변경·취소 관리" in name for name in names))
        self.assertFalse(any("회원 가입·탈퇴 혜택 이용" in name for name in names))
        self.assertFalse(any(is_step_like_usecase_name(name) for name in names))

    def test_requirement_policy_content_avoids_authoring_prefix_noise(self):
        requirements = [
            FakeRequirement("회원정보 수정 가능 항목/예외 안내", "고객이 회원정보 변경 가능 항목과 제한 조건을 확인하고 수정한다."),
            FakeRequirement("이메일 등록/변경/삭제 및 인증", "이메일 변경 시 인증과 이력 저장 기준을 적용한다."),
            FakeRequirement("프로필 변경 중단 상태 저장/복원", "변경 중단 후 재진입 시 이전 입력 상태를 복원한다."),
            FakeRequirement("통합주소록 수정 영향범위 안내", "주소록 변경이 가족·그룹 관계와 알림 수신에 미치는 영향을 안내한다."),
        ]

        spec = build_policy_spec(build_ctx("회원정보 조회/변경", requirements))
        contents = "\n".join(detail["content"] for detail in spec["policy_details"])

        self.assertNotRegex(
            contents,
            re.compile(
                r"^(접수 허용 기준|제한 안내 기준|이력 저장 기준|재검증 기준|상담 전환 기준|결과 회신 기준|운영 확인 기준|고객 고지 기준):",
                re.MULTILINE,
            ),
        )
        self.assertNotRegex(contents, r"기준:\s*[^.]{2,100}기준은")

    def test_member_info_change_topic_prefers_change_execution_over_signup_execution(self):
        requirements = [
            FakeRequirement("그룹 결합 할인 가입 지원", "그룹 구성원을 등록하고 인원 수 증가에 따른 할인 조건을 안내한다.", depth4="회원정보 조회/변경"),
            FakeRequirement("프로필 정보 수정(편집 모드)", "고객이 수정 가능한 항목을 편집하고 저장한다.", depth4="회원정보 조회/변경"),
            FakeRequirement("이메일 등록/변경/삭제 및 인증", "이메일 변경 시 인증과 이력 저장 기준을 적용한다.", depth4="회원정보 조회/변경"),
        ]

        spec = build_policy_spec(build_ctx("회원정보 조회/변경", requirements))
        names = [row["name"] for row in spec["usecases"] if row.get("process_target") == "Y"]

        self.assertIn("회원정보 통합 조회·이해", names)
        self.assertIn("회원정보 변경·검증 처리", names)
        self.assertIn("회원정보 정정·복구 관리", names)
        self.assertFalse(any("회원정보 조회·변경 신청 실행" in name for name in names))
        self.assertFalse(any("가입·신청" in name or "약관·동의" in name for name in names))
        self.assertFalse(any(is_step_like_usecase_name(name) for name in names))

    def test_member_info_topic_keeps_requirement_axes_in_member_context(self):
        requirements = [
            FakeRequirement("통합주소록 목록/주소용도 조회", "고객은 통합주소록에서 등록된 주소 목록과 활용 용도를 조회한다.", depth4="회원정보 조회/변경"),
            FakeRequirement("프로필 정보 수정(편집 모드)", "고객이 연락처, 이메일, 주소를 편집하고 저장한다.", depth4="회원정보 조회/변경"),
            FakeRequirement("민감 행위 재인증 정책", "회원정보 변경 시 재인증 요구 기준과 실패 시 대체 경로를 정의한다.", depth4="회원정보 조회/변경"),
            FakeRequirement("법인 대표자가 위임대리인을 등록·변경·삭제", "법인 대표자가 위임대리인을 등록하고 권한 범위를 확인한다.", depth4="회원정보 조회/변경"),
        ]

        spec = build_policy_spec(build_ctx("회원정보 조회/변경", requirements))
        serialized = json.dumps(spec, ensure_ascii=False)
        process_names = [row["name"] for row in spec["processes"]]

        self.assertIn("조회 범위·정합화", serialized)
        self.assertIn("회원정보 변경", serialized)
        self.assertIn("검증·재인증", serialized)
        self.assertIn("권한·관계 정보 관리", serialized)
        self.assertFalse(any("가입·신청" in name or "약관·동의" in name for name in process_names))

    def test_alert_topic_uses_notification_goals_not_search_goals(self):
        requirements = [
            FakeRequirement("알림 수신 설정(채널/유형)", "앱푸시/문자/이메일 등 알림 채널과 유형 단위로 수신 여부를 설정한다.", depth4="통합 알림"),
            FakeRequirement("인앱 알림센터(다음 행동 허브)", "고객이 알림센터에서 거래, 보안, 주문상태, 혜택 만료 알림을 확인한다.", depth4="통합 알림"),
            FakeRequirement("알림 상세 화면 이동 및 컨텍스트 전달", "알림 클릭 시 관련 상세 화면으로 이동하고 필요한 컨텍스트를 전달한다.", depth4="통합 알림"),
            FakeRequirement("잔고 부족 사전 알림", "출금 예정일 전에 부족 위험과 조치 경로를 알림으로 제공한다.", depth4="통합 알림"),
            FakeRequirement("선택 알림 조용한 시간 설정", "긴급하지 않은 혜택·추천 알림은 조용한 시간과 다시알림 설정을 적용한다.", depth4="통합 알림"),
        ]

        spec = build_policy_spec(build_ctx("통합 알림", requirements))
        names = [row["name"] for row in spec["usecases"] if row.get("process_target") == "Y"]
        serialized = json.dumps(spec, ensure_ascii=False)
        process_names = [row["name"] for row in spec["processes"]]

        self.assertIn("통합 알림 확인", names)
        self.assertIn("통합 알림 수신 설정 실행", names)
        self.assertIn("통합 알림 후속 처리·복구 관리", names)
        self.assertFalse(any("탐색 조건 적용" in name for name in names))
        self.assertFalse(any("가입·신청" in name or "약관·동의" in name or "결제·혜택" in name for name in process_names))
        self.assertIn("수신 설정·채널 기준", serialized)
        self.assertIn("알림함·후속 연결", serialized)
        self.assertIn("우선순위·중복 제어", serialized)
        self.assertIn("필수·거래성 알림", serialized)

    def test_notification_process_templates_do_not_fall_back_to_settings_or_generic_info(self):
        receive_templates = process_templates_for_usecase({"actor": "고객", "name": "통합 알림 수신 설정 실행"})
        confirm_templates = process_templates_for_usecase({"actor": "고객", "name": "통합 알림 확인"})
        recover_templates = process_templates_for_usecase({"actor": "고객", "name": "통합 알림 후속 처리·복구 관리"})

        self.assertIn("수신 유형 및 채널 선택", [item["name"] for item in receive_templates])
        self.assertIn("알림함 진입 및 유형 확인", [item["name"] for item in confirm_templates])
        self.assertIn("발송 실패·수신 제한 복구", [item["name"] for item in recover_templates])
        self.assertFalse(any(item["name"] == "설정 목적 선택" for item in receive_templates))
        self.assertFalse(any(item["name"] == "업무 진입 및 대상 확인" for item in confirm_templates))

    def test_customer_center_hub_topic_uses_support_goals_not_search_or_purchase_goals(self):
        requirements = [
            FakeRequirement("고객센터 홈(해결 허브)", "고객센터 홈은 고객 문제 유형별 해결 경로와 셀프 처리 가능 범위를 제공한다.", depth4="고객센터_통합허브"),
            FakeRequirement("전화하기 전 Self 해결 카드", "전화하기 전에 고객이 직접 해결 가능한 카드와 준비 정보를 먼저 제시한다.", depth4="고객센터_통합허브"),
            FakeRequirement("상담 채널 선택 가이드", "문의 유형과 긴급도에 따라 채팅, 전화, 1:1 문의 채널을 안내한다.", depth4="고객센터_통합허브"),
            FakeRequirement("1:1 문의 첨부 및 상태 갱신", "문의 접수 시 첨부, 개인정보 동의, 답변 상태를 관리한다.", depth4="고객센터_통합허브"),
            FakeRequirement("상담 Single-view 통합 조회", "콜센터 재유입 시 고객 문맥과 상담 이력을 상담원에게 전달한다.", depth4="고객센터_통합허브"),
        ]

        spec = build_policy_spec(build_ctx("고객센터_통합허브", requirements))
        names = [row["name"] for row in spec["usecases"] if row.get("process_target") == "Y"]
        serialized = json.dumps(spec, ensure_ascii=False)
        process_names = [row["name"] for row in spec["processes"]]
        policy_by_id = {row["id"]: row["name"] for row in spec["policy_groups"]}
        detail_group_names = {policy_by_id.get(row.get("policy_id"), "") for row in spec["policy_details"]}
        detail_contents = "\n".join(row["content"] for row in spec["policy_details"])

        self.assertTrue(any("셀프 해결 허브 이용" in name for name in names))
        self.assertTrue(any("상담·문의 접수 실행" in name for name in names))
        self.assertTrue(any("상담 전환·후속 관리" in name for name in names))
        self.assertFalse(any("탐색 조건 적용" in name or "가입·신청" in name or "결제·혜택" in name for name in process_names))
        self.assertIn("셀프 해결 경로", serialized)
        self.assertIn("상담 채널·전환", serialized)
        self.assertIn("문의 접수·상태 관리", serialized)
        self.assertIn("상담 문맥·이력", serialized)
        self.assertIn("후속 업무 연결 정책", detail_group_names)
        self.assertIn("예외·상담 전환 정책", detail_group_names)
        self.assertIn("처리 요청 접수 정책", detail_group_names)
        self.assertIn("처리 결과·이력 정책", detail_group_names)
        self.assertIn("불가 사유, 필요한 보완 정보", detail_contents)
        self.assertIn("이전 상담 요약", detail_contents)

    def test_customer_center_hub_process_templates_are_support_specific(self):
        hub_templates = process_templates_for_usecase({"actor": "고객", "name": "고객센터 통합허브 셀프 해결 허브 이용"})
        inquiry_templates = process_templates_for_usecase({"actor": "고객", "name": "상담·문의 접수 실행"})
        follow_templates = process_templates_for_usecase({"actor": "고객", "name": "상담 전환·후속 관리"})
        hub_names = [item["name"] for item in hub_templates]
        inquiry_names = [item["name"] for item in inquiry_templates]
        follow_names = [item["name"] for item in follow_templates]

        self.assertIn("문제 유형 및 현재 상태 확인", hub_names)
        self.assertIn("셀프 해결 가능 범위 판정", hub_names)
        self.assertIn("문의 유형 및 채널 선택", inquiry_names)
        self.assertIn("문의 접수 및 상태 생성", inquiry_names)
        self.assertIn("직전 과업·상담 문맥 확인", follow_names)
        self.assertIn("상담 이관 정보 구성", follow_names)
        self.assertFalse(any(name == "업무 진입 및 대상 확인" for name in hub_names + inquiry_names + follow_names))

    def test_customer_center_faq_notice_topic_uses_content_guidance_goals(self):
        requirements = [
            FakeRequirement("고객센터 통합 검색(FAQ/콘텐츠/메뉴/정책)", "FAQ뿐 아니라 공지, 가이드, 정책, 메뉴를 통합 검색하고 바로 해결 가능 여부를 표시한다.", depth4="고객센터_FAQ/공지/이용안내"),
            FakeRequirement("FAQ 상세(해결 가이드)", "FAQ 상세에서 단계별 해결 가이드와 관련 화면 바로가기를 제공한다.", depth4="고객센터_FAQ/공지/이용안내"),
            FakeRequirement("해결 성공 확인 및 후속 액션", "가이드 수행 후 미해결이면 추가 진단, 문의 템플릿, 상담 연결로 이어진다.", depth4="고객센터_FAQ/공지/이용안내"),
            FakeRequirement("공지 중요도/긴급도/영향 범위 구분", "일반 안내, 중요 변경, 긴급 공지, 장애/점검 공지를 구분하고 영향 범위를 표시한다.", depth4="고객센터_FAQ/공지/이용안내"),
            FakeRequirement("공통유의사항 노출순서 관리 기준 적용", "운영자는 적용영역별 공통유의사항의 노출순서를 설정하고 일괄 저장할 수 있어야 한다.", depth4="고객센터_FAQ/공지/이용안내"),
        ]

        spec = build_policy_spec(build_ctx("고객센터_FAQ/공지/이용안내", requirements))
        names = [row["name"] for row in spec["usecases"] if row.get("process_target") == "Y"]
        serialized = json.dumps(spec, ensure_ascii=False)
        process_names = [row["name"] for row in spec["processes"]]
        detail_contents = "\n".join(row["content"] for row in spec["policy_details"])

        self.assertTrue(any("FAQ·이용안내 탐색·확인" in name for name in names))
        self.assertTrue(any("해결 가이드 실행·후속 연결" in name for name in names))
        self.assertTrue(any("공지·변경 안내 확인" in name for name in names))
        self.assertFalse(any("탐색 조건 적용" in name or "가입·신청" in name or "셀프 해결 가능 범위 판정" in name for name in process_names))
        self.assertIn("FAQ 탐색·추천", serialized)
        self.assertIn("이용안내·가이드", serialized)
        self.assertIn("공지·장애·점검", serialized)
        self.assertIn("해결 실패·CS 연결", serialized)
        self.assertIn("콘텐츠 운영·버전 관리", serialized)
        self.assertIn("적용일", detail_contents)
        self.assertIn("영향 범위", detail_contents)

    def test_customer_center_faq_notice_process_templates_do_not_use_hub_templates(self):
        explore_templates = process_templates_for_usecase({"actor": "고객", "name": "고객센터 FAQ·공지·이용안내 FAQ·이용안내 탐색·확인"})
        guide_templates = process_templates_for_usecase({"actor": "고객", "name": "해결 가이드 실행·후속 연결"})
        notice_templates = process_templates_for_usecase({"actor": "고객", "name": "공지·변경 안내 확인"})
        names = [item["name"] for item in explore_templates + guide_templates + notice_templates]

        self.assertIn("도움 콘텐츠 목적 선택", names)
        self.assertIn("FAQ·가이드 검색 및 추천", names)
        self.assertIn("해결 가이드 상세 확인", names)
        self.assertIn("공지 유형 및 영향 범위 확인", names)
        self.assertFalse(any(name == "셀프 해결 가능 범위 판정" for name in names))
        self.assertFalse(any(name == "업무 진입 및 대상 확인" for name in names))

    def test_customer_center_store_topic_uses_visit_feasibility_goals(self):
        requirements = [
            FakeRequirement("매장 찾기 지도·리스트 검색", "위치 정보 동의 시 근처 매장을 추천하고 거리순, 지역, 지하철, 매장 속성 필터를 제공한다.", depth4="고객센터_매장안내"),
            FakeRequirement("매장별 처리 가능 업무/예약 가능 여부 안내", "고객은 가까운 매장이 자신의 문제를 실제로 해결할 수 있는지 미리 판단할 수 있어야 한다.", depth4="고객센터_매장안내"),
            FakeRequirement("단골 대리점 등록 및 관리", "고객이 원하는 대리점을 단골로 등록/해제하고 혜택/알림 수신 동의를 분리해 안내한다.", depth4="고객센터_매장안내"),
            FakeRequirement("대리점 전용 URL 발급/공유", "대리점별 고유 URL과 QR, 단축 링크를 제공하고 접근 권한, 만료, 리다이렉트 정책을 정의한다.", depth4="고객센터_매장안내"),
            FakeRequirement("매장찾기 팝업 통합 운영", "운영자는 고객 위치 기반 통합 운영 가능 여부와 단일 공통 팝업 전환 조건을 정의한다.", depth4="고객센터_매장안내"),
        ]

        spec = build_policy_spec(build_ctx("고객센터_매장안내", requirements))
        names = [row["name"] for row in spec["usecases"] if row.get("process_target") == "Y"]
        process_names = [row["name"] for row in spec["processes"]]
        serialized = json.dumps(spec, ensure_ascii=False)
        detail_contents = "\n".join(row["content"] for row in spec["policy_details"])

        self.assertTrue(any("매장 탐색·방문 가능성 확인" in name for name in names))
        self.assertTrue(any("방문 준비·예약 실행" in name for name in names))
        self.assertTrue(any("매장 이용 예외·대체 경로 확인" in name for name in names))
        self.assertIn("매장 검색·위치 기준", serialized)
        self.assertIn("방문 가능성·예약 기준", serialized)
        self.assertIn("대리점 사이트·URL 운영", serialized)
        self.assertIn("단골 매장·개인화", serialized)
        self.assertFalse(any("FAQ·가이드 검색" in name or "셀프 해결 가능 범위 판정" in name for name in process_names))
        self.assertIn("위치 동의", detail_contents)
        self.assertIn("예약 가능 여부", detail_contents)

    def test_customer_center_store_process_templates_are_store_specific(self):
        explore_templates = process_templates_for_usecase({"actor": "고객", "name": "매장 탐색·방문 가능성 확인"})
        reserve_templates = process_templates_for_usecase({"actor": "고객", "name": "방문 준비·예약 실행"})
        exception_templates = process_templates_for_usecase({"actor": "고객", "name": "매장 이용 예외·대체 경로 확인"})
        names = [item["name"] for item in explore_templates + reserve_templates + exception_templates]

        self.assertIn("방문 목적 및 위치 기준 선택", names)
        self.assertIn("매장 검색·속성 필터 적용", names)
        self.assertIn("방문 업무와 예약 가능 여부 확인", names)
        self.assertIn("대체 매장·온라인 경로 안내", names)
        self.assertFalse(any(name == "도움 콘텐츠 목적 선택" for name in names))
        self.assertFalse(any(name == "셀프 해결 가능 범위 판정" for name in names))

    def test_settings_topic_uses_control_goals_not_search_goals(self):
        requirements = [
            FakeRequirement("개인화 서비스 제공 동의/설정 진입 및 범위 제어", "고객은 설정에서 개인화 추천, AI 도움 기능 제공 여부를 선택할 수 있어야 한다.", depth4="설정"),
            FakeRequirement("알림 환경설정 연동(수신/표시/채널)", "업무 알림의 수신 여부와 표시 방식을 설정한다.", depth4="설정"),
            FakeRequirement("개인화 초기화(원클릭 리셋)", "개인화 학습 데이터와 추천 기록을 초기화할 수 있다.", depth4="설정"),
            FakeRequirement("자동 로그아웃/세션 정책 설정", "자동 로그아웃 조건을 설정 또는 안내한다.", depth4="설정"),
            FakeRequirement("가입·변경 업무 다국어 제공", "고객이 설정에서 언어와 안내 표시 방식을 선택한다.", depth4="설정"),
        ]

        spec = build_policy_spec(build_ctx("설정", requirements))
        names = [row["name"] for row in spec["usecases"] if row.get("process_target") == "Y"]
        process_names = [row["name"] for row in spec["processes"]]
        serialized = json.dumps(spec, ensure_ascii=False)

        self.assertIn("설정 상태·권한 관리", names)
        self.assertIn("설정 개인화·알림 관리", names)
        self.assertIn("설정 초기화·삭제 관리", names)
        self.assertFalse(any(is_step_like_usecase_name(name) for name in names))
        self.assertFalse(any("정보 탐색" in name or "탐색 조건 적용" in name for name in names))
        self.assertFalse(any("가입·신청" in name for name in process_names))
        self.assertFalse(any("약관·동의" in name for name in process_names))
        self.assertIn("개인화·접근성 설정", serialized)
        self.assertIn("동의·권한 설정", serialized)
        self.assertIn("기록·초기화 설정", serialized)
        self.assertIn("언어, 쉬운모드, 홈 우선 영역", serialized)
        self.assertIn("현재 설정 상태, 시스템 권한, 보안·세션", serialized)
        self.assertIn("개인화, 홈 구성, 알림 환경", serialized)
        self.assertNotIn("가입·변경 업무 다국어 제공 중", serialized)

    def test_settings_and_terms_process_templates_are_topic_specific(self):
        settings_templates = process_templates_for_usecase({"actor": "고객", "name": "설정 개인화·알림 관리"})
        terms_templates = process_templates_for_usecase({"actor": "고객", "name": "통합 약관 필수·선택 동의 관리"})
        settings_names = [item["name"] for item in settings_templates]
        terms_names = [item["name"] for item in terms_templates]

        self.assertIn("설정 목적 선택", settings_names)
        self.assertIn("설정 결과 반영", settings_names)
        self.assertIn("업무 유형별 동의 항목 확인", terms_names)
        self.assertIn("필수·선택 동의 구분", terms_names)
        self.assertIn("미동의 제한 범위 판정", terms_names)
        self.assertFalse(any(name == "업무 진입 및 목적 확인" for name in settings_names + terms_names))

        rights_templates = process_templates_for_usecase({"actor": "고객", "name": "통합 약관 권리 관리"})
        rights_names = [item["name"] for item in rights_templates]
        self.assertIn("약관 원문·요약 열람", rights_names)
        self.assertIn("개인정보 제공·위탁 고지 확인", rights_names)
        self.assertIn("거부권 및 미동의 영향 확인", rights_names)

    def test_terms_topic_uses_consent_management_goals_not_search_goals(self):
        requirements = [
            FakeRequirement("약관 동의 상태 조회", "필수/선택 동의 현재 상태를 조회할 수 있다.", depth4="통합 약관"),
            FakeRequirement("선택 동의 철회/재동의", "선택 동의는 목적별로 철회/재동의 가능해야 한다.", depth4="통합 약관"),
            FakeRequirement("개인정보 제3자 제공/위탁 고지 접근", "제3자 제공/처리 위탁/보관 기간 등 주요 고지 정보에 접근한다.", depth4="통합 약관"),
            FakeRequirement("결제 동의/약관(필수)", "결제 필수 동의 항목을 요약+상세로 제공하고 미완료 시 결제를 차단한다.", depth4="통합 약관"),
        ]

        spec = build_policy_spec(build_ctx("통합 약관", requirements))
        names = [row["name"] for row in spec["usecases"] if row.get("process_target") == "Y"]
        serialized = json.dumps(spec, ensure_ascii=False)

        self.assertIn("통합 약관 권리 관리", names)
        self.assertIn("통합 약관 필수·선택 동의 관리", names)
        self.assertIn("통합 약관 변경·철회 관리", names)
        self.assertFalse(any(is_step_like_usecase_name(name) for name in names))
        self.assertFalse(any("통합 약관 정보 탐색" in name for name in names))
        self.assertFalse(any("탐색 조건 적용" in name for name in names))
        self.assertIn("인증·동의 정책", serialized)
        self.assertIn("약관 버전", serialized)
        self.assertIn("개인정보·제3자 고지", serialized)
        self.assertNotIn("해지·취소 상태·제한 기준", serialized)
        detail_names = [detail["name"] for detail in spec["policy_details"]]
        detail_contents = "\n".join(detail["content"] for detail in spec["policy_details"])
        self.assertFalse(any(detail["name"] == "약관 동의 상태 조회" for detail in spec["policy_details"]))
        self.assertFalse(any(detail["name"] == "선택 동의 철회/재동의" for detail in spec["policy_details"]))
        self.assertTrue(any("동의" in name and "기준" in name for name in detail_names))
        self.assertIn("철회", detail_contents)

    def test_terms_topic_fallback_does_not_create_step_like_request_result_usecase(self):
        spec = build_policy_spec(build_ctx("통합 약관", []))
        names = [row["name"] for row in spec["usecases"] if row.get("process_target") == "Y"]
        fallback_name, _ = default_usecase_for_actor("고객", "통합 약관")

        self.assertIn("통합 약관 권리 관리", names)
        self.assertIn("필수·선택 동의 관리", names)
        self.assertIn("동의 변경·철회 관리", names)
        self.assertFalse(any(is_step_like_usecase_name(name) for name in names))
        self.assertNotIn("통합 약관 요청 및 결과 확인", names)
        self.assertEqual("고객 동의·권리 관리", fallback_name)
        self.assertFalse(is_step_like_usecase_name(fallback_name))

    def test_terms_policy_details_are_requirement_specific_not_repeated_templates(self):
        requirements = [
            FakeRequirement("약관 동의 상태 조회", "필수/선택 동의 현재 상태와 약관 버전을 조회한다.", depth4="통합 약관"),
            FakeRequirement("선택 동의 철회/재동의", "선택 동의는 목적별로 철회와 재동의가 가능해야 한다.", depth4="통합 약관"),
            FakeRequirement("개인정보 제3자 제공/위탁 고지 접근", "제3자 제공, 처리 위탁, 보관 기간을 고지한다.", depth4="통합 약관"),
            FakeRequirement("쿠키 고지 및 거부권", "쿠키 이용 목적과 거부 방법을 안내한다.", depth4="통합 약관"),
            FakeRequirement("미동의/비활성 기본 경험", "선택 동의 미완료 고객에게도 기본 경험을 제공한다.", depth4="통합 약관"),
            FakeRequirement("약관 변경 재고지", "약관 변경 요약과 시행일, 재동의 필요 여부를 고지한다.", depth4="통합 약관"),
            FakeRequirement("결제 동의/약관", "결제 필수 약관 동의가 없으면 결제를 제한한다.", depth4="통합 약관"),
            FakeRequirement("오픈소스 고지", "오픈소스 라이선스 고지를 제공한다.", depth4="통합 약관"),
            FakeRequirement("동의 이력 저장", "동의, 철회, 고지 확인 이력을 저장한다.", depth4="통합 약관"),
        ]

        spec = build_policy_spec(build_ctx("통합 약관", requirements))
        details = spec["policy_details"]
        contents = "\n".join(detail["content"] for detail in details)
        errors = validate_policy_specificity(spec)

        self.assertFalse(any("같은 패턴으로 반복" in error for error in errors))
        self.assertIn("필수·선택 동의의 현재 상태", contents)
        self.assertIn("목적별 선택 동의의 철회와 재동의", contents)
        self.assertIn("제3자 제공 또는 처리 위탁", contents)
        self.assertIn("쿠키·추적 기반 이용 목적", contents)

    def test_composite_requirement_theme_usecase_is_not_rejected_as_step(self):
        self.assertFalse(
            is_step_like_usecase_name("멤버십 회원 가입 대상 조건 검증 및 회선/모회선 인증 및 가입유형 분기 조건 확인")
        )
        self.assertFalse(is_step_like_usecase_name("상품 연동/인증 기준 검증 및 처리 결과 확정"))
        self.assertTrue(is_step_like_usecase_name("대상 확인"))
        self.assertTrue(is_step_like_usecase_name("본인확인"))
        self.assertTrue(is_step_like_usecase_name("인증번호 유효시간 확인"))
        self.assertTrue(is_step_like_usecase_name("상품상세/담기 요청 및 결과 확인"))


if __name__ == "__main__":
    unittest.main()
