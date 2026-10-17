# -*- coding: utf-8 -*-
"""AI Root Cause Analysis — Agile / manufacturing investigation network."""

import re
from markupsafe import Markup, escape

_EMPTY = '—'

_FISHBONE_KEYS = {
    'material': 'Material',
    'machine': 'Machine',
    'method': 'Method',
    'man': 'Manpower',
    'manpower': 'Manpower',
    'measurement': 'Measurement',
    'environment': 'Environment',
    'mother nature': 'Environment',
    'planning': 'Planning',
}

_NETWORK_CATS = [
    ('Material', 'MATERIAL FACTORS', 'material'),
    ('Machine', 'MACHINE FACTORS', 'machine'),
    ('Method', 'METHOD FACTORS', 'method'),
    ('Manpower', 'MANPOWER FACTORS', 'manpower'),
]

_SPRINT_STEPS = [
    ('detect', 'Detect'),
    ('analyze', 'Analyze'),
    ('review', 'Sprint Review'),
    ('escalate', 'Escalate'),
    ('capa', 'CAPA'),
    ('verify', 'Verify'),
    ('retro', 'Retrospective'),
    ('close', 'Close'),
]

_BOARD_STAGES = [
    ('backlog', 'Backlog'),
    ('doing', 'Doing'),
    ('review', 'Review'),
    ('done', 'Done'),
]

_SP_OPTIONS = [3, 5, 8, 5, 3, 8]


def _parse_fishbone(text):
    from .plant_rca_dashboard_content import _parse_fishbone_summary
    return _parse_fishbone_summary(text or '')


def _conf_ring_offset(percent):
    percent = int(max(0, min(100, percent or 0)))
    return int(round(301 * (1 - percent / 100.0)))


def _ring_color(confidence):
    if confidence >= 80:
        return '#3b82f6'
    if confidence >= 55:
        return '#f97316'
    return '#ef4444'


def _is_hot(text, highlight):
    if not text or not highlight:
        return False
    t, h = text.lower(), highlight.lower()
    if t in h or h in t:
        return True
    return any(len(w) > 4 and w in h for w in re.split(r'\W+', t))


def _sprint_segment_class(segment_idx, active_idx):
    if segment_idx < active_idx - 1:
        return 'is-blue'
    if segment_idx == active_idx - 1 and active_idx > 0:
        return 'is-orange'
    return 'is-grey'


def _render_kpis(kpis):
    parts = []
    for kpi in kpis or []:
        trend = kpi.get('trend') or ''
        trend_cls = kpi.get('trend_cls') or 'up'
        trend_html = (
            f'<em class="trend {trend_cls}">{escape(trend)}</em>' if trend else ''
        )
        parts.append(
            f'<div class="o_pm_agile_kpi">'
            f'<b>{escape(kpi.get("label") or "")}</b>'
            f'<div class="kpi_val_row"><strong>{escape(str(kpi.get("value") or _EMPTY))}</strong>'
            f'{trend_html}</div></div>'
        )
    return Markup(''.join(parts))


def _render_velocity_bars(days):
    if not days:
        return Markup('<div class="o_pm_agile_vel_empty">No sprint activity</div>')
    max_c = max((d.get('count') or 0) for d in days) or 1
    bars = []
    for d in days[-6:]:
        h = max(int(round(100 * (d.get('count') or 0) / max_c)), 10)
        bars.append(f'<span style="height:{h}%"></span>')
    return Markup(f'<div class="o_pm_agile_velocity">{"".join(bars)}</div>')


def _render_board(active_board, age):
    items = []
    for key, label in _BOARD_STAGES:
        cls = ' is-active' if key == active_board else ''
        items.append(f'<span class="o_pm_agile_board_step{cls}">{escape(label)}</span>')
    return Markup(
        f'<div class="o_pm_agile_board">'
        f'<div class="o_pm_agile_board_track">{"".join(items)}</div>'
        f'<span class="o_pm_agile_board_age">Age: {escape(age or _EMPTY)}</span></div>'
    )


