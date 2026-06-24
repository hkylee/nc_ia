#!/usr/bin/env python3
"""Build consulting-style one-off variants for the display policy task."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_tk_task_queue import (
    SECOND_PASS_ENRICHMENTS,
    SIXTH_ANALYSIS,
    enforce_omitted_source_labels,
    escape,
    format_copy,
)


VARIANT_DIR = ROOT / "output" / "reference_html" / "style_variants"


def item_list(items: list[str] | tuple[str, ...]) -> str:
    return "<ul>" + "".join(f"<li>{format_copy(item)}</li>" for item in items) + "</ul>"


def chips(items: list[str] | tuple[str, ...]) -> str:
    return "".join(f"<span>{escape(item)}</span>" for item in items)


def bcg_variant() -> str:
    data = SIXTH_ANALYSIS
    enrichment = SECOND_PASS_ENRICHMENTS[6]
    pillars = "".join(
        f"""
        <article>
          <span>{index:02d}</span>
          <h3>{escape(title)}</h3>
          <p>{format_copy(body)}</p>
        </article>
        """
        for index, (title, body) in enumerate(data["strategy_pillars"], 1)
    )
    transition_cards = "".join(
        f"""
        <article>
          <b>{escape(title)}</b>
          <p>{format_copy(body)}</p>
          <div class="chip-row">{chips(points)}</div>
        </article>
        """
        for title, body, points in data["transition_columns"]
    )
    matrix_groups = [
        ("Customer Pull", "고객이 바로 체감하는 전시 개선", [data["directions"][0], data["directions"][1]]),
        ("Operating Leverage", "운영 효율과 변경 대응력을 키우는 구조", [data["directions"][2], data["directions"][4]]),
        ("Experience Continuity", "내부·외부 화면을 하나의 경험으로 묶는 기준", [data["directions"][3]]),
        ("Personalized Action", "홈을 상태 기반 실행 허브로 전환", [data["directions"][5]]),
    ]
    matrix = "".join(
        f"""
        <article>
          <div class="matrix-label">{escape(label)}</div>
          <h3>{escape(title)}</h3>
          {''.join(f'<p><strong>{escape(item["title"])}</strong>{format_copy(" - " + item["effects"][0])}</p>' for item in items)}
        </article>
        """
        for label, title, items in matrix_groups
    )
    frictions = "".join(
        f"""
        <tr>
          <th>{index:02d}</th>
          <td><b>{escape(issue)}</b></td>
          <td>{format_copy(impact)}</td>
          <td>{format_copy(data["policy_takeaways"][index - 1])}</td>
        </tr>
        """
        for index, (issue, impact) in enumerate(data["asis"], 1)
    )
    flywheel = "".join(
        f"""
        <article>
          <span>{index:02d}</span>
          <b>{escape(label)}</b>
          <h3>{escape(title)}</h3>
          <p>{format_copy(body)}</p>
        </article>
        """
        for index, (title, body, label) in enumerate(data["journey_steps"], 1)
    )
    integration = "".join(
        f"""
        <article>
          <span>{escape(label)}</span>
          <h3>{escape(title)}</h3>
          <p>{format_copy(body)}</p>
          <div class="chip-row">{chips(points)}</div>
        </article>
        """
        for label, title, body, points in enrichment["cards"]
    )
    html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{escape(data["title"])} · BCG style</title>
  <style>
    :root {{ --ink:#101828; --blue:#0b4f9f; --green:#00856f; --lime:#d7ff54; --orange:#ff8a00; --pink:#ef4e7b; --line:#d6e0ec; --paper:#f4f7fb; --card:#ffffff; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--paper); color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; line-height:1.55; }}
    main {{ width:min(1240px, calc(100% - 56px)); margin:0 auto; padding:40px 0 72px; }}
    .hero {{ display:grid; grid-template-columns:1.1fr .9fr; min-height:520px; border-radius:28px; overflow:hidden; background:#071d3a; color:#fff; box-shadow:0 24px 56px rgba(16,24,40,.18); }}
    .hero-text {{ padding:44px; display:flex; flex-direction:column; justify-content:space-between; }}
    .kicker {{ color:var(--lime); font-size:12px; letter-spacing:.18em; text-transform:uppercase; font-weight:900; }}
    h1 {{ margin:18px 0; max-width:720px; font-size:46px; line-height:1.05; letter-spacing:-.01em; }}
    .lead {{ max-width:760px; color:#e4ecf7; font-size:17px; font-weight:760; }}
    .shift {{ margin-top:26px; padding-top:22px; border-top:1px solid rgba(255,255,255,.2); }}
    .shift h2 {{ margin:0 0 8px; font-size:25px; }}
    .shift p {{ margin:0; color:#d7e4f4; font-weight:740; }}
    .hero-board {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; padding:28px; background:linear-gradient(135deg,#0b4f9f,#00856f); }}
    .hero-board article {{ min-height:150px; border:1px solid rgba(255,255,255,.28); border-radius:22px; background:rgba(255,255,255,.12); padding:18px; backdrop-filter:blur(6px); }}
    .hero-board span {{ color:var(--lime); font-size:13px; font-weight:900; }}
    .hero-board h3 {{ margin:12px 0 8px; font-size:19px; }}
    .hero-board p {{ margin:0; color:#eef6ff; font-size:13px; font-weight:720; }}
    section {{ margin-top:26px; border-radius:26px; background:var(--card); border:1px solid var(--line); padding:30px; box-shadow:0 16px 40px rgba(16,24,40,.08); }}
    .section-head {{ display:flex; align-items:flex-end; justify-content:space-between; gap:18px; margin-bottom:20px; }}
    .section-head span {{ color:var(--blue); font-size:12px; font-weight:950; letter-spacing:.16em; text-transform:uppercase; }}
    h2 {{ margin:4px 0 0; font-size:28px; line-height:1.18; }}
    .transition {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }}
    .transition article {{ position:relative; overflow:hidden; min-height:260px; border-radius:22px; background:#f7fafc; border:1px solid var(--line); padding:22px; }}
    .transition article::before {{ content:""; position:absolute; top:0; left:0; right:0; height:7px; background:linear-gradient(90deg,var(--blue),var(--green),var(--orange)); }}
    .transition b {{ display:block; font-size:22px; }}
    .transition p, .matrix p, td {{ font-size:14px; font-weight:730; }}
    .chip-row {{ display:flex; flex-wrap:wrap; gap:7px; margin-top:16px; }}
    .chip-row span {{ display:inline-flex; border-radius:999px; background:#eaf2fb; color:#123b67; padding:6px 9px; font-size:12px; font-weight:850; }}
    .matrix {{ display:grid; grid-template-columns:repeat(2,1fr); gap:14px; }}
    .matrix article {{ min-height:220px; border-radius:24px; padding:22px; color:#fff; background:#0b4f9f; }}
    .matrix article:nth-child(2) {{ background:#00856f; }}
    .matrix article:nth-child(3) {{ background:#2b3a55; }}
    .matrix article:nth-child(4) {{ background:#ef4e7b; }}
    .matrix-label {{ display:inline-flex; border:1px solid rgba(255,255,255,.32); border-radius:999px; padding:5px 9px; font-size:12px; font-weight:900; }}
    .matrix h3 {{ margin:18px 0 14px; font-size:24px; }}
    .matrix p {{ margin:10px 0 0; color:#f5fbff; }}
    table {{ width:100%; border-collapse:separate; border-spacing:0; overflow:hidden; border:1px solid var(--line); border-radius:20px; }}
    th, td {{ padding:15px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ width:48px; color:var(--blue); font-size:13px; }}
    tr:last-child th, tr:last-child td {{ border-bottom:0; }}
    .flywheel {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }}
    .flywheel article, .integration article {{ border:1px solid var(--line); border-radius:22px; background:#fbfdff; padding:18px; }}
    .flywheel span {{ display:inline-grid; place-items:center; width:32px; height:32px; border-radius:999px; background:var(--lime); color:#071d3a; font-weight:950; }}
    .flywheel b, .integration span {{ display:block; margin-top:14px; color:var(--green); font-size:12px; font-weight:950; letter-spacing:.12em; text-transform:uppercase; }}
    .flywheel h3, .integration h3 {{ margin:7px 0; font-size:18px; }}
    .flywheel p, .integration p {{ margin:0; font-size:13px; font-weight:720; }}
    .integration-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }}
    @media (max-width:920px) {{ main {{ width:min(100% - 28px, 1240px); }} .hero, .transition, .matrix, .flywheel, .integration-grid {{ grid-template-columns:1fr; }} h1 {{ font-size:34px; }} }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="hero-text">
        <div>
          <div class="kicker">Consulting Variant · BCG Style</div>
          <h1>{escape(data["title"])}</h1>
          <p class="lead">{format_copy(data["one_liner"])}</p>
        </div>
        <div class="shift">
          <h2>{escape(data["shift_title"])}</h2>
          <p>{format_copy(data["shift_copy"])}</p>
        </div>
      </div>
      <div class="hero-board">{pillars}</div>
    </section>

    <section>
      <div class="section-head"><div><span>Exhibit 01</span><h2>Strategic Shift Map</h2></div></div>
      <div class="transition">{transition_cards}</div>
    </section>

    <section>
      <div class="section-head"><div><span>Exhibit 02</span><h2>Display Portfolio Logic</h2></div></div>
      <div class="matrix">{matrix}</div>
    </section>

    <section>
      <div class="section-head"><div><span>Exhibit 03</span><h2>Friction to Policy Response</h2></div></div>
      <table><tbody>{frictions}</tbody></table>
    </section>

    <section>
      <div class="section-head"><div><span>Exhibit 04</span><h2>Operating Flywheel</h2></div></div>
      <div class="flywheel">{flywheel}</div>
    </section>

    <section>
      <div class="section-head"><div><span>Exhibit 05</span><h2>Integrated Channel Lens</h2></div></div>
      <div class="integration-grid">{integration}</div>
    </section>
  </main>
</body>
</html>
"""
    return enforce_omitted_source_labels(html)


