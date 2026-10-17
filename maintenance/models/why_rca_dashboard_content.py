# -*- coding: utf-8 -*-
"""AI Why-Why Root Cause Analysis — full dashboard from rca_line_ids."""

import re
from markupsafe import Markup, escape

_EMPTY = '—'

_WHY_WORKFLOW = [
    ('detect', 'Detect'),
    ('investigate', 'Investigate'),
    ('why', 'Why Analysis'),
    ('root', 'Root Cause'),
    ('escalate', 'Escalate'),
    ('corrective', 'Corrective Action'),
    ('verify', 'Verify'),
    ('optimize', 'Optimize'),
    ('close', 'Close'),
]

_FISHBONE_KEYS = {
    'material': 'Material',
    'machine': 'Machine',
    'method': 'Method',
    'man': 'Manpower',
    'manpower': 'Manpower',
    'measurement': 'Measurement',
    'environment': 'Environment',
    'planning': 'Planning',
}

_TREND_COLORS = ['c-blue', 'c-blue', 'c-orange', 'c-red', 'c-orange', 'c-blue', 'c-blue']


def _conf_ring_offset(percent):
    percent = int(max(0, min(100, percent or 0)))
    return int(round(301 * (1 - percent / 100.0)))


def _ring_color(confidence):
    if confidence >= 80:
        return '#3b82f6'
    if confidence >= 55:
        return '#f97316'
    return '#ef4444'


def _why_segment_class(segment_idx, active_idx):
    if segment_idx < active_idx - 1:
        return 'is-blue'
    if segment_idx == active_idx - 1 and active_idx > 0:
        return 'is-orange'
    return 'is-grey'


def _is_hot(text, highlight):
    if not text or not highlight:
        return False
    t, h = text.lower(), highlight.lower()
    if t in h or h in t:
        return True
    return any(len(w) > 4 and w in h for w in re.split(r'\W+', t))


def _parse_fishbone_counts(text):
    from .plant_rca_dashboard_content import _parse_fishbone_summary

    branches = _parse_fishbone_summary(text or '')
    return {label: len(items) for label, items in branches.items() if items}


def _render_kpis(kpis):
    parts = []
    for kpi in kpis or []:
        trend = kpi.get('trend') or ''
        trend_cls = kpi.get('trend_cls') or 'up'
        trend_html = f'<em class="trend {trend_cls}">{escape(trend)}</em>' if trend else ''
        parts.append(
            f'<div class="o_pm_why_kpi">'
            f'<b>{escape(kpi.get("label") or "")}</b>'
            f'<div class="kpi_val_row"><strong>{escape(str(kpi.get("value") or _EMPTY))}</strong>'
            f'{trend_html}</div></div>'
        )
    return Markup(''.join(parts))


def _render_issues(issues, current_id):
    if not issues:
        return Markup('<p class="o_pm_why_empty">No team requests.</p>')
    rows = []
    for issue in issues:
        active = ' is-active' if issue.get('id') == current_id else ''
        count = issue.get('count')
        badge = f'<span class="issue_count">{int(count)}</span>' if count is not None else ''
        rows.append(
            f'<div class="o_pm_why_issue_row{active}" data-request-id="{issue.get("id")}" '
            f'role="button" tabindex="0">'
            f'<span class="issue_lbl">{escape((issue.get("name") or _EMPTY).upper())}</span>'
            f'{badge}</div>'
        )
    return Markup(f'<div class="o_pm_why_issue_list">{"".join(rows)}</div>')


def _render_heatmap(hours):
    if not hours:
        return Markup('')
    cells = []
    for cell in hours:
        cls = cell.get('level') or 'low'
        cells.append(f'<span class="hm_cell {cls}" title="{escape(cell.get("label") or "")}"></span>')
    return Markup(f'<div class="o_pm_why_heatmap">{"".join(cells)}</div>')


