"""HTML renderer for validated policy JSON specifications."""

from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from typing import Dict, Iterable, List, Mapping, Sequence

try:
    from bpmn_renderer import build_bpmn_xml
except ImportError:  # pragma: no cover - package import fallback.
    from .bpmn_renderer import build_bpmn_xml


def render_policy_html(spec: dict, template_html: str, template_type: str = "simple", stage_key: str = "10") -> str:
    style = extract_style(template_html)
    meta = spec["meta"]
    topic_label = meta.get("topic_display") or meta.get("topic", "")
    stage_rank_value = stage_rank(stage_key)
    sections: List[str] = [render_cover(spec)]
    sections.append(render_history(spec))
    if stage_rank_value >= 1:
        sections.append(render_overview(spec))
    if stage_rank_value >= 2:
        sections.append(render_terms(spec))
    if stage_rank_value >= 3:
        sections.append(render_actors(spec))
    if stage_rank_value >= 4:
        sections.append(render_usecase_table(spec))
    if stage_rank_value >= 5:
        sections.append(render_usecase_diagram(spec))
    if stage_rank_value >= 6:
        sections.append(render_states(spec))
    if stage_rank_value >= 7:
        sections.append(render_processes(spec, template_type))
    if stage_rank_value >= 8:
        sections.append(render_functions(spec, template_type))
    if stage_rank_value >= 9:
        sections.append(render_policies(spec))
    if stage_rank_value >= 10:
        sections.append(render_final_check(spec))

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1" name="viewport"/>
<title>{esc(topic_label)} 정책서 {esc(meta.get("document_type", ""))} {esc(meta.get("version", ""))}</title>
{style}
{render_mermaid_assets()}
</head>
<body>
<div class="page">
{''.join(sections)}
</div>
</body>
</html>
"""


def stage_rank(stage_key: str) -> int:
    if stage_key.isdigit():
        return int(stage_key)
    match = re.match(r"(?P<rank>\d+)_", stage_key)
    if match:
        return int(match.group("rank"))
    return 10 if stage_key == "full" else 4


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


def render_mermaid_assets() -> str:
    return """<style>