def _render_network(branches, root_cause, request_id, is_high_impact):
    root = (root_cause or '').strip()
    cols = []
    for label, title, _key in _NETWORK_CATS:
        items = [i for i in (branches.get(label) or []) if i][:3]
        if not items and label not in ('Material', 'Machine'):
            continue
        nodes = []
        for idx, item in enumerate(items):
            hot = _is_hot(item, root)
            sp = _SP_OPTIONS[idx % len(_SP_OPTIONS)]
            ticket = f'AG-{request_id:04d}{idx + 1}'
            cls = 'o_pm_agile_node'
            if hot:
                cls += ' is-hot'
            badges = f'<span class="ticket">{escape(ticket)}</span><span class="sp">{sp} SP</span>'
            if hot and is_high_impact:
                badges += '<span class="badge blocker">Blocker</span>'
            if hot:
                match = 98 if is_high_impact else 92
                badges += f'<span class="badge ai">AI match: {match}%</span>'
            nodes.append(
                f'<div class="{cls}"><span class="node_txt">{escape(item)}</span>'
                f'<div class="node_meta">{badges}</div></div>'
            )
        if not nodes:
            nodes.append(
                '<div class="o_pm_agile_node is-muted"><span class="node_txt">—</span></div>'
            )
        cols.append(
            f'<div class="o_pm_agile_cat"><div class="cat_title">{escape(title)}</div>'
            f'<div class="cat_nodes">{"".join(nodes)}</div></div>'
        )
    if not cols:
        cols.append(
            '<p class="o_pm_agile_empty">Add fishbone factors on <b>Root Cause Analysis &amp; MOM</b>.</p>'
        )
    return Markup(
        f'<div class="o_pm_agile_network_scroll"><div class="o_pm_agile_network">{"".join(cols)}</div></div>'
    )


def _render_jira_actions(actions):
    if not actions:
        return Markup('<p class="o_pm_agile_empty">No actions — add CAPA on RCA form.</p>')
    items = []
    for act in actions:
        done = act.get('done')
        cls = 'is-done' if done else ''
        mark = '✓' if done else '○'
        items.append(
            f'<li class="{cls}"><span class="chk">{mark}</span>'
            f'{escape((act.get("name") or "").strip())}</li>'
        )
    return Markup(f'<ul class="o_pm_agile_jira_list">{"".join(items)}</ul>')


def _render_sprint_steps(active='review'):
    active_idx = next((i for i, (k, _l) in enumerate(_SPRINT_STEPS) if k == active), 2)
    last = len(_SPRINT_STEPS) - 1
    steps = []
    for idx, (_key, label) in enumerate(_SPRINT_STEPS):
        if idx < active_idx:
            step_cls, icon = 'is-done', 'o_pm_sprint_icon_check'
        elif idx == active_idx:
            step_cls, icon = 'is-current', 'o_pm_sprint_icon_pulse'
        else:
            step_cls, icon = 'is-pending', 'o_pm_sprint_icon_pending'
        seg_left = ''
        if idx > 0:
            seg_left = (
                f'<span class="o_pm_sprint_seg o_pm_sprint_seg_left '
                f'{_sprint_segment_class(idx - 1, active_idx)}"></span>'
            )
        seg_right = ''
        if idx < last:
            seg_right = (
                f'<span class="o_pm_sprint_seg o_pm_sprint_seg_right '
                f'{_sprint_segment_class(idx, active_idx)}"></span>'
            )
        steps.append(
            f'<li class="o_pm_sprint_step {step_cls}">'
            f'<div class="o_pm_sprint_rail">{seg_left}'
            f'<span class="o_pm_sprint_icon {icon}"></span>{seg_right}</div>'
            f'<span class="o_pm_sprint_lbl">{escape(label.upper())}</span></li>'
        )
    phase = escape(_SPRINT_STEPS[active_idx][1]) if active_idx < len(_SPRINT_STEPS) else 'Review'
    return Markup(
        f'<div class="o_pm_sprint_orchestrator">'
        f'<div class="o_pm_sprint_head">'
        f'<span class="o_pm_sprint_head_ico"></span>'
        f'<span>Sprint orchestration — <em>{phase} phase active</em></span>'
        f'</div>'
        f'<ol class="o_pm_sprint_stepper">{"".join(steps)}</ol></div>'
    )