def _render_why_tree(lines, incident_title, root_cause, auto_generated=False):
    """Sequential 5-Why chain — problem → why/because steps → confirmed root cause."""
    root = (root_cause or '').strip()
    title = escape((incident_title or 'Production incident')[:60])

    if not lines:
        return Markup(
            f'<div class="o_pm_why_tree_empty">'
            f'<div class="o_pm_why_node l1 incident"><span class="ico">!</span>'
            f'<span>{title}</span></div>'
            f'<p>Add <b>5 Why</b> lines on the panel below, or enter fishbone + root cause on '
            f'<b>Root Cause Analysis &amp; MOM</b> to auto-build the chain.</p></div>'
        )

    steps = [
        f'<div class="o_pm_why_chain_start">'
        f'<div class="o_pm_why_node l1 incident"><span class="ico">!</span>'
        f'<span><small>Problem</small>{title}</span></div></div>',
    ]

    if auto_generated:
        steps.append(
            '<div class="o_pm_why_auto_badge">Auto-built from fishbone summary — '
            'edit 5 Why lines below to customize</div>'
        )

    for idx, line in enumerate(lines, start=1):
        prob = escape((line.get('problem') or f'Why {idx}?').strip())
        cause = escape((line.get('cause') or _EMPTY).strip())
        is_root_step = bool(root) and (
            _is_hot(cause, root) or idx == len(lines)
        )
        root_badge = (
            '<span class="ai_pred">Root cause level</span>' if is_root_step and root else ''
        )
        answer_cls = 'o_pm_why_node why_a is-root' if is_root_step and root else 'o_pm_why_node why_a'
        steps.append(
            f'<div class="o_pm_why_chain_step">'
            f'<div class="o_pm_why_step_num">Why {idx}</div>'
            f'<div class="o_pm_why_chain_connector"></div>'
            f'<div class="o_pm_why_node why_q"><span class="lbl">Question</span><span>{prob}</span></div>'
            f'<div class="o_pm_why_chain_arrow" aria-hidden="true">↓</div>'
            f'<div class="{answer_cls}"><span class="lbl">Because</span><span>{cause}</span>'
            f'{root_badge}</div></div>'
        )

    if root:
        steps.append(
            f'<div class="o_pm_why_chain_end">'
            f'<div class="o_pm_why_chain_connector"></div>'
            f'<div class="o_pm_why_node why_confirmed">'
            f'<span class="lbl">Confirmed root cause</span>'
            f'<span>{escape(root)}</span></div></div>'
        )

    return Markup(
        f'<div class="o_pm_why_tree_scroll"><div class="o_pm_why_tree o_pm_why_chain">'
        f'{"".join(steps)}</div></div>'
    )


def _render_workflow(active):
    active_idx = next((i for i, (k, _l) in enumerate(_WHY_WORKFLOW) if k == active), 2)
    last = len(_WHY_WORKFLOW) - 1
    steps = []
    for idx, (_key, label) in enumerate(_WHY_WORKFLOW):
        if idx < active_idx:
            step_cls, icon = 'is-done', 'o_pm_why_wf_icon_check'
        elif idx == active_idx:
            step_cls, icon = 'is-current', 'o_pm_why_wf_icon_pulse'
        else:
            step_cls, icon = 'is-pending', 'o_pm_why_wf_icon_pending'
        seg_left = ''
        if idx > 0:
            seg_left = (
                f'<span class="o_pm_why_wf_seg o_pm_why_wf_seg_left '
                f'{_why_segment_class(idx - 1, active_idx)}"></span>'
            )
        seg_right = ''
        if idx < last:
            seg_right = (
                f'<span class="o_pm_why_wf_seg o_pm_why_wf_seg_right '
                f'{_why_segment_class(idx, active_idx)}"></span>'
            )
        steps.append(
            f'<li class="o_pm_why_wf_step {step_cls}">'
            f'<div class="o_pm_why_wf_rail">{seg_left}<span class="{icon}"></span>{seg_right}</div>'
            f'<span class="o_pm_why_wf_lbl">{escape(label.upper())}</span></li>'
        )
    phase = _WHY_WORKFLOW[active_idx][1] if active_idx < len(_WHY_WORKFLOW) else 'Why Analysis'
    return Markup(
        f'<div class="o_pm_why_workflow">'
        f'<div class="o_pm_why_wf_head"><span class="wf_ico"></span>'
        f'<span>AI automation: <em>{escape(phase)} phase</em></span></div>'
        f'<ol class="o_pm_why_wf_stepper">{"".join(steps)}</ol></div>'
    )