.diagram-wrap { overflow-x: auto; }
.diagram-wrap > svg { display: block; max-width: none; }
.diagram-wrap .mermaid { min-width: 720px; margin: 0; padding: 18px; border-radius: 12px; background: #fbfcff; }
.state-transition-mermaid .mermaid { min-width: 980px; padding: 24px 28px; }
.diagram-wrap .mermaid svg { max-width: none; }
.diagram-caption { margin: 0 0 8px; color: #475569; font-size: 12px; font-weight: 700; }
.diagram-fallback { margin: 8px 0 0; padding: 16px 18px; border: 1px dashed #bfdbfe; border-radius: 12px; background: #f8fbff; color: #1f2937; white-space: pre-wrap; line-height: 1.65; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; }
.diagram-static { margin: 10px 0 16px; padding: 18px; border: 1px solid #dbeafe; border-radius: 16px; background: linear-gradient(135deg, #f8fbff 0%, #ffffff 62%, #eef6ff 100%); color: #0f172a; overflow-x: auto; }
.diagram-static-title { margin: 0 0 14px; color: #2563eb; font-size: 12px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.bpmn-viewer-wrap { margin: 12px 0 18px; padding: 16px; border: 1px solid #dbeafe; border-radius: 16px; background: linear-gradient(135deg, #f8fbff 0%, #ffffff 62%, #eef6ff 100%); color: #0f172a; overflow-x: auto; }
.bpmn-viewer-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 12px; }
.bpmn-viewer-title { color: #2563eb; font-size: 12px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.bpmn-download-button { display: inline-flex; align-items: center; border: 1px solid #bfdbfe; border-radius: 999px; background: #fff; color: #2563eb; cursor: pointer; font-size: 12px; font-weight: 800; padding: 8px 12px; text-decoration: none; }
.bpmn-viewer { display: none; width: 100%; min-width: 760px; height: 520px; border: 1px solid #dbe3ef; border-radius: 14px; background: #fff; }
.bpmn-viewer-wrap.is-rendered .bpmn-viewer { display: block; }
.bpmn-viewer-wrap.is-rendered .bpmn-fallback { display: none; }
.bpmn-fallback { margin-top: 10px; }
.bpmn-process-diagram { min-height: 0; padding: 14px 16px; align-items: flex-start; justify-content: flex-start; }
.bpmn-process-diagram > svg { display: block; height: auto; }
.static-boundary { min-width: 760px; padding: 16px; border: 1px dashed #bfdbfe; border-radius: 14px; background: rgba(255,255,255,.72); }
.static-lane { display: flex; align-items: center; gap: 12px; margin: 12px 0; }
.static-actor, .static-state, .static-task, .static-usecase, .static-system, .static-empty { box-sizing: border-box; border-radius: 14px; border: 1px solid #dbe3ef; background: #fff; box-shadow: 0 4px 14px rgba(15,23,42,.05); }
.static-actor { flex: 0 0 150px; padding: 13px 14px; border-color: #fed7aa; background: #fff7ed; color: #7c2d12; font-weight: 800; text-align: center; }
.static-system { flex: 0 0 150px; padding: 13px 14px; border-color: #cbd5e1; background: #f8fafc; color: #334155; font-weight: 800; text-align: center; }
.static-usecases, .static-flow { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; min-width: 0; }
.static-usecase { min-width: 170px; max-width: 240px; padding: 12px 14px; border-color: #93c5fd; background: #eff6ff; color: #1e3a8a; font-weight: 800; }
.static-state { min-width: 150px; padding: 12px 14px; border-color: #bfdbfe; background: #eff6ff; color: #1d4ed8; font-weight: 800; text-align: center; }
.static-task { min-width: 170px; max-width: 240px; padding: 12px 14px; border-color: #a7f3d0; background: #ecfdf5; color: #065f46; font-weight: 800; }
.static-gateway { padding: 10px 12px; border: 1px solid #fcd34d; border-radius: 12px; background: #fffbeb; color: #92400e; font-weight: 800; }
.static-arrow { flex: 0 0 auto; color: #2563eb; font-weight: 900; }
.static-note { display: block; margin-top: 6px; color: #64748b; font-size: 12px; font-weight: 600; line-height: 1.45; }
.static-empty { padding: 18px; color: #64748b; text-align: center; }
.usecase-list-table,
.state-code-table,
.state-transition-table,
.process-list-table,
.function-list-table,
.policy-list-table { table-layout: fixed; }
.usecase-list-table th:nth-child(1), .usecase-list-table td:nth-child(1) { width: 15% !important; }
.usecase-list-table th:nth-child(2), .usecase-list-table td:nth-child(2) { width: 13% !important; }
.usecase-list-table th:nth-child(3), .usecase-list-table td:nth-child(3) { width: 19% !important; }
.usecase-list-table th:nth-child(4), .usecase-list-table td:nth-child(4) { width: 38% !important; }
.usecase-list-table th:nth-child(5), .usecase-list-table td:nth-child(5) { width: 15% !important; }
.state-code-table th:nth-child(1), .state-code-table td:nth-child(1) { width: 16% !important; }
.state-code-table th:nth-child(2), .state-code-table td:nth-child(2) { width: 16% !important; }
.state-code-table th:nth-child(3), .state-code-table td:nth-child(3) { width: 42% !important; }
.state-code-table th:nth-child(4), .state-code-table td:nth-child(4) { width: 26% !important; }
.state-transition-table th:nth-child(1), .state-transition-table td:nth-child(1) { width: 16% !important; }
.state-transition-table th:nth-child(2), .state-transition-table td:nth-child(2) { width: 22% !important; }
.state-transition-table th:nth-child(3), .state-transition-table td:nth-child(3) { width: 16% !important; }
.state-transition-table th:nth-child(4), .state-transition-table td:nth-child(4) { width: 46% !important; }
.meta th { width: 180px !important; }
.meta td { width: auto !important; }
.process-list-table th:nth-child(1), .process-list-table td:nth-child(1) { width: 16% !important; }
.process-list-table th:nth-child(2), .process-list-table td:nth-child(2) { width: 18% !important; }
.process-list-table th:nth-child(3), .process-list-table td:nth-child(3) { width: 25% !important; }
.process-list-table th:nth-child(4), .process-list-table td:nth-child(4) { width: 22% !important; }
.process-list-table th:nth-child(5), .process-list-table td:nth-child(5) { width: 19% !important; }
.function-list-table th:nth-child(1), .function-list-table td:nth-child(1),
.policy-list-table th:nth-child(1), .policy-list-table td:nth-child(1) { width: 16% !important; }
.function-list-table th:nth-child(2), .function-list-table td:nth-child(2),
.policy-list-table th:nth-child(2), .policy-list-table td:nth-child(2) { width: 18% !important; }
.function-list-table th:nth-child(3), .function-list-table td:nth-child(3),
.policy-list-table th:nth-child(3), .policy-list-table td:nth-child(3) { width: 32% !important; }
.function-list-table th:nth-child(4), .function-list-table td:nth-child(4),
.policy-list-table th:nth-child(4), .policy-list-table td:nth-child(4) { width: 34% !important; }
.policy-group { margin: 6px 0 22px; }
.policy-item { margin: 0 0 16px; }
.policy-item + .policy-item { margin-top: 14px; }
.policy-item-title { margin: 0 0 6px; font-weight: 700; line-height: 1.55; }
.policy-item-content { margin: 0 0 0 18px; padding-left: 12px; border-left: 2px solid #e5edf7; color: #111827; line-height: 1.72; }
.policy-item-line { display: block; margin: 3px 0; }
.diagram-wrap.mermaid-diagram { display: none; }
.diagram-wrap.mermaid-diagram.mermaid-rendered { display: block; }
.diagram-wrap.mermaid-diagram.mermaid-rendered + .diagram-fallback-html,
.diagram-wrap.mermaid-diagram.mermaid-rendered + .diagram-fallback { display: none; }
</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script src="https://unpkg.com/bpmn-js/dist/bpmn-viewer.production.min.js"></script>
<script>
(function () {
  function markRenderedMermaidBlocks() {
    var renderedCount = 0;
    document.querySelectorAll(".diagram-wrap.mermaid-diagram").forEach(function (wrap) {
      var hasSvg = !!wrap.querySelector("svg");
      var hasError = !!wrap.querySelector(".error-icon, .mermaid-error")
        || /syntax error|parse error/i.test(wrap.textContent || "");
      if (hasSvg && !hasError) {
        wrap.classList.add("mermaid-rendered");
        renderedCount += 1;
      } else {
        wrap.classList.remove("mermaid-rendered");
      }
    });
    return renderedCount;
  }
  function renderMermaid() {
    if (!window.mermaid || !document.querySelector(".mermaid")) {
      return;
    }
    try {
      window.mermaid.initialize({
        startOnLoad: false,
        securityLevel: "loose",
        theme: "default",
        flowchart: { htmlLabels: true, curve: "basis" }
      });
      Promise.resolve(window.mermaid.run({ querySelector: ".mermaid" }))
        .then(function () {
          markRenderedMermaidBlocks();
        })
        .catch(function (error) {
          if (!markRenderedMermaidBlocks()) {
            console.warn("Mermaid render failed. Diagram fallback is displayed.", error);
          }
        });
    } catch (error) {
      if (!markRenderedMermaidBlocks()) {
        console.warn("Mermaid render failed. Diagram fallback is displayed.", error);
      }
    }
    window.setTimeout(markRenderedMermaidBlocks, 800);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderMermaid);
  } else {
    renderMermaid();
  }
})();
(function () {
  function readBpmnPayload(sourceId) {
    var source = document.getElementById(sourceId);
    if (!source) {
      return "";
    }
    try {
      var payload = JSON.parse(source.textContent || "{}");
      return payload.xml || "";
    } catch (error) {
      console.warn("BPMN payload parse failed.", error);
      return "";
    }
  }
  function renderBpmnViewers() {
    var containers = document.querySelectorAll("[data-bpmn-viewer]");
    if (!containers.length || !window.BpmnJS) {
      return;
    }
    containers.forEach(function (container) {
      var wrap = container.closest(".bpmn-viewer-wrap");
      var xml = readBpmnPayload(container.getAttribute("data-bpmn-source-id"));
      if (!xml) {
        return;
      }
      try {
        var viewer = new window.BpmnJS({ container: container });
        viewer.importXML(xml).then(function () {
          var canvas = viewer.get("canvas");
          canvas.zoom("fit-viewport");
          if (wrap) {
            wrap.classList.add("is-rendered");
          }
        }).catch(function (error) {
          if (wrap) {
            wrap.classList.add("is-failed");
          }
          console.warn("BPMN render failed. Static fallback is displayed.", error);
        });
      } catch (error) {
        if (wrap) {
          wrap.classList.add("is-failed");
        }
        console.warn("BPMN render failed. Static fallback is displayed.", error);
      }
    });
  }
  function bindBpmnDownload() {
    document.addEventListener("click", function (event) {
      var button = event.target.closest("[data-bpmn-download]");
      if (!button) {
        return;
      }
      var xml = readBpmnPayload(button.getAttribute("data-bpmn-download"));
      if (!xml) {
        return;
      }
      var blob = new Blob([xml], { type: "application/xml;charset=utf-8" });
      var url = URL.createObjectURL(blob);
      var anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = button.getAttribute("data-bpmn-file") || "process.bpmn";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      renderBpmnViewers();
      bindBpmnDownload();
    });
  } else {
    renderBpmnViewers();
    bindBpmnDownload();
  }
})();
</script>"""


def as_render_list(value: object) -> List[object]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [value]
    try:
        return list(value)  # type: ignore[arg-type]
    except TypeError:
        return [value]


def render_cover(spec: dict) -> str:
    meta = spec["meta"]
    topic_label = meta.get("topic_display") or meta.get("topic", "")
    author = str(meta.get("author", "")).strip()
    author_label = author if author.startswith("SK Telecom 플랫폼기획 2팀") else f"SK Telecom 플랫폼기획 2팀 / {author}"
    return f"""
<div class="eyebrow">통합채널 정책서 {esc(meta.get("document_type", ""))}</div>
<h1>{esc(topic_label)} 정책서</h1>
<table class="meta">
{tr(th("정책서 ID"), td(esc(meta.get("document_id", "")), "mono"))}
{tr(th("문서 구분"), td(esc(meta.get("document_type", ""))))}
{tr(th("문서 상태"), td(esc(meta.get("status") or meta.get("document_status", ""))))}
{tr(th("버전"), td(esc(meta.get("version", "")), "mono"))}
{tr(th("작성자"), td(esc(author_label)))}
{tr(th("작성일"), td(esc(meta.get("date") or meta.get("created_at", ""))))}
{tr(th("작성 기준"), td(join_lines(meta.get("authoring_basis", []))))}
</table>
"""


def render_history(spec: dict) -> str:
    rows = []
    for item in spec.get("history", []):
        change = item.get("change") or item.get("changes") or item.get("description") or item.get("summary") or ""
        rows.append(
            tr(
                td(esc(item.get("version", ""))),
                td(esc(change)),
                td(esc(item.get("date", ""))),
                td(esc(item.get("author", ""))),
            )
        )
    return f"""
<h2>0. 문서 히스토리</h2>
<table>
<thead>{tr(th("버전", style="width: 90px;"), th("변경 내용"), th("변경일자", style="width: 120px;"), th("변경자", style="width: 180px;"))}</thead>
<tbody>{''.join(rows)}</tbody>
</table>
"""


def render_overview(spec: dict) -> str:
    overview = spec["overview"]
    scope = "".join(
        f'<p class="plain-text">• {esc(item)}</p>'
        for item in as_render_list(overview.get("scope", []))
        if str(item).strip()
    )
    principle_lines = []
    for item in as_render_list(overview.get("principles", [])):
        if isinstance(item, Mapping):
            name = item.get("name") or item.get("title") or ""
            description = item.get("description") or item.get("detail") or ""
            if name and description:
                principle_lines.append(
                    f'<p class="principle-text">• <b>{esc(name)}</b>: {esc(description)}</p>'
                )
            elif name or description:
                principle_lines.append(f'<p class="principle-text">• {esc(name or description)}</p>')
            continue
        text = str(item).strip()
        if text:
            principle_lines.append(f'<p class="principle-text">• {esc(text)}</p>')
    principles = "".join(principle_lines)
    return f"""
<h2>1. 개요</h2>
<h3>가. 범위</h3>
{scope}
<h3>나. 설계 원칙</h3>
{principles}
"""


def render_terms(spec: dict) -> str:
    rows = []
    for item in as_render_list(spec.get("terms", [])):
        if isinstance(item, Mapping):
            rows.append(
                tr(
                    td(esc(item.get("id", "")), "mono"),
                    td(esc(item.get("name") or item.get("term") or item.get("title") or "")),
                    td(esc(item.get("description") or item.get("definition") or item.get("meaning") or "")),
                )
            )
        else:
            rows.append(tr(td("", "mono"), td(esc(item)), td("")))
    return f"""
<h2>2. 주요 용어</h2>
<p class="plain-text">본 장의 용어는 정책서 전반에서 동일한 의미로 사용한다.<br/>용어는 단순 설명이 아니라 프로세스, 기능, 정책 판단에 쓰이는 기준으로 정의한다.</p>
<table>
<thead>{tr(th("용어 ID", style="width: 130px;"), th("용어", style="width: 220px;"), th("설명"))}</thead>
<tbody>{''.join(rows)}</tbody>
</table>
"""


def render_usecases(spec: dict) -> str:
    return render_actors(spec) + render_usecase_table(spec) + render_usecase_diagram(spec) + render_states(spec)


def render_actors(spec: dict) -> str:
    actor_rows = [
        tr(td(esc(item.get("id", "")), "mono"), td(esc(item.get("name", ""))), td(esc(item.get("description", ""))))
        for item in spec.get("actors", [])
    ]
    return f"""
<h2>3. 유즈케이스 정의</h2>
<h3>가. 액터</h3>
<p class="plain-text">액터는 독립 책임 주체만 정의한다.<br/>로그인 고객, 비로그인 고객, 정상 고객, 제한 고객처럼 같은 고객의 상태 차이는 액터로 분리하지 않고 상태와 정책 조건에서 관리한다.</p>
<table>
<thead>{tr(th("액터 ID", style="width: 130px;"), th("액터명", style="width: 170px;"), th("설명"))}</thead>
<tbody>{''.join(actor_rows)}</tbody>
</table>
"""


def render_usecase_table(spec: dict) -> str:
    usecase_rows = [
        tr(
            td(esc(item.get("id", "")), "mono"),
            td(esc(item.get("actor", ""))),
            td(esc(item.get("name", ""))),
            td(esc(item.get("description", ""))),
            td(esc(item.get("process_target", "")), "center"),
        )
        for item in spec.get("usecases", [])
    ]
    return f"""
<h3>나. 유즈케이스</h3>
<p class="plain-text">고객과 운영자가 직접 수행하는 유즈케이스는 프로세스 정의 대상으로 관리한다.<br/>BSS와 연계 시스템의 조회·검증·저장 처리는 고객 또는 운영자 프로세스를 지원하는 보조 유즈케이스로 관리한다.</p>
<table class="usecase-list-table">
<thead>{tr(th("유즈케이스 ID", style="width: 150px;"), th("액터", style="width: 140px;"), th("유즈케이스명", style="width: 190px;"), th("설명"), th("프로세스 정의 대상", style="width: 110px;"))}</thead>
<tbody>{''.join(usecase_rows)}</tbody>
</table>
"""


def render_usecase_diagram(spec: dict) -> str:
    return f"""
<h3>다. 유즈케이스 다이어그램</h3>
<p class="plain-text">샘플 정책서의 UML Use Case Diagram 표기 기준에 따라 액터, 시스템 경계, 유즈케이스, association 관계로 표현한다.</p>
{build_usecase_static_diagram(spec)}
"""


def render_states(spec: dict) -> str:
    usecase_names = {item.get("id", ""): item.get("name", "") for item in spec.get("usecases", [])}
    state_names = {
        str(item.get("id", "")).strip(): str(item.get("name", "")).strip()
        for item in spec.get("states", [])
        if isinstance(item, dict) and str(item.get("id", "")).strip() and str(item.get("name", "")).strip()
    }
    state_rows = [
        tr(td(esc(item.get("id", "")), "mono"), td(esc(item.get("name", ""))), td(esc(item.get("description", ""))), td(esc(item.get("next_action", ""))))
        for item in spec.get("states", [])
    ]
    transition_rows = [
        tr(
            td(state_reference_cell(item.get("current_state", ""), state_names)),
            td(state_transition_event_cell(item, usecase_names)),
            td(state_reference_cell(item.get("next_state", ""), state_names)),
            td(esc(item.get("criteria", ""))),
        )
        for item in spec.get("state_transitions", [])
    ]
    return f"""
<h3>라. 상태 전이표</h3>
<p class="plain-text">본 장은 주요 상태와 상태 전이 기준을 정의한다.<br/>상태 전이표에서 사용하는 상태명은 상태 코드 목록의 상태명과 일치해야 한다.</p>
<h4>1) 상태 코드</h4>
<table class="state-code-table">
<thead>{tr(th("상태 코드", style="width: 160px;"), th("상태명", style="width: 150px;"), th("정의"), th("대표 후속 처리", style="width: 230px;"))}</thead>
<tbody>{''.join(state_rows)}</tbody>
</table>
<h4>2) 상태 전이 기준</h4>
<table class="state-transition-table">
<thead>{tr(th("현재 상태", style="width: 150px;"), th("전이 이벤트", style="width: 180px;"), th("다음 상태", style="width: 150px;"), th("처리 기준 및 후속 처리"))}</thead>
<tbody>{''.join(transition_rows)}</tbody>
		</table>
		<h4>3) 상태 전이 다이어그램</h4>
		<p class="plain-text">상태 전이 다이어그램은 대표 상태와 전이 이벤트를 개념적으로 보여주며, 상세 판정 기준은 상태 전이표를 따른다.</p>
		{render_state_mermaid_diagram(spec)}
		"""


def render_state_mermaid_diagram(spec: dict) -> str:
    # 상태 전이는 문서 검토 핵심 영역이라 외부 Mermaid 런타임에 의존하지 않고
    # 다운로드 HTML과 file:// 미리보기에서도 항상 보이는 정적 SVG를 우선 사용한다.
    return build_state_static_diagram(spec)


def render_processes(spec: dict, template_type: str = "simple") -> str:
    grouped = defaultdict(list)
    usecase_names = {item.get("id", ""): item.get("name", "") for item in spec.get("usecases", [])}
    function_names = {item.get("id", ""): item.get("name", "") for item in spec.get("functions", [])}
    policy_names = {item.get("id", ""): item.get("name", "") for item in spec.get("policy_groups", [])}
    for process in spec.get("processes", []):
        grouped[process.get("usecase_id", "")].append(process)

    blocks = []
    for index, (usecase_id, rows) in enumerate(grouped.items(), 1):
        table_rows = []
        for process in rows:
            table_rows.append(
                tr(
                    td(esc(process.get("id", "")), "mono"),
                    td(esc(process.get("name", ""))),
                    td(esc(process.get("description", ""))),
                    td(join_reference_lines(process.get("related_functions", []), function_names)),
                    td(join_reference_lines(process.get("related_policies", []), policy_names)),
                )
            )
        blocks.append(f"""
<h4>{index}) {heading_with_id(usecase_names.get(usecase_id, usecase_id), usecase_id)}</h4>
<table class="process-list-table">
<thead>{tr(th("프로세스 ID", style="width: 150px;"), th("프로세스명", style="width: 170px;"), th("설명"), th("관련 기능", style="width: 230px;"), th("관련 정책", style="width: 260px;"))}</thead>
<tbody>{''.join(table_rows)}</tbody>
</table>
""")
    if template_type == "full":
        detail = render_process_details(spec)
        flow_heading = "다. 전체 업무 흐름도"
    else:
        detail = ""
        flow_heading = "나. 전체 업무 흐름도"

    return f"""
<h2>4. 프로세스 정의</h2>
<h3>가. 프로세스 목록</h3>
<p class="plain-text">프로세스는 고객 또는 운영자가 경험하는 순서대로 작성한다.<br/>관련 기능은 기능 정의 작성 후 기능 ID·기능명으로 연결하고, 관련 정책은 정책 정의 작성 후 정책 ID·정책명으로 연결한다.</p>
{''.join(blocks)}
	{detail}
	<h3>{flow_heading}</h3>
	<p class="plain-text">전체 업무 흐름도는 유즈케이스별 시작, 주요 처리, 결과 확정, 종료 흐름을 시각적으로 요약한다.<br/>상세 진입 조건, 예외, 정책 값은 프로세스 목록과 정책 정의를 따른다.</p>
	{render_process_bpmn_viewer(spec)}
	"""


def render_process_bpmn_viewer(spec: dict) -> str:
    xml = build_bpmn_xml(spec)
    source_id = "bpmn-process-xml"
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    topic_slug = re.sub(r"\s+", "", str(meta.get("topic", "process")).strip())
    topic_slug = re.sub(r"[^\w가-힣]", "", topic_slug, flags=re.UNICODE) or "process"
    template_label = "Full" if "full" in str(meta.get("document_type", "")).casefold() else "간소화"
    version = str(meta.get("version", "v0.10")).strip() or "v0.10"
    file_name = f"NC_{topic_slug}_정책서_{template_label}_{version}_전체업무흐름도.bpmn"
    payload = json.dumps({"xml": xml}, ensure_ascii=False).replace("</", "<\\/")
    return f"""
<div class="bpmn-viewer-wrap">
<div class="bpmn-viewer-head">
<div class="bpmn-viewer-title">BPMN 2.0 Process Diagram</div>
<a class="bpmn-download-button" href="{esc(file_name)}" download="{esc(file_name)}">BPMN XML 다운로드</a>
</div>
<div class="bpmn-viewer" data-bpmn-source-id="{source_id}" data-bpmn-viewer="true"></div>
<script id="{source_id}" type="application/json">{payload}</script>
<div class="bpmn-fallback">{build_process_static_diagram(spec)}</div>
</div>
"""


def render_process_details(spec: dict) -> str:
    usecases = {item.get("id", ""): item for item in spec.get("usecases", [])}
    details_by_process = {
        str(item.get("process_id", "")).strip(): item
        for item in spec.get("process_details", [])
        if isinstance(item, dict) and str(item.get("process_id", "")).strip()
    }
    detail_blocks = []
    for index, process in enumerate(spec.get("processes", []), 1):
        usecase = usecases.get(process.get("usecase_id", ""), {})
        detail = details_by_process.get(str(process.get("id", "")).strip(), {})
        entry_condition = detail.get("entry_condition") or f"{esc(process.get('name', ''))}를 수행할 고객 상태와 선행 검증 조건이 충족된 경우 진입한다."
        exit_condition = detail.get("exit_condition") or f"{esc(process.get('name', ''))} 처리 결과가 성공, 실패, 보류, 제한 중 하나로 확정되고 고객 안내와 이력이 저장된 경우 종료한다."
        previous_processes = detail.get("previous_processes") if isinstance(detail.get("previous_processes"), list) else ["동일 유즈케이스의 직전 프로세스 또는 업무 진입 조건"]
        next_processes = detail.get("next_processes") if isinstance(detail.get("next_processes"), list) else ["동일 유즈케이스의 다음 프로세스 또는 결과 안내"]
        related_functions = detail.get("related_functions") if isinstance(detail.get("related_functions"), list) else process.get("related_functions", [])
        related_policies = detail.get("related_policies") if isinstance(detail.get("related_policies"), list) else process.get("related_policies", [])
        detail_blocks.append(f"""
<h4>{index}) {heading_with_id(process.get("name", ""), process.get("id", ""))}</h4>
<table>
<thead>
<tr>
<th style="width: 190px;">항목</th>
<th>내용</th>
</tr>
</thead>
<tbody>
{tr(td("프로세스 ID"), td(esc(process.get("id", "")), "mono"))}
{tr(td("프로세스명"), td(esc(process.get("name", ""))))}
{tr(td("설명"), td(esc(process.get("description", ""))))}
{tr(td("액터"), td(esc(usecase.get("actor", ""))))}
{tr(td("진입 조건"), td(esc(entry_condition)))}
{tr(td("종료 조건"), td(esc(exit_condition)))}
{tr(td("선행 프로세스"), td(join_lines(previous_processes)))}
{tr(td("후행 프로세스"), td(join_lines(next_processes)))}
{tr(td("관련 기능"), td(join_lines(related_functions)))}
{tr(td("관련 정책"), td(join_lines(related_policies)))}
</tbody>
</table>
""")
    return f"""
<h3>나. 프로세스 상세</h3>
<p class="plain-text">프로세스 상세는 각 프로세스의 진입 조건, 종료 조건, 선행·후행 관계, 관련 기능, 관련 정책 목록을 정의한다.<br/>진입과 종료 기준이 분명해야 상세 설계와 테스트 케이스를 도출할 수 있다.</p>
{''.join(detail_blocks)}
"""


def render_mermaid_block(
    code: str,
    caption: str = "",
    class_name: str = "",
    fallback_text: str = "",
    fallback_html: str = "",
) -> str:
    caption_html = f'<div class="diagram-caption">{esc(caption)}</div>' if caption else ""
    class_attr = f" mermaid-diagram{f' {class_name}' if class_name else ''}"
    fallback = (
        f'<div class="diagram-fallback-html">{fallback_html}</div>'
        if fallback_html
        else (f'<pre class="diagram-fallback">{html.escape(fallback_text, quote=False)}</pre>' if fallback_text else "")
    )
    return f'<div class="diagram-wrap{class_attr}">{caption_html}<pre class="mermaid">{html.escape(code, quote=False)}</pre></div>{fallback}'


def build_usecase_static_diagram(spec: dict) -> str:
    usecases = [item for item in spec.get("usecases", []) if isinstance(item, dict)]
    actor_names = []
    for actor in spec.get("actors", []):
        name = str(actor.get("name", "")).strip()
        if name and name not in actor_names:
            actor_names.append(name)
    for usecase in usecases:
        name = str(usecase.get("actor", "")).strip()
        if name and name not in actor_names:
            actor_names.append(name)
    topic_label = spec.get("meta", {}).get("topic_display") or spec.get("meta", {}).get("topic", "통합채널")
    return build_usecase_static_diagram_from_data(actor_names, usecases, topic_label)


def build_usecase_static_diagram_from_data(actor_names: Sequence[str], usecases: Sequence[dict], topic: object = "통합채널") -> str:
    if not actor_names or not usecases:
        return static_empty_diagram("UML 2.0 Use Case Diagram", "작성된 액터 또는 유즈케이스가 없습니다.")

    actor_order = []
    for name in actor_names:
        text = str(name).strip()
        if text and text not in actor_order:
            actor_order.append(text)
    for item in usecases:
        text = str(item.get("actor", "")).strip()
        if text and text not in actor_order:
            actor_order.append(text)
    if not actor_order:
        return static_empty_diagram("UML 2.0 Use Case Diagram", "액터와 유즈케이스 연결 정보가 없습니다.")

    usecase_count = len(usecases)
    gap = 72 if usecase_count <= 10 else 64
    diagram_height = max(520, 115 + max(0, usecase_count - 1) * gap + 120, max(1, len(actor_order)) * 132 + 110)
    boundary_y = 36
    boundary_height = diagram_height - 82
    usecase_x = 560
    usecase_rx = 118
    usecase_ry = 31

    human_actors = [name for name in actor_order if not is_system_actor_name(name)]
    system_actors = [name for name in actor_order if is_system_actor_name(name)]
    if not human_actors:
        midpoint = max(1, len(actor_order) // 2)
        human_actors = actor_order[:midpoint]
        system_actors = actor_order[midpoint:]

    actor_positions: Dict[str, tuple[int, int, str]] = {}
    for name, y in zip(human_actors, svg_even_positions(len(human_actors), 120, diagram_height - 170)):
        actor_positions[name] = (112, y, "left")
    for name, y in zip(system_actors, svg_even_positions(len(system_actors), 120, diagram_height - 170)):
        actor_positions[name] = (1008, y, "right")

    usecase_positions = []
    for index, item in enumerate(usecases):
        usecase_positions.append((usecase_x, 115 + index * gap, item))

    connections = []
    for x, y, item in usecase_positions:
        actor_name = str(item.get("actor", "")).strip()
        actor_position = actor_positions.get(actor_name)
        if not actor_position:
            continue
        actor_x, actor_y, side = actor_position
        actor_anchor_y = actor_y + 52
        if side == "right":
            connections.append(f'<line class="conn" x1="{x + usecase_rx}" x2="{actor_x - 32}" y1="{y}" y2="{actor_anchor_y}"></line>')
        else:
            connections.append(f'<line class="conn" x1="{actor_x + 32}" x2="{x - usecase_rx}" y1="{actor_anchor_y}" y2="{y}"></line>')

    actor_shapes = [
        draw_svg_actor(x, y, name, "system" if side == "right" and is_system_actor_name(name) else "human")
        for name, (x, y, side) in actor_positions.items()
    ]

    usecase_shapes = []
    for x, y, item in usecase_positions:
        name = str(item.get("name", "") or item.get("id", "")).strip()
        usecase_id = str(item.get("id", "") or "").strip()
        process_target = str(item.get("process_target", "") or "").strip()
        note = f"{usecase_id} · 프로세스 {process_target}" if process_target else usecase_id
        usecase_shapes.append(
            f'<ellipse class="uc" cx="{x}" cy="{y}" rx="{usecase_rx}" ry="{usecase_ry}"></ellipse>'
            + svg_text_lines(name, x, y - 3, "uc-text", max_chars=16, max_lines=2, line_height=14)
            + (f'<text class="uc-sub" text-anchor="middle" x="{x}" y="{y + 22}">{esc(note)}</text>' if note else "")
        )

    return (
        '<div class="diagram-wrap uml-usecase-diagram">'
        f'<svg aria-label="{html.escape(str(topic), quote=True)} 유즈케이스 다이어그램" height="{diagram_height}" role="img" '
        f'viewBox="0 0 1120 {diagram_height}" width="1120" xmlns="http://www.w3.org/2000/svg">'
        '<defs>'
        '<style>'
        ".sysbox { fill:#ffffff; stroke:#c6cfdb; stroke-width:1.5; }"
        ".actor-line { stroke:#4f5b6a; stroke-width:2; fill:none; }"
        ".system-actor-line { stroke:#64748b; stroke-width:2; fill:none; }"
        ".actor-text { font:14px Arial, 'Malgun Gothic', sans-serif; fill:#222; font-weight:700; }"
        ".title { font:700 15px Arial, 'Malgun Gothic', sans-serif; fill:#222; }"
        ".uc { fill:#f7f9fc; stroke:#8fa3bf; stroke-width:1.5; }"
        ".uc-text { font:700 13px Arial, 'Malgun Gothic', sans-serif; fill:#1f2937; }"
        ".uc-sub { font:11px 'Courier New', 'Malgun Gothic', monospace; fill:#667085; }"
        ".conn { stroke:#8a94a6; stroke-width:1.4; fill:none; }"
        ".legend { font:12px Arial, 'Malgun Gothic', sans-serif; fill:#5b6472; }"
        '</style>'
        '</defs>'
        f'<rect class="sysbox" height="{boundary_height}" rx="12" ry="12" width="540" x="290" y="{boundary_y}"></rect>'
        f'<text class="title" text-anchor="middle" x="560" y="{boundary_y + 25}">{esc(topic)} 업무 시스템</text>'
        f'{"".join(connections)}'
        f'{"".join(usecase_shapes)}'
        f'{"".join(actor_shapes)}'
        '<text class="legend" x="304" y="'
        f'{diagram_height - 26}">※ 화면 이동·버튼 클릭은 제외하고, 액터가 완결하는 업무와 시스템 보조 처리를 연결합니다.</text>'
        '</svg>'
        "</div>"
    )


def build_state_static_diagram(spec: dict) -> str:
    transitions = [item for item in spec.get("state_transitions", []) if isinstance(item, dict)]
    if not transitions:
        states = [item for item in spec.get("states", []) if isinstance(item, dict)]
        if not states:
            return static_empty_diagram("State Transition Diagram", "작성된 상태 또는 상태 전이가 없습니다.")
        columns = 3
        rows = (len(states) + columns - 1) // columns
        diagram_height = max(260, 92 + rows * 92)
        cards = []
        for index, item in enumerate(states):
            col = index % columns
            row = index // columns
            x = 92 + col * 330
            y = 96 + row * 88
            label = compact_label(item.get("id", ""), item.get("name", ""))
            cards.append(
                f'<rect class="state" height="54" rx="12" ry="12" width="250" x="{x}" y="{y}"></rect>'
                + svg_text_lines(label, x + 125, y + 32, "state-text", max_chars=22, max_lines=2, line_height=14)
            )
        return (
            '<div class="diagram-wrap state-transition-diagram">'
            f'<svg aria-label="상태 전이 다이어그램" height="{diagram_height}" role="img" '
            f'viewBox="0 0 1120 {diagram_height}" width="1120" xmlns="http://www.w3.org/2000/svg">'
            '<defs><style>'
            ".boundary { fill:#ffffff; stroke:#c6cfdb; stroke-width:1.5; }"
            ".d-title { font:700 15px Arial, 'Malgun Gothic', sans-serif; fill:#222; }"
            ".state { fill:#f7f9fc; stroke:#8fa3bf; stroke-width:1.6; }"
            ".state-text { font:700 13px Arial, 'Malgun Gothic', sans-serif; fill:#1f2937; }"
            '</style></defs>'
            f'<rect class="boundary" height="{diagram_height - 42}" rx="12" ry="12" width="1060" x="30" y="20"></rect>'
            '<text class="d-title" x="56" y="54">상태 코드 개요</text>'
            f'{"".join(cards)}'
            '</svg></div>'
        )

    state_meta = {
        str(item.get("name", "")).strip(): str(item.get("id", "")).strip()
        for item in spec.get("states", [])
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    }
    state_name_by_id = {
        str(item.get("id", "")).strip(): str(item.get("name", "")).strip()
        for item in spec.get("states", [])
        if isinstance(item, dict) and str(item.get("id", "")).strip() and str(item.get("name", "")).strip()
    }

    def resolve_state_name(value: object) -> str:
        raw = str(value or "").strip()
        return state_name_by_id.get(raw, raw)

    state_names: List[str] = []
    for transition in transitions:
        for key in ("current_state", "next_state"):
            name = resolve_state_name(transition.get(key, ""))
            if name and name not in state_names:
                state_names.append(name)
    for item in spec.get("states", []):
        name = str(item.get("name", "")).strip() if isinstance(item, dict) else ""
        if name and name not in state_names:
            state_names.append(name)

    outgoing: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, list[str]] = defaultdict(list)
    for transition in transitions:
        current = resolve_state_name(transition.get("current_state", ""))
        next_state = resolve_state_name(transition.get("next_state", ""))
        if current and next_state and next_state not in outgoing[current]:
            outgoing[current].append(next_state)
        if current and next_state and current not in incoming[next_state]:
            incoming[next_state].append(current)

    main_path: list[str] = []
    start_candidates = [name for name in state_names if outgoing.get(name) and not incoming.get(name)]
    current = start_candidates[0] if start_candidates else resolve_state_name(transitions[0].get("current_state", ""))
    while current and current not in main_path:
        main_path.append(current)
        candidates = [
            name
            for name in outgoing.get(current, [])
            if name not in main_path and not is_alert_state_name(name)
        ]
        if not candidates:
            break
        current = candidates[0]
    if len(main_path) == 1 and transitions:
        first_next = resolve_state_name(transitions[0].get("next_state", ""))
        if first_next and first_next not in main_path:
            main_path.append(first_next)

    main_edge_pairs = list(zip(main_path, main_path[1:]))
    main_edges = set(main_edge_pairs)
    main_transitions = []
    for current_name, next_name in main_edge_pairs:
        for transition in transitions:
            if (
                resolve_state_name(transition.get("current_state", "")) == current_name
                and resolve_state_name(transition.get("next_state", "")) == next_name
            ):
                main_transitions.append(transition)
                break
    secondary_transitions = [
        transition
        for transition in transitions
        if (
            resolve_state_name(transition.get("current_state", "")),
            resolve_state_name(transition.get("next_state", "")),
        )
        not in main_edges
    ]

    branch_states: list[str] = []
    for transition in secondary_transitions:
        for key in ("current_state", "next_state"):
            name = resolve_state_name(transition.get(key, ""))
            if name and name not in main_path and name not in branch_states:
                branch_states.append(name)
    for name in state_names:
        if name and name not in main_path and name not in branch_states:
            branch_states.append(name)

    branch_cols = min(4, max(1, len(branch_states)))
    branch_rows = (len(branch_states) + branch_cols - 1) // branch_cols if branch_states else 0
    branch_start_y = 316
    branch_row_gap = 154
    diagram_height = max(520, branch_start_y + max(1, branch_rows) * branch_row_gap + 84)
    boundary_y = 28
    boundary_h = diagram_height - 78
    main_step = 780 / max(1, len(main_path) - 1)
    node_w = 150 if len(main_path) <= 5 else max(108, min(136, int(main_step - 24)))
    node_h = 64

    positions: dict[str, tuple[float, float]] = {}
    state_nodes: list[str] = []
    edge_paths: list[str] = []
    edge_labels: list[str] = []

    def node_label(name: str) -> str:
        state_id = state_meta.get(name, "")
        return (
            svg_text_lines(name, int(positions[name][0]), int(positions[name][1] - 6), "state-text", max_chars=11, max_lines=1, line_height=14)
            + (
                svg_text_lines(state_id, int(positions[name][0]), int(positions[name][1] + 17), "state-sub", max_chars=22, max_lines=1, line_height=12)
                if state_id
                else ""
            )
        )

    def label_box(text: object, x: float, y: float, *, max_chars: int = 14, max_lines: int = 2) -> str:
        lines = wrap_svg_text(text, max_chars=max_chars, max_lines=max_lines)
        if not lines:
            return ""
        line_height = 14
        width = max(74, min(210, max(len(line) for line in lines) * 7 + 22))
        height = len(lines) * line_height + 10
        rect_x = x - width / 2
        rect_y = y - height + 4
        text_y = rect_y + 17
        return (
            f'<rect class="flow-label-bg" height="{height}" rx="8" ry="8" width="{width}" x="{rect_x:.1f}" y="{rect_y:.1f}"></rect>'
            + "".join(
                f'<text class="flow-label" text-anchor="middle" x="{x:.1f}" y="{text_y + index * line_height:.1f}">{esc(line)}</text>'
                for index, line in enumerate(lines)
            )
        )

    def endpoint(source: str, target: str) -> tuple[float, float, float, float]:
        sx, sy = positions[source]
        tx, ty = positions[target]
        if source == target:
            return sx + node_w / 2, sy, tx + node_w / 2, ty
        if abs(tx - sx) >= abs(ty - sy):
            if tx >= sx:
                return sx + node_w / 2, sy, tx - node_w / 2, ty
            return sx - node_w / 2, sy, tx + node_w / 2, ty
        if ty >= sy:
            return sx, sy + node_h / 2, tx, ty - node_h / 2
        return sx, sy - node_h / 2, tx, ty + node_h / 2

    for index, name in enumerate(main_path):
        cx = distributed_x(index, len(main_path), 170, 950)
        cy = 134
        positions[name] = (cx, cy)
        state_class = state_node_class(name, name in main_path and name in (main_path[:1] + main_path[-1:]))
        state_nodes.append(
            f'<rect class="{state_class}" height="{node_h}" rx="29" ry="29" width="{node_w}" x="{cx - node_w / 2:.1f}" y="{cy - node_h / 2:.1f}"></rect>'
            + node_label(name)
        )

    for index, name in enumerate(branch_states):
        row = index // branch_cols
        col = index % branch_cols
        items_in_row = min(branch_cols, len(branch_states) - row * branch_cols)
        cx = distributed_x(col, items_in_row, 180, 940)
        cy = branch_start_y + row * branch_row_gap
        positions[name] = (cx, cy)
        state_class = state_node_class(name)
        state_nodes.append(
            f'<rect class="{state_class}" height="{node_h}" rx="29" ry="29" width="{node_w}" x="{cx - node_w / 2:.1f}" y="{cy - node_h / 2:.1f}"></rect>'
            + node_label(name)
        )

    for transition_index, transition in enumerate(transitions):
        current = resolve_state_name(transition.get("current_state", ""))
        next_state = resolve_state_name(transition.get("next_state", ""))
        event = str(transition.get("event", "")).strip()
        if current not in positions or next_state not in positions:
            continue
        sx, sy, tx, ty = endpoint(current, next_state)
        source_cx, source_cy = positions[current]
        target_cx, target_cy = positions[next_state]
        is_main = (current, next_state) in main_edges
        edge_class = "flow" if is_main else "flow-dash"
        if current == next_state:
            loop_x = source_cx + node_w / 2
            edge_paths.append(
                f'<path class="{edge_class}" d="M{loop_x:.1f} {source_cy:.1f} C{loop_x + 72:.1f} {source_cy - 62:.1f}, {loop_x + 72:.1f} {source_cy + 62:.1f}, {loop_x:.1f} {source_cy + 8:.1f}"></path>'
            )
            edge_labels.append(label_box(event, loop_x + 62, source_cy - 52))
            continue
        if abs(target_cy - source_cy) < 4:
            if is_main:
                edge_paths.append(f'<line class="{edge_class}" x1="{sx:.1f}" x2="{tx:.1f}" y1="{sy:.1f}" y2="{ty:.1f}"></line>')
                edge_labels.append(label_box(event, (sx + tx) / 2, sy - 40, max_chars=12))
            else:
                bend = -72 if source_cy > 220 else 72
                control_y = source_cy + bend
                edge_paths.append(
                    f'<path class="{edge_class}" d="M{sx:.1f} {sy:.1f} C{(sx + tx) / 2:.1f} {control_y:.1f}, {(sx + tx) / 2:.1f} {control_y:.1f}, {tx:.1f} {ty:.1f}"></path>'
                )
                edge_labels.append(label_box(event, (sx + tx) / 2, control_y - 8 if bend < 0 else control_y + 28, max_chars=12))
            continue
        vertical_gap = target_cy - source_cy
        c1y = sy + (70 if vertical_gap > 0 else -70)
        c2y = ty - (70 if vertical_gap > 0 else -70)
        edge_paths.append(f'<path class="{edge_class}" d="M{sx:.1f} {sy:.1f} C{sx:.1f} {c1y:.1f}, {tx:.1f} {c2y:.1f}, {tx:.1f} {ty:.1f}"></path>')
        label_x = (source_cx + target_cx) / 2
        label_y = (source_cy + target_cy) / 2 - 8
        if not is_main:
            label_y += 18 if transition_index % 2 else -18
        edge_labels.append(label_box(event, label_x, label_y, max_chars=13))

    return (
        '<div class="diagram-wrap state-transition-diagram">'
        f'<svg aria-label="상태 전이 다이어그램" height="{diagram_height}" role="img" '
        f'viewBox="0 0 1120 {diagram_height}" width="1120" xmlns="http://www.w3.org/2000/svg">'
        '<defs>'
        '<marker id="state-arrow" markerHeight="8" markerWidth="8" orient="auto" refX="7" refY="4" viewBox="0 0 8 8">'
        '<path d="M0,0 L8,4 L0,8 z" fill="#7b8798"></path></marker>'
        '<style>'
        ".boundary { fill:#ffffff; stroke:#c6cfdb; stroke-width:1.5; }"
        ".d-title { font:700 15px Arial, 'Malgun Gothic', sans-serif; fill:#222; }"
        ".state { fill:#f7f9fc; stroke:#8fa3bf; stroke-width:1.6; }"
        ".state-major { fill:#eef5ff; stroke:#6f8fb8; stroke-width:1.8; }"
        ".state-alert { fill:#fff5f5; stroke:#d69a9a; stroke-width:1.6; }"
        ".state-text { font:700 13px Arial, 'Malgun Gothic', sans-serif; fill:#1f2937; }"
        ".state-sub { font:12px Arial, 'Malgun Gothic', sans-serif; fill:#4b5563; }"
        ".flow { stroke:#7b8798; stroke-width:1.5; fill:none; marker-end:url(#state-arrow); }"
        ".flow-dash { stroke:#9aa5b5; stroke-width:1.4; fill:none; stroke-dasharray:6 5; marker-end:url(#state-arrow); }"
        ".flow-label { font:12px Arial, 'Malgun Gothic', sans-serif; fill:#4b5563; }"
        ".flow-label-bg { fill:#ffffff; stroke:#e5edf7; stroke-width:1; opacity:.96; }"
        ".note { font:12px Arial, 'Malgun Gothic', sans-serif; fill:#6b7280; }"
        '</style></defs>'
        f'<rect class="boundary" height="{boundary_h}" rx="12" ry="12" width="1040" x="40" y="{boundary_y}"></rect>'
        '<text class="d-title" text-anchor="middle" x="560" y="56">상태 전이</text>'
        f'{"".join(edge_paths)}'
        f'{"".join(state_nodes)}'
        f'{"".join(edge_labels)}'
        f'<text class="note" x="78" y="{diagram_height - 54}">실선은 대표 흐름, 점선은 예외·복구·제한 흐름을 의미합니다.</text>'
        '</svg></div>'
    )


def build_process_static_diagram(spec: dict) -> str:
    processes = [item for item in spec.get("processes", []) if isinstance(item, dict)]
    if not processes:
        return static_empty_diagram("BPMN 2.0 Process Diagram", "작성된 프로세스가 없습니다.")

    usecase_names = {str(item.get("id", "")).strip(): str(item.get("name", "")).strip() for item in spec.get("usecases", []) if isinstance(item, dict)}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for process in processes:
        grouped[str(process.get("usecase_id", "")).strip()].append(process)

    groups: List[tuple[str, list[dict], int]] = []
    for usecase_id, rows in grouped.items():
        # Keep a usecase lane as one left-to-right BPMN sequence. Wrapping task
        # nodes into a second row makes the return edge look like a backward
        # workflow and puts End in the middle of the lane.
        groups.append((usecase_id, rows, 150))

    task_width = 160
    task_half = task_width // 2
    task_gap = 185
    first_task_x = 410
    start_x = 300
    start_r = 17
    max_process_count = max((len(rows) for _, rows, _ in groups), default=1)
    last_task_x = first_task_x + max(0, max_process_count - 1) * task_gap
    diagram_width = max(1120, last_task_x + task_half + 132)
    pool_width = diagram_width - 60
    diagram_height = 44 + sum(group_height + 18 for _, _, group_height in groups)
    blocks = []
    y_cursor = 32
    for group_index, (usecase_id, rows, group_height) in enumerate(groups, 1):
        label = compact_label(usecase_id, usecase_names.get(usecase_id, "유즈케이스 미지정"))
        pool_y = y_cursor
        pool_h = group_height
        blocks.append(
            f'<rect class="pool" height="{pool_h}" rx="14" ry="14" width="{pool_width}" x="30" y="{pool_y}"></rect>'
            f'<rect class="pool-head" height="{pool_h}" rx="14" ry="14" width="230" x="30" y="{pool_y}"></rect>'
            f'<text class="pool-index" x="58" y="{pool_y + 32}">{group_index:02d}</text>'
            + svg_text_lines(label, 145, pool_y + 61, "pool-title", max_chars=15, max_lines=4, line_height=16)
        )
        first_y = pool_y + 76
        blocks.append(f'<circle class="start" cx="{start_x}" cy="{first_y}" r="{start_r}"></circle>')
        blocks.append(f'<text class="start-text" text-anchor="middle" x="{start_x}" y="{first_y + 4}">Start</text>')
        previous: tuple[int, int] | None = None
        for index, process in enumerate(rows):
            x = first_task_x + index * task_gap
            y = first_y
            task_class = "task-key" if index == 0 or index == len(rows) - 1 else "task"
            label_text = compact_label(process.get("id", ""), process.get("name", ""))
            blocks.append(f'<rect class="{task_class}" height="66" rx="12" ry="12" width="{task_width}" x="{x - task_half}" y="{y - 33}"></rect>')
            process_id = str(process.get("id", "")).strip()
            process_name = str(process.get("name", "")).strip()
            if process_id:
                blocks.append(svg_text_lines(process_id, x, y - 12, "task-text", max_chars=28, max_lines=1, line_height=14))
            blocks.append(svg_text_lines(process_name or label_text, x, y + 11, "task-text", max_chars=15, max_lines=2, line_height=14))
            if previous is None:
                blocks.append(f'<line class="flow" marker-end="url(#bpmn-arrow)" x1="{start_x + start_r}" x2="{x - task_half - 6}" y1="{first_y}" y2="{y}"></line>')
            else:
                prev_x, prev_y = previous
                blocks.append(f'<line class="flow" marker-end="url(#bpmn-arrow)" x1="{prev_x + task_half + 4}" x2="{x - task_half - 6}" y1="{prev_y}" y2="{y}"></line>')
            previous = (x, y)
        if previous:
            last_x, last_y = previous
            end_x = last_x + task_half + 58
            blocks.append(f'<line class="flow" marker-end="url(#bpmn-arrow)" x1="{last_x + task_half + 4}" x2="{end_x - 21}" y1="{last_y}" y2="{last_y}"></line>')
            blocks.append(f'<circle class="end" cx="{end_x}" cy="{last_y}" r="17"></circle>')
            blocks.append(f'<text class="start-text" text-anchor="middle" x="{end_x}" y="{last_y + 4}">End</text>')
        y_cursor += pool_h + 18
    return (
        '<div class="diagram-wrap bpmn-process-diagram">'
        f'<svg aria-label="전체 업무 흐름도 BPMN" height="{diagram_height}" role="img" '
        f'viewBox="0 0 {diagram_width} {diagram_height}" width="{diagram_width}" xmlns="http://www.w3.org/2000/svg">'
        '<defs>'
        '<marker id="bpmn-arrow" markerHeight="10" markerWidth="10" orient="auto" refX="9" refY="5" viewBox="0 0 10 10">'
        '<path d="M0,0 L10,5 L0,10 z" fill="#667085"></path></marker>'
        '<style>'
        ".pool{fill:#fff;stroke:#cfd8e3;stroke-width:1.4;}"
        ".pool-head{fill:#eef3f8;stroke:#cfd8e3;stroke-width:1.4;}"
        ".pool-index{font:700 13px Arial, 'Malgun Gothic', sans-serif;fill:#3b82f6;}"
        ".pool-title{font:700 13px Arial, 'Malgun Gothic', sans-serif;fill:#1f2937;}"
        ".task{fill:#f8fafc;stroke:#94a3b8;stroke-width:1.3;}"
        ".task-key{fill:#eef5ff;stroke:#6f8fb8;stroke-width:1.5;}"
        ".task-text{font:700 12px Arial, 'Malgun Gothic', sans-serif;fill:#1f2937;}"
        ".flow{stroke:#667085;stroke-width:1.35;fill:none;}"
        ".start{fill:#eaf7ef;stroke:#73b483;stroke-width:1.5;}"
        ".end{fill:#f4f4f5;stroke:#71717a;stroke-width:1.5;}"
        ".start-text{font:700 10px Arial, 'Malgun Gothic', sans-serif;fill:#374151;}"
        '</style></defs>'
        f'{"".join(blocks)}'
        '</svg></div>'
    )


def static_empty_diagram(title: str, message: str) -> str:
    return (
        '<div class="diagram-static">'
        f'<div class="diagram-static-title">{esc(title)}</div>'
        f'<div class="static-empty">{esc(message)}</div></div>'
    )


def svg_even_positions(count: int, start: int, end: int) -> List[int]:
    if count <= 0:
        return []
    if count == 1:
        return [(start + end) // 2]
    if end <= start:
        return [start for _ in range(count)]
    step = (end - start) / max(1, count - 1)
    return [int(start + step * index) for index in range(count)]


def draw_svg_actor(x: int, y: int, label: str, actor_type: str = "human") -> str:
    line_class = "system-actor-line" if actor_type == "system" else "actor-line"
    return (
        f'<circle class="{line_class}" cx="{x}" cy="{y}" r="18"></circle>'
        f'<line class="{line_class}" x1="{x}" x2="{x}" y1="{y + 18}" y2="{y + 65}"></line>'
        f'<line class="{line_class}" x1="{x - 26}" x2="{x + 26}" y1="{y + 35}" y2="{y + 35}"></line>'
        f'<line class="{line_class}" x1="{x}" x2="{x - 20}" y1="{y + 65}" y2="{y + 100}"></line>'
        f'<line class="{line_class}" x1="{x}" x2="{x + 20}" y1="{y + 65}" y2="{y + 100}"></line>'
        + svg_text_lines(label, x, y + 126, "actor-text", max_chars=11, max_lines=2, line_height=15)
    )


def svg_text_lines(
    text: object,
    x: int,
    y: int,
    class_name: str,
    *,
    max_chars: int = 14,
    max_lines: int = 2,
    line_height: int = 15,
    anchor: str = "middle",
) -> str:
    lines = wrap_svg_text(text, max_chars=max_chars, max_lines=max_lines)
    if not lines:
        return ""
    start_y = y - int((len(lines) - 1) * line_height / 2)
    return "".join(
        f'<text class="{class_name}" text-anchor="{anchor}" x="{x}" y="{start_y + index * line_height}">{esc(line)}</text>'
        for index, line in enumerate(lines)
    )


def wrap_svg_text(text: object, *, max_chars: int = 14, max_lines: int = 2) -> List[str]:
    value = esc(text)
    if not value:
        return []
    words = value.split()
    lines: List[str] = []
    current = ""
    if len(words) > 1:
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = word
        if current:
            lines.append(current)
    else:
        lines = [value[index : index + max_chars] for index in range(0, len(value), max_chars)]
    if len(lines) > max_lines:
        clipped = lines[:max_lines]
        clipped[-1] = clipped[-1][: max(1, max_chars - 1)].rstrip() + "…"
        return clipped
    return lines


def compact_label(*parts: object) -> str:
    return " ".join(str(part).strip() for part in parts if str(part).strip())


def distributed_x(index: int, count: int, start: int, end: int) -> float:
    if count <= 1:
        return (start + end) / 2
    if end <= start:
        return float(start)
    return start + ((end - start) * index / max(1, count - 1))


def is_alert_state_name(name: object) -> bool:
    text = str(name or "")
    alert_keywords = (
        "실패",
        "오류",
        "불가",
        "제한",
        "반려",
        "회수",
        "재검수",
        "보류",
        "만료",
        "탈퇴",
        "차단",
    )
    return any(keyword in text for keyword in alert_keywords)


def state_node_class(name: object, force_major: bool = False) -> str:
    text = str(name or "")
    major_keywords = ("완료", "정상", "승인", "배포 완료")
    if is_alert_state_name(text):
        return "state-alert"
    if force_major or any(keyword in text for keyword in major_keywords):
        return "state-major"
    return "state"


def build_usecase_text_diagram(spec: dict) -> str:
    diagram = spec.get("meta", {}).get("usecase_diagram", {}) if isinstance(spec.get("meta"), dict) else {}
    lines = diagram.get("lines", []) if isinstance(diagram, dict) else []
    clean_lines = [str(line).strip() for line in lines if str(line).strip()]
    if clean_lines:
        return "\n".join(clean_lines)

    generated_lines = []
    for usecase in spec.get("usecases", []):
        if not isinstance(usecase, dict):
            continue
        actor = str(usecase.get("actor", "")).strip() or "액터"
        name = str(usecase.get("name", "")).strip() or str(usecase.get("id", "")).strip()
        if not name:
            continue
        relation = "→" if usecase.get("process_target") == "Y" else "→ 지원:"
        generated_lines.append(f"[{actor}] {relation} ({name})")
    return "\n".join(generated_lines) or "작성된 액터 또는 유즈케이스가 없습니다."


def build_state_text_diagram(spec: dict) -> str:
    transitions = [item for item in spec.get("state_transitions", []) if isinstance(item, dict)]
    if transitions:
        lines = []
        for transition in transitions:
            usecase_ids = ", ".join(transition_usecase_ids_value(transition))
            prefix = f"[{usecase_ids}] " if usecase_ids else ""
            current = str(transition.get("current_state", "")).strip() or "현재 상태"
            event = str(transition.get("event", "")).strip() or "전이 이벤트"
            next_state = str(transition.get("next_state", "")).strip() or "다음 상태"
            criteria = str(transition.get("criteria", "")).strip()
            suffix = f" - {criteria}" if criteria else ""
            lines.append(f"{prefix}{current} → {event} → {next_state}{suffix}")
        return "\n".join(lines)

    states = [item for item in spec.get("states", []) if isinstance(item, dict)]
    if states:
        return "\n".join(
            f"{state.get('id', '')} {state.get('name', '')}".strip()
            for state in states
            if str(state.get("id", "")).strip() or str(state.get("name", "")).strip()
        )
    return "작성된 상태 또는 상태 전이가 없습니다."


def build_process_text_diagram(spec: dict) -> str:
    processes = [item for item in spec.get("processes", []) if isinstance(item, dict)]
    if not processes:
        return "작성된 프로세스가 없습니다."

    usecase_names = {str(item.get("id", "")).strip(): str(item.get("name", "")).strip() for item in spec.get("usecases", []) if isinstance(item, dict)}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for process in processes:
        grouped[str(process.get("usecase_id", "")).strip()].append(process)

    lines = []
    for usecase_id, rows in grouped.items():
        usecase_label = " ".join(part for part in (usecase_id, usecase_names.get(usecase_id, "")) if part).strip() or "유즈케이스 미지정"
        lines.append(f"[{usecase_label}]")
        for index, process in enumerate(rows, 1):
            process_label = " ".join(
                part
                for part in (str(process.get("id", "")).strip(), str(process.get("name", "")).strip())
                if part
            ).strip()
            related_functions = ", ".join(str(item) for item in process.get("related_functions", [])[:3])
            related_policies = ", ".join(str(item) for item in process.get("related_policies", [])[:3])
            refs = []
            if related_functions:
                refs.append(f"기능: {related_functions}")
            if related_policies:
                refs.append(f"정책: {related_policies}")
            suffix = f" ({' / '.join(refs)})" if refs else ""
            lines.append(f"  {index}. {process_label}{suffix}")
    return "\n".join(lines)


def build_usecase_mermaid(spec: dict) -> str:
    usecases = [item for item in spec.get("usecases", []) if isinstance(item, dict)]
    actor_names = []
    for actor in spec.get("actors", []):
        name = str(actor.get("name", "")).strip()
        if name and name not in actor_names:
            actor_names.append(name)
    for usecase in usecases:
        name = str(usecase.get("actor", "")).strip()
        if name and name not in actor_names:
            actor_names.append(name)
    topic_label = spec.get("meta", {}).get("topic_display") or spec.get("meta", {}).get("topic", "통합채널")
    return build_usecase_mermaid_from_data(actor_names, usecases, topic_label)


def build_usecase_mermaid_from_data(actor_names: Sequence[str], usecases: Sequence[dict], topic: object = "통합채널") -> str:
    if not actor_names or not usecases:
        return 'flowchart TD\n  EMPTY["UML 2.0 Use Case Diagram<br/>작성된 액터 또는 유즈케이스가 없습니다"]'

    actor_node_by_name = {name: f"A{index:02d}" for index, name in enumerate(actor_names, 1)}
    human_nodes = []
    system_nodes = []
    usecase_nodes = []
    lines = [
        "flowchart LR",
        "  %% UML 2.0 Use Case Diagram rendered with Mermaid",
        "  classDef actor fill:#fff7ed,stroke:#f97316,color:#7c2d12;",
        "  classDef systemActor fill:#f8fafc,stroke:#64748b,color:#334155;",
        "  classDef usecase fill:#eff6ff,stroke:#2563eb,color:#1e3a8a;",
        f'  subgraph SYSTEM["System Boundary: {mermaid_label(topic, max_chars=70)}"]',
        "    direction TB",
    ]
    for index, usecase in enumerate(usecases, 1):
        node_id = f"U{index:02d}"
        usecase_nodes.append(node_id)
        label = mermaid_multiline_label(usecase.get("id", ""), usecase.get("name", ""), max_chars=70)
        lines.append(f'    {node_id}(["{label}"])')
    lines.append("  end")

    for name, node_id in actor_node_by_name.items():
        label = mermaid_multiline_label("Actor", name, max_chars=44)
        lines.append(f'  {node_id}["{label}"]')
        if is_system_actor_name(name):
            system_nodes.append(node_id)
        else:
            human_nodes.append(node_id)

    for index, usecase in enumerate(usecases, 1):
        actor_node = actor_node_by_name.get(str(usecase.get("actor", "")).strip())
        if actor_node:
            lines.append(f"  {actor_node} --- U{index:02d}")

    if human_nodes:
        lines.append(f"  class {','.join(human_nodes)} actor;")
    if system_nodes:
        lines.append(f"  class {','.join(system_nodes)} systemActor;")
    if usecase_nodes:
        lines.append(f"  class {','.join(usecase_nodes)} usecase;")
    lines.append("  style SYSTEM fill:#f8fafc,stroke:#334155,stroke-width:1px,color:#0f172a")
    return "\n".join(lines)


def build_state_mermaid(spec: dict) -> str:
    states = list(spec.get("states", []))
    transitions = list(spec.get("state_transitions", []))
    state_name_by_id = {
        str(item.get("id", "")).strip(): str(item.get("name", "")).strip()
        for item in states
        if isinstance(item, dict) and str(item.get("id", "")).strip() and str(item.get("name", "")).strip()
    }

    def resolve_state_name(value: object) -> str:
        raw = str(value or "").strip()
        return state_name_by_id.get(raw, raw)

    state_records: list[tuple[str, str]] = []
    seen_state_names: set[str] = set()
    for state in states:
        if not isinstance(state, dict):
            continue
        state_id = str(state.get("id", "")).strip()
        state_name = str(state.get("name", "")).strip()
        if not state_name:
            continue
        state_records.append((state_id, state_name))
        seen_state_names.add(state_name)
    for transition in transitions:
        if not isinstance(transition, dict):
            continue
        for key in ("current_state", "next_state"):
            state_name = resolve_state_name(transition.get(key, ""))
            if state_name and state_name not in seen_state_names:
                state_records.append(("", state_name))
                seen_state_names.add(state_name)

    if not state_records:
        return 'stateDiagram-v2\n  [*] --> EMPTY\n  state "작성된 상태가 없습니다" as EMPTY'

    alias_by_name = {}
    alias_by_id = {}
    lines = ["stateDiagram-v2", "  direction LR"]
    alert_aliases = []
    major_aliases = []
    for index, (state_id, state_name) in enumerate(state_records, 1):
        alias = f"S{index:02d}"
        if state_id:
            alias_by_id[state_id] = alias
        alias_by_name[state_name] = alias
        label = mermaid_multiline_label(state_name, state_id, max_chars=48)
        lines.append(f'  state "{label}" as {alias}')
        if is_alert_state_name(state_name):
            alert_aliases.append(alias)
        elif any(keyword in state_name for keyword in ("완료", "정상", "승인")) or index == 1:
            major_aliases.append(alias)

    first_alias = "S01"
    lines.append(f"  [*] --> {first_alias}")
    rendered_transitions = 0
    for transition in transitions:
        raw_current = str(transition.get("current_state", "")).strip()
        raw_next = str(transition.get("next_state", "")).strip()
        current = resolve_state_name(raw_current)
        next_state = resolve_state_name(raw_next)
        current_alias = alias_by_name.get(current) or alias_by_id.get(raw_current)
        next_alias = alias_by_name.get(next_state) or alias_by_id.get(raw_next)
        if not current_alias or not next_alias:
            continue
        event = mermaid_label(transition.get("event", ""), max_chars=34)
        lines.append(f"  {current_alias} --> {next_alias} : {event}")
        rendered_transitions += 1

    if not rendered_transitions:
        for left, right in zip(range(1, len(states)), range(2, len(states) + 1)):
            lines.append(f"  S{left:02d} --> S{right:02d}")
    lines.extend(
        [
            "  classDef major fill:#eef5ff,stroke:#6f8fb8,color:#1f2937,stroke-width:1.8px",
            "  classDef alert fill:#fff5f5,stroke:#d69a9a,color:#1f2937,stroke-width:1.6px",
        ]
    )
    if major_aliases:
        lines.append(f"  class {','.join(major_aliases)} major")
    if alert_aliases:
        lines.append(f"  class {','.join(alert_aliases)} alert")
    return "\n".join(lines)


def build_process_mermaid(spec: dict) -> str:
    processes = list(spec.get("processes", []))
    if not processes:
        return 'flowchart TD\n  EMPTY["BPMN 2.0 Process Diagram<br/>작성된 프로세스가 없습니다"]'

    usecase_names = {item.get("id", ""): item.get("name", "") for item in spec.get("usecases", [])}
    grouped = defaultdict(list)
    for process in processes:
        grouped[process.get("usecase_id", "")].append(process)

    lines = [
        "flowchart LR",
        "  %% BPMN 2.0 Process Diagram rendered with Mermaid",
        "  classDef startEvent fill:#ffffff,stroke:#0f172a,stroke-width:2px,color:#0f172a;",
        "  classDef endEvent fill:#ffffff,stroke:#0f172a,stroke-width:4px,color:#0f172a;",
        "  classDef task fill:#ecfdf5,stroke:#059669,color:#064e3b;",
        "  classDef gateway fill:#fffbeb,stroke:#d97706,color:#92400e;",
        "  classDef exception fill:#fff1f2,stroke:#e11d48,color:#881337;",
    ]
    start_nodes = []
    end_nodes = []
    task_nodes = []
    gateway_nodes = []
    exception_nodes = []
    global_index = 1
    for group_index, (usecase_id, rows) in enumerate(grouped.items(), 1):
        lane_id = f"L{group_index:02d}"
        start_id = f"S{group_index:02d}"
        gateway_id = f"G{group_index:02d}"
        end_id = f"E{group_index:02d}"
        exception_id = f"X{group_index:02d}"
        start_nodes.append(start_id)
        gateway_nodes.append(gateway_id)
        end_nodes.append(end_id)
        exception_nodes.append(exception_id)
        usecase_label = mermaid_multiline_label("Lane", usecase_id, usecase_names.get(usecase_id, ""), max_chars=82)
        lines.append(f'  subgraph {lane_id}["{usecase_label}"]')
        lines.append("    direction LR")
        lines.append(f'    {start_id}((Start))')
        previous_node = start_id
        for process in rows:
            node_id = f"P{global_index:03d}"
            task_nodes.append(node_id)
            label = mermaid_multiline_label(process.get("id", ""), process.get("name", ""), max_chars=76)
            lines.append(f'    {node_id}["{label}"]')
            lines.append(f"    {previous_node} --> {node_id}")
            previous_node = node_id
            global_index += 1
        lines.append(f'    {gateway_id}{{"조건 판정"}}')
        lines.append(f'    {exception_id}["예외/제한<br/>재시도·상담 전환"]')
        lines.append(f'    {end_id}((End))')
        lines.append(f"    {previous_node} --> {gateway_id}")
        lines.append(f"    {gateway_id} -->|정상| {end_id}")
        lines.append(f"    {gateway_id} -. 실패·제한·보류 .-> {exception_id}")
        lines.append("  end")

    if start_nodes:
        lines.append(f"  class {','.join(start_nodes)} startEvent;")
    if task_nodes:
        lines.append(f"  class {','.join(task_nodes)} task;")
    if gateway_nodes:
        lines.append(f"  class {','.join(gateway_nodes)} gateway;")
    if end_nodes:
        lines.append(f"  class {','.join(end_nodes)} endEvent;")
    if exception_nodes:
        lines.append(f"  class {','.join(exception_nodes)} exception;")
    return "\n".join(lines)


def contains_exception_keyword(process: dict) -> bool:
    text = " ".join(
        str(process.get(key, ""))
        for key in ("id", "name", "description", "usecase_id")
    )
    text += " " + " ".join(str(item) for item in process.get("related_policies", []))
    return any(keyword in text for keyword in ("실패", "제한", "보류", "예외", "상담"))


def is_system_actor_name(name: str) -> bool:
    return any(keyword in name for keyword in ("BSS", "시스템", "기관", "연계", "엔진", "AI", "인증"))


def mermaid_label(*parts: object, max_chars: int = 64) -> str:
    text = " ".join(str(part) for part in parts if str(part).strip())
    text = html.unescape(text)
    text = re.sub(r"</?br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text.replace('"', "'")


def mermaid_multiline_label(*parts: object, max_chars: int = 64) -> str:
    text = mermaid_label(*parts, max_chars=max_chars)
    midpoint = max(18, min(34, len(text) // 2))
    if len(text) <= midpoint + 10:
        return text
    split_at = text.rfind(" ", 0, midpoint)
    if split_at < 10:
        split_at = text.find(" ", midpoint)
    if split_at < 0:
        return text
    return text[:split_at].strip() + "<br/>" + text[split_at:].strip()


def render_functions(spec: dict, template_type: str) -> str:
    functions_by_process: dict[str, list[dict]] = defaultdict(list)
    orphan_functions: list[dict] = []
    for item in spec.get("functions", []):
        process_ids = function_process_ids(item)
        if process_ids:
            for process_id in process_ids:
                functions_by_process[process_id].append(item)
        else:
            orphan_functions.append(item)

    list_blocks = []
    used_function_refs: set[tuple[str, str]] = set()
    group_index = 1
    for process in spec.get("processes", []):
        process_id = str(process.get("id", "")).strip()
        rows = functions_by_process.pop(process_id, [])
        if not rows:
            continue
        list_blocks.append(render_function_list_group(group_index, process.get("name", ""), process_id, rows))
        used_function_refs.update((process_id, str(item.get("id", "")).strip()) for item in rows)
        group_index += 1

    for process_id, rows in functions_by_process.items():
        list_blocks.append(render_function_list_group(group_index, "미연결 프로세스", process_id, rows))
        used_function_refs.update((process_id, str(item.get("id", "")).strip()) for item in rows)
        group_index += 1

    remaining_orphans = [
        item
        for item in orphan_functions
        if ("", str(item.get("id", "")).strip()) not in used_function_refs
    ]
    if remaining_orphans:
        list_blocks.append(render_function_list_group(group_index, "미연결 기능", "", remaining_orphans))

    detail_blocks = []
    if template_type == "full":
        function_details = {
            str(detail.get("function_id", "")).strip(): detail
            for detail in spec.get("function_details", [])
            if isinstance(detail, dict) and str(detail.get("function_id", "")).strip()
        }
        processes_by_id = {
            str(process.get("id", "")).strip(): process
            for process in spec.get("processes", [])
            if isinstance(process, dict) and str(process.get("id", "")).strip()
        }
        for index, item in enumerate(spec.get("functions", []), 1):
            detail = function_details.get(str(item.get("id", "")).strip(), {})
            related_processes = [
                processes_by_id[process_id]
                for process_id in function_process_ids(item)
                if process_id in processes_by_id
            ]
            related_process_policies = unique_values(
                policy_ref
                for process in related_processes
                for policy_ref in (
                    process.get("related_policies", [])
                    if isinstance(process.get("related_policies", []), list)
                    else []
                )
            )
            related_policies = detail.get("related_policies") if isinstance(detail.get("related_policies"), list) else related_process_policies
            input_information = detail.get("input_information") if isinstance(detail.get("input_information"), list) else ["고객 또는 운영자 요청 정보", "상태·권한·기준 정보"]
            processing_logic = detail.get("processing_logic") if isinstance(detail.get("processing_logic"), list) else item.get("details", [])
            sub_functions = detail.get("sub_functions") if isinstance(detail.get("sub_functions"), list) else item.get("details", [])
            output_information = detail.get("output_information") if isinstance(detail.get("output_information"), list) else ["처리 결과", "고객 안내 기준", "이력 저장 결과"]
            failure_exception_cases = detail.get("failure_exception_cases") if isinstance(detail.get("failure_exception_cases"), list) else ["권한·상태 조건 불일치", "BSS·연계 응답 지연", "반복 실패 또는 상담 전환 필요"]
            detail_blocks.append(f"""
<h4>{index}) {heading_with_id(item.get("name", ""), item.get("id", ""))}</h4>
<table>
<thead>
<tr>
<th style="width: 190px;">항목</th>
<th>내용</th>
</tr>
</thead>
<tbody>
{tr(td("기능 ID"), td(esc(item.get("id", "")), "mono"))}
{tr(td("기능명"), td(esc(item.get("name", ""))))}
{tr(td("관련 프로세스"), td(join_lines(function_process_ids(item)), "mono"))}
{tr(td("설명"), td(esc(item.get("description", ""))))}
{tr(td("입력 정보"), td(join_lines(input_information)))}
{tr(td("처리 (상태-액션-결과)"), td(join_lines(processing_logic)))}
{tr(td("세부 기능 구성"), td(join_lines(sub_functions)))}
{tr(td("출력 정보"), td(join_lines(output_information)))}
{tr(td("실패/예외 케이스"), td(join_lines(failure_exception_cases)))}
{tr(td("관련 정책"), td(join_lines(related_policies)))}
</tbody>
</table>
""")
    detail_heading = (
        "<h3>나. 기능 상세</h3>"
        "<p class=\"plain-text\">기능 상세는 프로세스를 수행하기 위해 채널, BSS, 외부기관이 어떤 입력을 받아 어떤 처리를 하고 어떤 결과를 반환하는지 정의한다.<br/>"
        "처리 로직은 정상·분기·예외 흐름이 드러나도록 상태-액션-결과 구조로 작성한다.</p>"
        if template_type == "full"
        else ""
    )
    return f"""
<h2>5. 기능 정의</h2>
<h3>가. 기능 목록</h3>
<p class="plain-text">기능은 화면 단위가 아니라 프로세스를 수행하기 위한 처리 단위로 작성한다.<br/>각 기능은 관련 정책을 실행하는 수단이며, 정책값은 정책 정의 장에서 관리한다.</p>
{''.join(list_blocks)}
{detail_heading}
{''.join(detail_blocks)}
"""


def function_process_ids(item: Mapping[str, object]) -> list[str]:
    values: list[str] = []
    process_id = str(item.get("process_id", "")).strip()
    if process_id:
        values.append(process_id)
    raw = item.get("process_ids")
    if isinstance(raw, list):
        values.extend(str(value).strip() for value in raw if str(value).strip())
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def render_policies(spec: dict) -> str:
    details_by_policy = defaultdict(list)
    for detail in flatten_policy_details(spec.get("policy_details", [])):
        details_by_policy[detail.get("policy_id", "")].append(detail)

    groups = [group for group in spec.get("policy_groups", []) if isinstance(group, dict)]
    group_by_id = {str(group.get("id", "")).strip(): group for group in groups}
    group_by_name = {str(group.get("name", "")).strip(): group for group in groups}

    list_blocks = []
    rendered_policy_ids: set[str] = set()
    group_index = 1
    for process in spec.get("processes", []):
        related_groups = resolve_policy_groups(process.get("related_policies", []), group_by_id, group_by_name)
        if not related_groups:
            continue
        list_blocks.append(
            render_policy_list_group(
                group_index,
                process.get("name", ""),
                process.get("id", ""),
                related_groups,
                details_by_policy,
            )
        )
        rendered_policy_ids.update(str(group.get("id", "")).strip() for group in related_groups)
        group_index += 1

    remaining_groups = [
        group
        for group in groups
        if str(group.get("id", "")).strip() not in rendered_policy_ids
    ]
    if remaining_groups:
        list_blocks.append(render_policy_list_group(group_index, "미연결 정책", "", remaining_groups, details_by_policy))

    detail_blocks = []
    for index, group in enumerate(groups, 1):
        items = []
        for detail in details_by_policy.get(group.get("id", ""), []):
            items.append(f"""
<div class="policy-item">
<div class="policy-item-title">• {esc(detail.get("name", ""))} <span class="mono">({esc(detail.get("id", ""))})</span></div>
<div class="policy-item-content">{policy_item_content(detail.get("content", ""))}</div>
</div>
""")
        detail_blocks.append(f"""
<h4>{index}) {heading_with_id(group.get("name", ""), group.get("id", ""))}</h4>
<div class="policy-group">{''.join(items)}</div>
""")
    return f"""
<h2>6. 정책 정의</h2>
<h3>가. 정책 목록</h3>
<p class="plain-text">정책은 기능 설명이 아니라 기능 동작 기준이다.<br/>프로세스에서 인증 수단, 가능 횟수, 유효시간, 권한, 제한, 고지, 저장, 예외, 운영 판단이 필요한 항목은 정책으로 분리한다.</p>
{''.join(list_blocks)}
<h3>나. 정책 상세</h3>
{''.join(detail_blocks)}
	"""


def flatten_policy_details(raw_details: object) -> list[dict]:
    """Support both flat policy items and grouped policy-detail payloads."""
    if not isinstance(raw_details, list):
        return []
    details: list[dict] = []
    for detail in raw_details:
        if not isinstance(detail, dict):
            continue
        raw_items = detail.get("items")
        if isinstance(raw_items, list):
            policy_id = detail.get("policy_id", "")
            policy_name = detail.get("policy_name", "")
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                normalized = dict(item)
                normalized.setdefault("policy_id", policy_id)
                normalized.setdefault("policy_name", policy_name)
                details.append(normalized)
            continue
        details.append(detail)
    return details


def render_function_list_group(index: int, process_name: object, process_id: object, functions: Sequence[dict]) -> str:
    rows = [
        tr(
            td(esc(item.get("id", "")), "mono"),
            td(esc(item.get("name", ""))),
            td(esc(item.get("description", ""))),
            td(join_lines(item.get("details", []))),
        )
        for item in functions
    ]
    return f"""
<h4>{index}) {heading_with_id(process_name, process_id)}</h4>
<table class="function-list-table">
<thead>{tr(th("기능 ID", style="width: 150px;"), th("기능명", style="width: 180px;"), th("설명"), th("세부 기능 구성", style="width: 260px;"))}</thead>
<tbody>{''.join(rows)}</tbody>
</table>
"""


def render_policy_list_group(
    index: int,
    process_name: object,
    process_id: object,
    policy_groups: Sequence[dict],
    details_by_policy: dict,
) -> str:
    rows = []
    for group in policy_groups:
        details = details_by_policy.get(group.get("id", ""), [])
        rows.append(
            tr(
                td(esc(group.get("id", "")), "mono"),
                td(esc(group.get("name", ""))),
                td(esc(group.get("description", ""))),
                td(join_lines(detail.get("name", "") for detail in details)),
            )
        )
    return f"""
<h4>{index}) {heading_with_id(process_name, process_id)}</h4>
<table class="policy-list-table">
<thead>{tr(th("정책 ID", style="width: 150px;"), th("정책명", style="width: 190px;"), th("설명"), th("정책 항목", style="width: 260px;"))}</thead>
<tbody>{''.join(rows)}</tbody>
</table>
"""


def resolve_policy_groups(
    references: Iterable[object],
    group_by_id: dict[str, dict],
    group_by_name: dict[str, dict],
) -> list[dict]:
    resolved: list[dict] = []
    seen: set[str] = set()
    if isinstance(references, str):
        normalized_references: Iterable[object] = [references]
    else:
        normalized_references = references or []
    for reference in normalized_references:
        policy_id, policy_name = split_policy_reference(reference)
        group = group_by_id.get(policy_id) or group_by_name.get(policy_name)
        if not group:
            continue
        group_id = str(group.get("id", "")).strip()
        if group_id in seen:
            continue
        resolved.append(group)
        seen.add(group_id)
    return resolved


def split_policy_reference(reference: object) -> tuple[str, str]:
    text = str(reference or "").strip()
    match = re.match(r"^(PG-[A-Z0-9]+(?:-[A-Z0-9]+)+)(?:\s*[:|/]\s*|\s+)?(.*)$", text)
    if not match:
        return "", text
    return match.group(1).strip(), match.group(2).strip()


def render_final_check(spec: dict) -> str:
    final_items = list(spec.get("final_check", []))
    if spec.get("meta", {}).get("template_type") == "full":
        final_items.extend(
            [
                "Full 버전의 모든 프로세스 상세에 진입 조건, 종료 조건, 선행·후행 관계, 관련 기능, 관련 정책이 작성되어 있는지 확인한다.",
                "Full 버전의 모든 기능 상세에 입력 정보, 처리 로직, 세부 기능 구성, 출력 정보, 실패·예외 케이스, 관련 정책이 작성되어 있는지 확인한다.",
            ]
        )
    items = "".join(render_final_check_item(index, item) for index, item in enumerate(final_items, 1))
    return f"""
<h2>최종 점검 기준</h2>
<div class="guide">
<div class="guide-title">{esc(spec.get("meta", {}).get("topic_display") or spec.get("meta", {}).get("topic", ""))} 정책서 제출 전 점검</div>
{items}
</div>
"""


def render_final_check_item(index: int, item: object) -> str:
    if isinstance(item, dict):
        title = item.get("item") or item.get("title") or f"점검 항목 {index}"
        criteria = item.get("criteria") or item.get("description") or item.get("content") or ""
        body = sentence_breaks(criteria)
        return f'<div class="guide-section-title">{index}. {esc(title)}</div>{body}'
    text = str(item or "").strip()
    title, body = split_final_check_text(text)
    if body:
        return f'<div class="guide-section-title">{index}. {esc(title)}</div>{sentence_breaks(body)}'
    return f'<div class="guide-section-title">{index}. {esc(title)}</div>'


def split_final_check_text(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    match = re.match(r"^([^:：.。]{2,28})[:：]\s*(.+)$", text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return text, ""


def sentence_breaks(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    normalized = re.sub(r"(?<=[.。])\s+", "<br/>", esc(text))
    return f"{normalized}<br/>"


def heading_with_id(name: object, identifier: object) -> str:
    clean_name = str(name or "").strip()
    clean_id = str(identifier or "").strip()
    if clean_name and clean_id and clean_name != clean_id:
        return f"{esc(clean_name)} ({esc(clean_id)})"
    if clean_name:
        return esc(clean_name)
    if clean_id:
        return esc(clean_id)
    return ""


def transition_usecase_ids_value(transition: Mapping[str, object]) -> List[str]:
    values = transition.get("usecase_ids")
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    legacy = str(transition.get("usecase_id", "")).strip()
    return [legacy] if legacy else []


def join_usecase_refs(transition: Mapping[str, object], usecase_names: Mapping[str, str]) -> str:
    labels = [
        heading_with_id(usecase_names.get(usecase_id, ""), usecase_id)
        for usecase_id in transition_usecase_ids_value(transition)
    ]
    return "<br/>".join(label for label in labels if label)


def state_transition_event_cell(transition: Mapping[str, object], usecase_names: Mapping[str, str]) -> str:
    event = str(transition.get("event", "")).strip()
    if event:
        return esc(event)
    return join_usecase_refs(transition, usecase_names)


def state_reference_cell(value: object, state_names_by_id: Mapping[str, str]) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    name = state_names_by_id.get(raw)
    if not name:
        return esc(raw)
    return f'{esc(name)}<br/><span class="mono">{esc(raw)}</span>'


def join_lines(items: Iterable[object] | object) -> str:
    if items is None:
        return ""
    if isinstance(items, str):
        return esc(items)
    return "<br/>".join(esc(item) for item in items if str(item).strip())


def join_reference_lines(items: Iterable[object], names_by_id: Mapping[object, object]) -> str:
    labels = []
    normalized_names = {
        str(identifier).strip(): str(name).strip()
        for identifier, name in names_by_id.items()
        if str(identifier).strip()
    }
    for item in items or []:
        text = str(item).strip()
        if not text:
            continue
        name = normalized_names.get(text)
        labels.append(f"{text} {name}" if name else text)
    return "<br/>".join(esc(label) for label in labels)


def policy_item_content(value: object) -> str:
    """Render every policy detail sentence as a continuation bullet."""
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
        raw_line = normalize_policy_bullet_line(raw_line)
        if not raw_line:
            continue
        lines.extend(split_policy_bullet_sentences(raw_line))
    return lines


def normalize_policy_bullet_line(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"^[-•]\s*", "", text).strip()
    return text


def split_policy_bullet_sentences(value: str) -> List[str]:
    result: List[str] = []
    start = 0
    for match in re.finditer(r"(?<!\d)([.!?])\s+(?=\S)", value):
        line = value[start : match.start(1) + 1].strip()
        if line:
            result.append(line)
        start = match.end()
    tail = value[start:].strip()
    if tail:
        result.append(tail)
    return result


def unique_values(items: Iterable[object]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


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


def esc(value: object) -> str:
    text = html.unescape(str(value))
    text = re.sub(r"</?br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return html.escape(text, quote=False)