def render_agile_rca_dashboard_html(payload=None):
    p = payload or {}
    confidence = int(max(0, min(100, p.get('confidence') or 0)))
    ring_offset = _conf_ring_offset(confidence)
    ring_color = _ring_color(confidence)
    root = escape((p.get('final_root_cause') or '').strip() or _EMPTY)
    version = escape(p.get('build_version') or '1.0.75')
    branches = _parse_fishbone(p.get('fishbone_summary') or '')
    severity = escape(p.get('severity_label') or 'Medium')
    sev_cls = p.get('severity_class') or 'med'

    return Markup(f"""
<div class="o_pm_agile_rca_dash" data-dashboard="agile-rca" data-version="{version}">
  <header class="o_pm_agile_top">
    <div class="o_pm_agile_top_left">
      <h1>Agile Investigation Network <span class="o_pm_agile_build_tag">v{version}</span></h1>
      <p class="o_pm_agile_method_line">
        <span class="o_pm_agile_method_badge">RCA method: Agile</span>
        Sprint-based investigation network, incident intel, and corrective actions from saved work order data.
      </p>
    </div>
    <div class="o_pm_agile_top_right">
      <span class="o_pm_agile_pill pill-sprint">{escape(p.get("sprint_label") or "Sprint active")}</span>
      <span class="o_pm_agile_pill pill-live"><span class="live_dot"></span> Live AI monitoring</span>
      <div class="o_pm_agile_sprint_prog">
        <small>Sprint progress</small>
        <div class="prog_track"><span style="width:{int(p.get("sprint_progress") or 0)}%"></span></div>
        <strong>{int(p.get("sprint_progress") or 0)}%</strong>
      </div>
      <span class="o_pm_agile_bell">&#128276;<em>{int(p.get("notification_count") or 0)}</em></span>
      <span class="o_pm_agile_user"><span class="avatar">{escape(p.get("owner_initials") or "—")}</span>
        <span>{escape(p.get("owner_name") or _EMPTY)}<br/><small>{escape(p.get("owner_role") or "")}</small></span></span>
    </div>
  </header>

  <section class="o_pm_agile_kpis">{_render_kpis(p.get("kpis"))}</section>

  <section class="o_pm_agile_grid">
    <aside class="o_pm_agile_col_left">
      <div class="o_pm_agile_panel_title">Incident intel</div>
      <div class="o_pm_agile_severity {sev_cls}">
        <span class="sev_ico">!</span><strong>{severity}</strong>
      </div>
      <div class="o_pm_agile_vel_block">
        <small>Sprint velocity</small>
        {_render_velocity_bars(p.get("velocity_days"))}
      </div>
      <div class="o_pm_agile_meta">
        <div class="meta_row"><span>Incident ID</span><strong class="linkish">{escape(p.get("incident_id") or _EMPTY)}</strong></div>
        <div class="meta_row"><span>Agile ticket</span><strong class="linkish">{escape(p.get("agile_ticket") or _EMPTY)}</strong></div>
        <div class="meta_row"><span>Sprint</span><strong>{escape(p.get("sprint_name") or _EMPTY)}</strong></div>
        <div class="meta_row"><span>Issue</span><strong>{escape(p.get("issue_title") or _EMPTY)}</strong></div>
        <div class="meta_row"><span>Plant area</span><span class="area_sel">{escape(p.get("plant_area") or _EMPTY)}</span></div>
      </div>
      <div class="o_pm_agile_board_wrap">
        <small>Issue board track</small>
        {_render_board(p.get("board_active"), p.get("incident_age"))}
      </div>
    </aside>

    <main class="o_pm_agile_col_center">
      <div class="o_pm_agile_engine_head">
        <div class="o_pm_agile_panel_title"><span class="pulse"></span> Agile investigation network</div>
        <div class="o_pm_agile_legend">
          <span><i class="dot blue"></i> AI dependency</span>
          <span><i class="dot orange"></i> Root cause confirmed</span>
        </div>
      </div>
      {_render_network(branches, p.get("final_root_cause"), p.get("current_request_id") or 0, p.get("is_high_impact"))}
    </main>

    <aside class="o_pm_agile_col_right">
      <div class="o_pm_agile_panel_title">AI agile actions</div>
      <div class="o_pm_agile_intel_top">
        <div class="o_pm_agile_ring">
          <svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="48" fill="none" stroke="#eff6ff" stroke-width="11"/>
          <circle cx="60" cy="60" r="48" fill="none" stroke="{ring_color}" stroke-width="11" stroke-linecap="round"
            stroke-dasharray="301" stroke-dashoffset="{ring_offset}" transform="rotate(-90 60 60)"/></svg>
          <div class="ring_txt">{confidence}%<small>Confidence</small></div>
        </div>
        <div class="o_pm_agile_predict">
          <b>Predicted root cause</b>
          <p>{root}</p>
        </div>
      </div>
      <div class="o_pm_agile_jira">
        <b>Recommended actions</b>
        {_render_jira_actions(p.get("corrective_actions"))}
      </div>
    </aside>
  </section>

  <footer class="o_pm_agile_footer">
    {_render_sprint_steps(p.get("sprint_active_step") or "review")}
  </footer>
</div>
""")