def _render_trend_bars(trend_days, anomaly_idx=-1):
    if not trend_days:
        return Markup('<p class="o_pm_why_empty">No trend data</p>')
    max_c = max((d.get('count') or 0) for d in trend_days) or 1
    bars = []
    for idx, day in enumerate(trend_days):
        count = day.get('count') or 0
        h = max(int(round(100 * count / max_c)), 8) if max_c else 8
        color = _TREND_COLORS[idx % len(_TREND_COLORS)]
        cls = 'bar anomaly' if idx == anomaly_idx else f'bar {color}'
        label = 'Anomaly' if idx == anomaly_idx and count else ''
        bars.append(
            f'<div class="trend_col"><div class="{cls}" style="height:{h}%"></div>'
            f'<label>{escape(day.get("label") or "")}</label>'
            f'{f"<em>{label}</em>" if label else ""}</div>'
        )
    return Markup(f'<div class="o_pm_why_trend_bars">{"".join(bars)}</div>')


def _render_defect_bars(defect_rows):
    if not defect_rows:
        return Markup('<p class="o_pm_why_empty">—</p>')
    max_v = max((r.get('pct') or 0) for r in defect_rows) or 1
    rows = []
    for row in defect_rows:
        w = max(int(round(100 * (row.get('pct') or 0) / max_v)), 12)
        rows.append(
            f'<div class="defect_row"><span>{escape(row.get("label") or "")}</span>'
            f'<div class="defect_track"><span style="width:{w}%"></span></div>'
            f'<strong>{int(row.get("pct") or 0)}%</strong></div>'
        )
    return Markup(''.join(rows))


def _render_alerts(alerts):
    if not alerts:
        return Markup('<p class="o_pm_why_empty">No alerts</p>')
    return Markup(''.join(
        f'<div class="o_pm_why_alert {a.get("level", "info")}">'
        f'<span class="dot"></span>'
        f'<span>{escape(a.get("text") or "")}</span>'
        f'<em>{escape(a.get("time") or "")}</em></div>'
        for a in alerts
    ))


def _render_capa(actions):
    if not actions:
        return Markup('<p class="o_pm_why_empty">No CAPA on record.</p>')
    items = []
    for act in actions:
        done = act.get('done')
        mark = '✓' if done else '○'
        cls = 'is-done' if done else ''
        items.append(
            f'<li class="{cls}"><span class="chk">{mark}</span>'
            f'{escape((act.get("name") or "").strip())}</li>'
        )
    return Markup(f'<ul class="o_pm_why_capa_list">{"".join(items)}</ul>')


