"""BPMN 2.0 XML renderer for policy process definitions."""

from __future__ import annotations

import html
import json
import re
import xml.dom.minidom
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple


BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"
BPMN_JS_VIEWER_CDN = "https://unpkg.com/bpmn-js/dist/bpmn-viewer.production.min.js"

ET.register_namespace("bpmn", BPMN_NS)
ET.register_namespace("bpmndi", BPMNDI_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("di", DI_NS)


@dataclass(frozen=True)
class BpmnArtifactPaths:
    bpmn: Path
    viewer: Path


def build_bpmn_xml(spec: Mapping[str, Any]) -> str:
    """Build a deterministic BPMN 2.0 XML document from policy process JSON."""

    processes = [item for item in spec.get("processes", []) if isinstance(item, Mapping)]
    topic = str(
        (spec.get("meta", {}).get("topic_display") or spec.get("meta", {}).get("topic", "NOVA 정책서"))
        if isinstance(spec.get("meta"), Mapping)
        else "NOVA 정책서"
    )
    process_id = "Process_" + bpmn_safe_id(topic)

    definitions = ET.Element(
        qn(BPMN_NS, "definitions"),
        {
            "id": f"Definitions_{bpmn_safe_id(topic)}",
            "targetNamespace": "https://nova-policy.local/bpmn",
        },
    )
    process_element = ET.SubElement(
        definitions,
        qn(BPMN_NS, "process"),
        {"id": process_id, "name": f"{topic} 전체 업무 흐름", "isExecutable": "false"},
    )
    lane_set = ET.SubElement(process_element, qn(BPMN_NS, "laneSet"), {"id": "LaneSet_1"})
    used_ids = {process_id, "LaneSet_1"}

    usecase_names = {
        str(item.get("id", "")).strip(): str(item.get("name", "")).strip()
        for item in spec.get("usecases", [])
        if isinstance(item, Mapping)
    }
    grouped = group_processes_by_usecase(processes)

    diagram_width = max(1120, max((len(rows) for _, rows in grouped), default=1) * 220 + 560)
    lane_height = 170

    shapes: List[Tuple[str, int, int, int, int]] = []
    edges: List[Tuple[str, List[Tuple[int, int]]]] = []

    for row_index, (usecase_id, rows) in enumerate(grouped):
        lane_y = 70 + row_index * lane_height
        lane_id = make_unique_bpmn_id(used_ids, "Lane", usecase_id or f"UNASSIGNED_{row_index + 1}")
        lane_name = compact_name(usecase_id, usecase_names.get(usecase_id, "유즈케이스 미지정"))
        lane = ET.SubElement(lane_set, qn(BPMN_NS, "lane"), {"id": lane_id, "name": lane_name})
        shapes.append((lane_id, 40, lane_y - 45, diagram_width - 80, 140))

        node_refs: List[str] = []
        node_defs: List[Tuple[str, str, Dict[str, str]]] = []
        flow_defs: List[Tuple[str, str, str, List[Tuple[int, int]]]] = []

        start_id = make_unique_bpmn_id(used_ids, "Start", usecase_id or "UNASSIGNED")
        end_id = make_unique_bpmn_id(used_ids, "End", usecase_id or "UNASSIGNED")
        node_refs.extend([start_id])
        node_defs.append(("startEvent", start_id, {"name": "시작"}))
        shapes.append((start_id, 112, lane_y - 18, 36, 36))

        previous_id = start_id
        previous_anchor = (148, lane_y)
        for process_index, process in enumerate(rows):
            raw_id = str(process.get("id", "") or f"P{process_index + 1}").strip()
            task_id = make_unique_bpmn_id(used_ids, "Task", raw_id)
            task_name = compact_name(raw_id, str(process.get("name", "") or "프로세스").strip(), max_len=72)
            x = 240 + process_index * 220
            y = lane_y - 40
            node_refs.append(task_id)
            node_defs.append(("task", task_id, {"name": task_name}))
            shapes.append((task_id, x, y, 170, 80))
            flow_id = make_unique_bpmn_id(used_ids, "Flow", f"{previous_id}_{task_id}")
            flow_defs.append((flow_id, previous_id, task_id, [previous_anchor, (x, lane_y)]))
            previous_id = task_id
            previous_anchor = (x + 170, lane_y)

        end_x = 240 + max(1, len(rows)) * 220
        node_refs.append(end_id)
        node_defs.append(("endEvent", end_id, {"name": "종료"}))
        shapes.append((end_id, end_x, lane_y - 18, 36, 36))
        flow_defs.append(
            (
                make_unique_bpmn_id(used_ids, "Flow", f"{previous_id}_{end_id}"),
                previous_id,
                end_id,
                [previous_anchor, (end_x, lane_y)],
            )
        )

        for node_ref in node_refs:
            ET.SubElement(lane, qn(BPMN_NS, "flowNodeRef")).text = node_ref
        for tag, element_id, attrs in node_defs:
            element = ET.SubElement(process_element, qn(BPMN_NS, tag), {"id": element_id, **attrs})
            for flow_id, source_id, target_id, _ in flow_defs:
                if target_id == element_id:
                    ET.SubElement(element, qn(BPMN_NS, "incoming")).text = flow_id
                if source_id == element_id:
                    ET.SubElement(element, qn(BPMN_NS, "outgoing")).text = flow_id
        for flow_id, source_id, target_id, waypoints in flow_defs:
            ET.SubElement(
                process_element,
                qn(BPMN_NS, "sequenceFlow"),
                {"id": flow_id, "sourceRef": source_id, "targetRef": target_id},
            )
            edges.append((flow_id, waypoints))

    diagram = ET.SubElement(definitions, qn(BPMNDI_NS, "BPMNDiagram"), {"id": "BPMNDiagram_1"})
    plane = ET.SubElement(diagram, qn(BPMNDI_NS, "BPMNPlane"), {"id": "BPMNPlane_1", "bpmnElement": process_id})
    for element_id, x, y, width, height in shapes:
        shape = ET.SubElement(plane, qn(BPMNDI_NS, "BPMNShape"), {"id": f"{element_id}_di", "bpmnElement": element_id})
        ET.SubElement(shape, qn(DC_NS, "Bounds"), {"x": str(x), "y": str(y), "width": str(width), "height": str(height)})
    for flow_id, waypoints in edges:
        edge = ET.SubElement(plane, qn(BPMNDI_NS, "BPMNEdge"), {"id": f"{flow_id}_di", "bpmnElement": flow_id})
        for x, y in waypoints:
            ET.SubElement(edge, qn(DI_NS, "waypoint"), {"x": str(x), "y": str(y)})

    xml_bytes = ET.tostring(definitions, encoding="utf-8", xml_declaration=True)
    return xml.dom.minidom.parseString(xml_bytes).toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def build_bpmn_io_viewer_html(xml: str, *, title: str = "BPMN 2.0 Process Diagram", bpmn_file_name: str = "process.bpmn") -> str:
    """Build a standalone bpmn.io viewer HTML with embedded BPMN XML."""

    payload = json.dumps({"xml": xml}, ensure_ascii=False).replace("</", "<\\/")
    safe_title = html.escape(title)
    safe_bpmn_file_name = html.escape(bpmn_file_name)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1" name="viewport"/>
<title>{safe_title}</title>
<style>
body {{ margin: 0; background: #f6f8fb; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", Arial, sans-serif; }}
.viewer-shell {{ min-height: 100vh; display: flex; flex-direction: column; }}
.viewer-toolbar {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 14px 18px; border-bottom: 1px solid #dbe3ef; background: #ffffff; }}
.viewer-title {{ margin: 0; font-size: 15px; font-weight: 800; }}
.viewer-meta {{ color: #64748b; font-size: 12px; font-weight: 700; }}
.viewer-actions {{ display: flex; align-items: center; gap: 8px; }}
.viewer-button {{ display: inline-flex; align-items: center; border: 1px solid #bfdbfe; border-radius: 999px; background: #fff; color: #2563eb; cursor: pointer; font-size: 12px; font-weight: 800; padding: 8px 12px; text-decoration: none; }}
#canvas {{ flex: 1 1 auto; min-height: 720px; background: #ffffff; }}
.viewer-fallback {{ display: none; margin: 18px; padding: 16px; border: 1px dashed #bfdbfe; border-radius: 12px; background: #eff6ff; color: #1f2937; line-height: 1.65; }}
.is-failed #canvas {{ display: none; }}
.is-failed .viewer-fallback {{ display: block; }}
</style>
<script src="{BPMN_JS_VIEWER_CDN}"></script>
</head>
<body>
<div class="viewer-shell" id="viewer-shell">
<div class="viewer-toolbar">
<div>
<h1 class="viewer-title">{safe_title}</h1>
<div class="viewer-meta">Rendered with bpmn.io bpmn-js viewer</div>
</div>
<div class="viewer-actions">
<a class="viewer-button" href="{safe_bpmn_file_name}" download="{safe_bpmn_file_name}">BPMN XML 다운로드</a>
</div>
</div>
<div id="canvas"></div>
<div class="viewer-fallback">bpmn.io viewer를 불러오지 못했습니다. 같은 이름의 .bpmn 파일을 bpmn.io 또는 Camunda Modeler에서 열어 확인할 수 있습니다.</div>
<script id="bpmn-process-xml" type="application/json">{payload}</script>
</div>
<script>
(function () {{
  function readBpmnXml() {{
    var source = document.getElementById("bpmn-process-xml");
    if (!source) {{
      return "";
    }}
    try {{
      return (JSON.parse(source.textContent || "{{}}").xml || "");
    }} catch (error) {{
      console.warn("BPMN payload parse failed.", error);
      return "";
    }}
  }}
  function markFailed(error) {{
    document.getElementById("viewer-shell").classList.add("is-failed");
    if (error) {{
      console.warn("BPMN render failed.", error);
    }}
  }}
  function render() {{
    var xml = readBpmnXml();
    if (!xml || !window.BpmnJS) {{
      markFailed();
      return;
    }}
    try {{
      var viewer = new window.BpmnJS({{ container: "#canvas" }});
      viewer.importXML(xml).then(function () {{
        viewer.get("canvas").zoom("fit-viewport");
      }}).catch(markFailed);
    }} catch (error) {{
      markFailed(error);
    }}
  }}
  function bindDownload() {{
    var button = document.querySelector("[data-bpmn-download]");
    if (!button) {{
      return;
    }}
    button.addEventListener("click", function () {{
      var xml = readBpmnXml();
      if (!xml) {{
        return;
      }}
      var blob = new Blob([xml], {{ type: "application/xml;charset=utf-8" }});
      var url = URL.createObjectURL(blob);
      var anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "{safe_bpmn_file_name}";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(function () {{ URL.revokeObjectURL(url); }}, 1000);
    }});
  }}
  if (document.readyState === "loading") {{
    document.addEventListener("DOMContentLoaded", function () {{
      render();
      bindDownload();
    }});
  }} else {{
    render();
    bindDownload();
  }}
}})();
</script>
</body>
</html>
"""


def write_bpmn_artifacts(spec: Mapping[str, Any], bpmn_path: Path) -> BpmnArtifactPaths:
    """Write BPMN XML and a standalone bpmn.io viewer next to it."""

    bpmn_path.parent.mkdir(parents=True, exist_ok=True)
    xml = build_bpmn_xml(spec)
    bpmn_path.write_text(xml, encoding="utf-8")
    viewer_path = bpmn_io_viewer_path_for(bpmn_path)
    viewer_title = bpmn_title_from_spec(spec)
    viewer_path.write_text(
        build_bpmn_io_viewer_html(xml, title=viewer_title, bpmn_file_name=bpmn_path.name),
        encoding="utf-8",
    )
    return BpmnArtifactPaths(bpmn=bpmn_path, viewer=viewer_path)


def bpmn_io_viewer_path_for(bpmn_path: Path) -> Path:
    return bpmn_path.with_name(f"{bpmn_path.stem}_viewer.html")


def bpmn_title_from_spec(spec: Mapping[str, Any]) -> str:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    topic = str(meta.get("topic_display") or meta.get("topic") or "정책서").strip()
    return f"{topic} 전체 업무 흐름도"


def group_processes_by_usecase(processes: Iterable[Mapping[str, Any]]) -> List[Tuple[str, List[Mapping[str, Any]]]]:
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for process in processes:
        usecase_id = str(process.get("usecase_id", "") or "UNASSIGNED").strip() or "UNASSIGNED"
        grouped[usecase_id].append(process)
    if not grouped:
        grouped["UNASSIGNED"].append({"id": "PR-EMPTY-001", "name": "프로세스 미정"})
    return list(grouped.items())


def qn(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def bpmn_safe_id(value: object) -> str:
    text = re.sub(r"[^0-9A-Za-z_]+", "_", str(value or "").strip())
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        text = "Item"
    if text[0].isdigit():
        text = f"N_{text}"
    return text


def make_unique_bpmn_id(used_ids: set[str], prefix: str, raw: object) -> str:
    base = f"{prefix}_{bpmn_safe_id(raw)}"
    candidate = base
    index = 2
    while candidate in used_ids:
        candidate = f"{base}_{index}"
        index += 1
    used_ids.add(candidate)
    return candidate


def compact_name(*parts: object, max_len: int = 80) -> str:
    text = " ".join(str(part).strip() for part in parts if str(part or "").strip())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"
