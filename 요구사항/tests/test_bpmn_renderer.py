import xml.etree.ElementTree as ET

from src.bpmn_renderer import (
    BPMN_JS_VIEWER_CDN,
    BPMN_NS,
    BPMNDI_NS,
    build_bpmn_io_viewer_html,
    build_bpmn_xml,
    write_bpmn_artifacts,
)


def sample_spec():
    return {
        "meta": {"topic": "회원 가입탈퇴"},
        "usecases": [{"id": "UC-MBR-001", "name": "회원 가입"}],
        "processes": [
            {"id": "PR-MBR-001", "usecase_id": "UC-MBR-001", "name": "가입 정보 확인"},
            {"id": "PR-MBR-002", "usecase_id": "UC-MBR-001", "name": "인증 결과 반영"},
        ],
    }


def test_build_bpmn_xml_creates_process_tasks_and_di():
    spec = sample_spec()

    xml = build_bpmn_xml(spec)
    root = ET.fromstring(xml)
    namespaces = {"bpmn": BPMN_NS, "bpmndi": BPMNDI_NS}

    process = root.find("bpmn:process", namespaces)
    assert process is not None
    assert process.attrib["isExecutable"] == "false"

    task_names = [task.attrib.get("name", "") for task in root.findall(".//bpmn:task", namespaces)]
    assert any("PR-MBR-001 가입 정보 확인" in name for name in task_names)
    assert any("PR-MBR-002 인증 결과 반영" in name for name in task_names)
    assert not root.findall(".//bpmn:exclusiveGateway", namespaces)

    lanes = root.findall(".//bpmn:lane", namespaces)
    assert lanes
    assert lanes[0].attrib["name"] == "UC-MBR-001 회원 가입"
    assert root.findall(".//bpmndi:BPMNShape", namespaces)
    assert root.findall(".//bpmndi:BPMNEdge", namespaces)


def test_build_bpmn_io_viewer_html_embeds_bpmn_js_viewer():
    xml = build_bpmn_xml(sample_spec())

    viewer_html = build_bpmn_io_viewer_html(xml, title="회원 가입탈퇴 전체 업무 흐름도", bpmn_file_name="flow.bpmn")

    assert BPMN_JS_VIEWER_CDN in viewer_html
    assert "Rendered with bpmn.io bpmn-js viewer" in viewer_html
    assert 'new window.BpmnJS({ container: "#canvas" })' in viewer_html
    assert 'type="application/json">{"xml":' in viewer_html
    assert "flow.bpmn" in viewer_html


def test_write_bpmn_artifacts_writes_xml_and_standalone_viewer(tmp_path):
    bpmn_path = tmp_path / "NC_회원가입탈퇴_정책서_간소화_v0.1_전체업무흐름도.bpmn"

    artifacts = write_bpmn_artifacts(sample_spec(), bpmn_path)

    assert artifacts.bpmn == bpmn_path
    assert artifacts.viewer == tmp_path / "NC_회원가입탈퇴_정책서_간소화_v0.1_전체업무흐름도_viewer.html"
    assert artifacts.bpmn.exists()
    assert artifacts.viewer.exists()
    assert "<bpmn:definitions" in artifacts.bpmn.read_text(encoding="utf-8")
    assert "bpmn.io bpmn-js viewer" in artifacts.viewer.read_text(encoding="utf-8")