def render_why_rca_dashboard_html(payload=None):
    p = payload or {}
    confidence = int(max(0, min(100, p.get('confidence') or 0)))
    ring_offset = _conf_ring_offset(confidence)
    ring_color = _ring_color(confidence)
    root = escape((p.get('final_root_cause') or '').strip() or _EMPTY)
    version = escape(p.get('build_version') or '1.0.77')

    return Markup(f"""
<div class="o_pm_why_rca_dash" data-dashboard="why-rca" data-version="{version}">
  <header class="o_pm_why_top">
    <div class="o_pm_why_top_left">
      <h1>AI Why-Why Root Cause Analysis <span class="o_pm_why_build_tag">v{version}</span></h1>
      <p class="o_pm_why_method_line">
        <span class="o_pm_why_method_badge">RCA method: 5 Why</span>
        Sequential why-chain analysis, root cause validation, and CAPA from saved work order data.
      </p>
    </div>
    <div class="o_pm_why_top_right">
      <span class="o_pm_why_pill pill-sync"><span class="live_dot"></span> Plant sync live</span>
      <span class="o_pm_why_pill pill-ai"><span class="live_dot teal"></span> AI monitoring active</span>
      <div class="o_pm_why_head_kpi">
        <small>Production health</small>
        <strong>{escape(p.get("health_display") or _EMPTY)}</strong>
        <div class="o_pm_why_health_bar"><span style="width:{int(p.get("health_bar_percent") or 0)}%"></span></div>
      </div>
      <div class="o_pm_why_head_kpi">
        <small>Shift monitored</small>
        <strong>{escape(p.get("shift_label") or _EMPTY)}</strong>
      </div>
      <span class="o_pm_why_bell">&#128276;<em>{int(p.get("notification_count") or 0)}</em></span>
      <span class="o_pm_why_user"><span class="avatar">{escape(p.get("owner_initials") or "—")}</span>
        <span>{escape(p.get("owner_name") or _EMPTY)}<br/><small>{escape(p.get("owner_role") or "")}</small></span></span>
    </div>
  </header>

  <section class="o_pm_why_kpis">{_render_kpis(p.get("kpis"))}</section>

  <section class="o_pm_why_grid">
    <aside class="o_pm_why_col_left">
      <div class="o_pm_why_sec_title">Production issue selection</div>
      {_render_issues(p.get("team_issues"), p.get("current_request_id"))}
      <div class="o_pm_why_sec_title">Operational heatmap</div>
      {_render_heatmap(p.get("heatmap_hours"))}
    </aside>

    <main class="o_pm_why_col_center">
      <div class="o_pm_why_engine_head">
        <div class="o_pm_why_sec_title"><span class="pulse"></span> Why-why flow engine</div>
      </div>
      {_render_why_tree(
          p.get("why_lines"),
          p.get("incident_title"),
          p.get("final_root_cause"),
          p.get("why_auto_generated"),
      )}
    </main>

    <aside class="o_pm_why_col_right">
      <div class="o_pm_why_sec_title">AI root cause intelligence</div>
      <div class="o_pm_why_intel_top">
        <div class="o_pm_why_ring">
          <svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="48" fill="none" stroke="#eff6ff" stroke-width="11"/>
          <circle cx="60" cy="60" r="48" fill="none" stroke="{ring_color}" stroke-width="11" stroke-linecap="round"
            stroke-dasharray="301" stroke-dashoffset="{ring_offset}" transform="rotate(-90 60 60)"/></svg>
          <div class="ring_txt">{confidence}%<small>Why confidence</small></div>
        </div>
        <div class="o_pm_why_predict">
          <b>Predicted root cause</b>
          <p>{root}</p>
        </div>
      </div>
      <div class="o_pm_why_risk_pair">
        <div class="risk_box"><small>Financial risk</small><strong>{escape(p.get("cost_label") or _EMPTY)}</strong></div>
        <div class="risk_box"><small>Downtime prob.</small><strong>{int(p.get("failure_risk_percent") or 0)}%</strong></div>
      </div>
      <div class="o_pm_why_capa">
        <b>AI suggested CAPA</b>
        {_render_capa(p.get("corrective_actions"))}
      </div>
    </aside>
  </section>

  <section class="o_pm_why_mid_footer">
    {_render_workflow(p.get("why_workflow_step") or "why")}
  </section>

  <footer class="o_pm_why_footer">
    <div class="o_pm_why_footer_card">
      <div class="o_pm_why_sec_title">Rejection trend analysis</div>
      {_render_trend_bars(p.get("trend_days"), p.get("trend_anomaly_idx"))}
    </div>
    <div class="o_pm_why_footer_card">
      <div class="o_pm_why_sec_title">Defect distribution heatmap</div>
      {_render_defect_bars(p.get("defect_rows"))}
    </div>
    <div class="o_pm_why_footer_card">
      <div class="o_pm_why_sec_title">Real-time operational alerts</div>
      {_render_alerts(p.get("live_alerts"))}
    </div>
  </footer>
</div>
""")