def mckinsey_variant() -> str:
    data = SIXTH_ANALYSIS
    scqa = "".join(
        f"""
        <article>
          <span>{escape(label)}</span>
          <p>{format_copy(body)}</p>
        </article>
        """
        for label, body in data["problem"]
    )
    issue_tree = "".join(
        f"""
        <article>
          <div class="node-head"><span>{index:02d}</span><h3>{escape(title)}</h3></div>
          <p>{format_copy(data["process_group_notes"][title]["summary"])}</p>
          {item_list(items)}
        </article>
        """
        for index, (title, items) in enumerate(data["process_groups"], 1)
    )
    flow = "".join(
        f"""
        <article>
          <b>{index:02d}</b>
          <h3>{escape(title)}</h3>
          <p>{format_copy(body)}</p>
        </article>
        """
        for index, (title, body, _label) in enumerate(data["journey_steps"], 1)
    )
    priorities = "".join(
        f"""
        <tr>
          <th>{index:02d}</th>
          <td><b>{escape(item["title"])}</b>{item_list(item["todo"])}</td>
          <td>{item_list(item["effects"])}</td>
          <td>{chips(item["kpis"])}</td>
        </tr>
        """
        for index, item in enumerate(data["directions"], 1)
    )
    decisions = "".join(
        f"""
        <tr>
          <th>{escape(area)}</th>
          <td>{format_copy(question)}</td>
          <td>{format_copy(output)}</td>
        </tr>
        """
        for area, question, output in data["policy_questions"]
    )
    takeaways = item_list(data["policy_takeaways"])
    html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{escape(data["title"])} · McKinsey style</title>
  <style>
    :root {{ --ink:#111827; --sub:#374151; --muted:#6b7280; --blue:#1f5eff; --line:#d9dee8; --paper:#ffffff; --wash:#f6f8fb; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#eef2f7; color:var(--ink); font-family:Arial,"Helvetica Neue",-apple-system,BlinkMacSystemFont,sans-serif; line-height:1.55; }}
    main {{ width:min(1180px, calc(100% - 56px)); margin:0 auto; padding:34px 0 72px; }}
    .cover {{ min-height:520px; display:grid; grid-template-columns:minmax(0,1fr) 330px; gap:42px; align-items:end; background:var(--paper); border-top:8px solid var(--blue); padding:56px; box-shadow:0 18px 50px rgba(17,24,39,.13); }}
    .kicker {{ color:var(--blue); font-size:12px; font-weight:800; letter-spacing:.18em; text-transform:uppercase; }}
    h1 {{ margin:18px 0 18px; max-width:760px; font-size:44px; line-height:1.06; letter-spacing:-.01em; }}
    .lead {{ max-width:820px; color:var(--sub); font-size:17px; font-weight:700; }}
    .answer {{ border-left:4px solid var(--blue); padding-left:20px; }}
    .answer h2 {{ margin:0 0 10px; font-size:24px; }}
    .answer p {{ margin:0; color:var(--sub); font-weight:700; }}
    section {{ margin-top:24px; background:var(--paper); border:1px solid var(--line); padding:34px; }}
    .exhibit {{ display:flex; align-items:flex-start; justify-content:space-between; gap:20px; margin-bottom:22px; border-bottom:1px solid var(--line); padding-bottom:16px; }}
    .exhibit span {{ color:var(--blue); font-size:12px; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }}
    h2 {{ margin:6px 0 0; font-size:28px; line-height:1.18; letter-spacing:-.01em; }}
    .scqa {{ display:grid; grid-template-columns:repeat(4,1fr); gap:0; border:1px solid var(--line); }}
    .scqa article {{ min-height:190px; padding:20px; border-right:1px solid var(--line); background:#fff; }}
    .scqa article:last-child {{ border-right:0; }}
    .scqa span {{ display:block; color:var(--blue); font-size:13px; font-weight:800; margin-bottom:12px; }}
    p, li, td {{ color:var(--ink); font-size:14px; font-weight:650; }}
    ul {{ margin:10px 0 0; padding-left:18px; }}
    li + li {{ margin-top:6px; }}
    .tree {{ display:grid; grid-template-columns:repeat(2,1fr); gap:16px; }}
    .tree article {{ border:1px solid var(--line); background:var(--wash); padding:20px; }}
    .node-head {{ display:grid; grid-template-columns:42px minmax(0,1fr); gap:12px; align-items:start; margin-bottom:12px; }}
    .node-head span {{ display:grid; place-items:center; width:34px; height:34px; background:var(--blue); color:#fff; font-weight:800; }}
    h3 {{ margin:0; font-size:18px; line-height:1.28; }}
    .flow {{ display:grid; grid-template-columns:repeat(6,1fr); border:1px solid var(--line); }}
    .flow article {{ min-height:220px; padding:18px; border-right:1px solid var(--line); background:#fff; }}
    .flow article:last-child {{ border-right:0; }}
    .flow b {{ display:block; color:var(--blue); margin-bottom:18px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ border:1px solid var(--line); padding:15px; vertical-align:top; text-align:left; }}
    th {{ width:62px; color:var(--blue); font-size:13px; background:#f8fafc; }}
    td b {{ display:block; margin-bottom:8px; font-size:15px; }}
    td span {{ display:inline-flex; border:1px solid #c8d3e4; background:#fff; color:#1f2937; border-radius:999px; padding:5px 8px; margin:0 6px 6px 0; font-size:12px; font-weight:800; }}
    .takeaways {{ columns:2; column-gap:34px; }}
    .takeaways li {{ break-inside:avoid; margin-bottom:9px; }}
    @media (max-width:960px) {{ main {{ width:min(100% - 28px, 1180px); }} .cover, .scqa, .tree, .flow {{ grid-template-columns:1fr; }} .scqa article, .flow article {{ border-right:0; border-bottom:1px solid var(--line); }} h1 {{ font-size:34px; }} .takeaways {{ columns:1; }} }}
  </style>
</head>
<body>
  <main>
    <section class="cover">
      <div>
        <div class="kicker">Consulting Variant · McKinsey Style</div>
        <h1>{escape(data["title"])}</h1>
        <p class="lead">{format_copy(data["one_liner"])}</p>
      </div>
      <aside class="answer">
        <h2>{escape(data["shift_title"])}</h2>
        <p>{format_copy(data["shift_copy"])}</p>
      </aside>
    </section>

    <section>
      <div class="exhibit"><div><span>Exhibit 1</span><h2>Situation, complication and answer</h2></div></div>
      <div class="scqa">{scqa}</div>
    </section>

    <section>
      <div class="exhibit"><div><span>Exhibit 2</span><h2>Issue tree for the operating model</h2></div></div>
      <div class="tree">{issue_tree}</div>
    </section>

    <section>
      <div class="exhibit"><div><span>Exhibit 3</span><h2>End-to-end To-Be flow</h2></div></div>
      <div class="flow">{flow}</div>
    </section>

    <section>
      <div class="exhibit"><div><span>Exhibit 4</span><h2>Strategic priorities and impact logic</h2></div></div>
      <table><tbody>{priorities}</tbody></table>
    </section>

    <section>
      <div class="exhibit"><div><span>Exhibit 5</span><h2>Policy decisions required for build-out</h2></div></div>
      <table><tbody>{decisions}</tbody></table>
    </section>

    <section>
      <div class="exhibit"><div><span>Exhibit 6</span><h2>Policy takeaways</h2></div></div>
      <div class="takeaways">{takeaways}</div>
    </section>
  </main>
</body>
</html>
"""
    return enforce_omitted_source_labels(html)


def main() -> int:
    VARIANT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "display-policy-bcg-style.html": bcg_variant(),
        "display-policy-mckinsey-style.html": mckinsey_variant(),
    }
    for filename, html_text in outputs.items():
        (VARIANT_DIR / filename).write_text(html_text, encoding="utf-8")
    for filename in outputs:
        print(VARIANT_DIR / filename)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
