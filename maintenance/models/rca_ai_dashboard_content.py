# -*- coding: utf-8 -*-
"""Root Cause Analysis & MOM dashboard — meeting record view (not fishbone diagram)."""

from markupsafe import Markup, escape

from .plant_rca_dashboard_content import _parse_fishbone_summary

_EMPTY = '—'

_FISHBONE_ROWS = [
    ('Material', 'c-blue'),
    ('Machine', 'c-orange'),
    ('Method', 'c-green'),
    ('Manpower', 'c-purple'),
    ('Measurement', 'c-cyan'),
    ('Environment', 'c-red'),
]


def _conf_ring_offset(percent):
    percent = int(max(0, min(100, percent or 0)))
    return int(round(301 * (1 - percent / 100.0)))


def _ring_color(percent):
    if percent >= 80:
        return '#22c55e'
    if percent >= 55:
        return '#f59e0b'
    return '#ef4444'


def _impact_tag_class(level):
    if level == 'high':
        return 'critical'
    if level == 'medium':
        return 'high'
    if level == 'low':
        return 'low'
    return 'med'


def _render_summary_cards(cards):
    if not cards:
        return Markup('')
    return Markup(''.join(
        f'<div class="o_pm_mom_card {escape(c.get("tone") or "")}">'
        f'<small>{escape(c.get("label") or "")}</small>'
        f'<strong>{c.get("value") or _EMPTY}</strong>'
        f'<span>{escape(c.get("hint") or "")}</span></div>'
        for c in cards
    ))


def _render_issues(issues, current_id):
    if not issues:
        return Markup('<p class="o_pm_mom_empty">No other team requests.</p>')
    blocks = []
    for issue in issues:
        active = ' is-active' if issue.get('id') == current_id else ''
        tag = _impact_tag_class(issue.get('impact_level'))
        type_lbl = escape(issue.get('type_label') or '')
        blocks.append(
            f'<div class="o_pm_mom_issue{active}" data-request-id="{issue.get("id") or ""}">'
            f'<div class="issue_top"><span class="issue_emoji">{escape(issue.get("emoji") or "🔧")}</span>'
            f'<span class="issue_name">{escape(issue.get("name") or "")}</span></div>'
            f'<small>{escape(issue.get("meta_line") or "")}</small>'
            f'<div class="issue_meta"><span>{escape(issue.get("age") or "")}</span>'
            f'<span class="tag {tag}">{escape(issue.get("impact_label") or "")}</span>'
            f'<span class="tag type">{type_lbl}</span></div></div>'
        )
    return Markup(''.join(blocks))


def _render_fishbone_table(branches):
    rows = []
    for label, color in _FISHBONE_ROWS:
        items = branches.get(label, [])
        text = '; '.join(items) if items else ''
        cls = 'filled' if text else 'empty'
        rows.append(
            f'<tr class="{cls}"><th class="{color}">{label}</th>'
            f'<td>{escape(text or "Not recorded — add on MOM tab below")}</td></tr>'
        )
    return Markup(
        '<table class="o_pm_mom_fb_table"><tbody>' + ''.join(rows) + '</tbody></table>'
    )


def _render_why_lines(lines):
    if not lines:
        return Markup(
            '<p class="o_pm_mom_empty">No 5-Why lines — optional; add on request or use Why-Why screen.</p>'
        )
    items = []
    for line in lines:
        items.append(
            f'<li><b>{escape(line.get("why") or "")}</b>'
            f'<span>{escape(line.get("because") or "")}</span></li>'
        )
    return Markup('<ol class="o_pm_mom_why_list">' + ''.join(items) + '</ol>')


def _render_checklist(items):
    if not items:
        return Markup('')
    rows = []
    for item in items:
        done = item.get('done')
        mark = '✓' if done else '○'
        cls = 'done' if done else 'pending'
        rows.append(
            f'<li class="{cls}"><span class="chk">{mark}</span>'
            f'{escape(item.get("label") or "")}</li>'
        )
    return Markup('<ul class="o_pm_mom_checklist">' + ''.join(rows) + '</ul>')


def _render_capa_list(actions):
    if not actions:
        return Markup('<p class="o_pm_mom_empty">No corrective actions — add on MOM tab below.</p>')
    items = []
    for action in actions:
        done = action.get('done')
        mark = '✓' if done else '○'
        cls = 'done' if done else 'pending'
        items.append(
            f'<li class="{cls}"><span class="chk">{mark}</span>'
            f'{escape((action.get("name") or "").strip())}</li>'
        )
    return Markup('<ul class="o_pm_mom_capa">' + ''.join(items) + '</ul>')


def _render_text_block(title, text, empty_hint):
    body = (text or '').strip()
    if body:
        return Markup(
            f'<div class="o_pm_mom_block"><h4>{escape(title)}</h4>'
            f'<p>{escape(body)}</p></div>'
        )
    return Markup(
        f'<div class="o_pm_mom_block is-empty"><h4>{escape(title)}</h4>'
        f'<p class="o_pm_mom_empty">{escape(empty_hint)}</p></div>'
    )


def render_rca_ai_dashboard_html(confidence=0, equipment_label=None, root_cause=None, payload=None):
    if payload:
        return render_rca_ai_dashboard_from_payload(payload)
    return render_rca_ai_dashboard_from_payload({
        'completeness_percent': confidence,
        'equipment_select': equipment_label or _EMPTY,
        'final_root_cause': root_cause or '',
        'team_issues': [],
        'summary_cards': [],
        'checklist': [],
        'corrective_actions': [],
        'build_version': '1.0.197',
        'scope_note': 'Open a maintenance request to load MOM data',
    })


def render_rca_ai_dashboard_from_payload(payload=None):
    """MOM meeting dashboard — document view; use Plant RCA for Ishikawa diagram."""
    p = payload or {}
    completeness = int(max(0, min(100, p.get('completeness_percent') or 0)))
    ring_offset = _conf_ring_offset(completeness)
    ring_color = _ring_color(completeness)
    version = escape(p.get('build_version') or '1.0.197')
    scope = escape(p.get('scope_note') or 'RCA meeting record for this work order')
    type_label = escape(p.get('maintenance_type_label') or '')
    wo_ref = escape(p.get('work_order_ref') or _EMPTY)
    stage_label = escape(p.get('stage_label') or _EMPTY)
    equip = escape(p.get('equipment_select') or _EMPTY)
    area = escape(p.get('work_area') or _EMPTY)
    owner_initials = escape(p.get('owner_initials') or '—')
    owner_name = escape(p.get('owner_name') or '')
    owner_role = escape(p.get('owner_role') or '')
    root = escape((p.get('final_root_cause') or '').strip() or 'Not confirmed — enter on MOM tab below.')
    action_owner = escape((p.get('mom_action_owner') or '').strip() or 'Not assigned')
    current_id = p.get('current_request_id')
    branches = _parse_fishbone_summary(p.get('fishbone_summary') or '')
    capa_pct = escape(p.get('capa_completion') or '0%')
    rca_status = escape(p.get('rca_status_label') or 'In progress')
    rca_status_cls = escape(p.get('rca_status_class') or 'warn')

    return Markup(f"""
<div class="o_pm_ai_rca_dash o_pm_rca_mom_dash" data-rca-dashboard-mode="mom" data-rca-dashboard-version="{version}">
  <header class="o_pm_mom_head">
    <div class="o_pm_mom_head_title">
      <h2>Root Cause Analysis &amp; MOM <span class="o_pm_rca_build_tag">{version}</span></h2>
      <p>{scope} · <strong>{type_label}</strong> · {wo_ref} · {equip}</p>
    </div>
    <div class="o_pm_mom_head_meta">
      <span class="o_pm_mom_status {rca_status_cls}">{rca_status}</span>
      <span class="o_pm_mom_pill">Stage: <strong>{stage_label}</strong></span>
      <span class="o_pm_mom_pill">Area: <strong>{area}</strong></span>
      <span class="o_pm_mom_user"><span class="avatar">{owner_initials}</span>{owner_name}<small>{owner_role}</small></span>
    </div>
  </header>

  <section class="o_pm_mom_summary">{_render_summary_cards(p.get("summary_cards"))}</section>

  <div class="o_pm_mom_body">
    <aside class="o_pm_mom_col o_pm_mom_sidebar">
      <h3>Team requests</h3>
      <div class="o_pm_mom_issues_scroll">{_render_issues(p.get("team_issues"), current_id)}</div>
      <div class="o_pm_mom_hint">
        Use <strong>Fishbone RCA</strong> in the header for the Ishikawa diagram and AI analysis view.
      </div>
    </aside>

    <main class="o_pm_mom_col o_pm_mom_main">
      <div class="o_pm_mom_section">
        <h3>Final root cause</h3>
        <div class="o_pm_mom_root_box">{root}</div>
      </div>

      <div class="o_pm_mom_section">
        <h3>Fishbone summary (6M)</h3>
        {_render_fishbone_table(branches)}
      </div>

      {_render_text_block("MOM discussion", p.get("mom_discussion"), "Record meeting discussion on the MOM tab below.")}
      {_render_text_block("MOM decision", p.get("mom_decision"), "Record agreed decision on the MOM tab below.")}

      <div class="o_pm_mom_block">
        <h4>Action owner</h4>
        <p class="o_pm_mom_owner">{action_owner}</p>
      </div>

      <div class="o_pm_mom_section">
        <h3>5 Why analysis</h3>
        {_render_why_lines(p.get("why_lines"))}
      </div>
    </main>

    <aside class="o_pm_mom_col o_pm_mom_status_col">
      <h3>RCA completeness</h3>
      <div class="o_pm_mom_ring_wrap">
        <div class="o_pm_ai_rca_conf_ring">
          <svg viewBox="0 0 120 120" aria-hidden="true">
            <circle cx="60" cy="60" r="48" fill="none" stroke="#ecfdf5" stroke-width="11"/>
            <circle cx="60" cy="60" r="48" fill="none" stroke="{ring_color}" stroke-width="11"
              stroke-linecap="round" stroke-dasharray="301" stroke-dashoffset="{ring_offset}"
              transform="rotate(-90 60 60)"/>
          </svg>
          <div class="conf_txt">{completeness}%<small>Complete</small></div>
        </div>
      </div>
      {_render_checklist(p.get("checklist"))}

      <div class="o_pm_mom_section">
        <h3>Corrective actions (CAPA)</h3>
        <div class="o_pm_mom_capa_head">Completion: <strong>{capa_pct}</strong></div>
        {_render_capa_list(p.get("corrective_actions"))}
      </div>
    </aside>
  </div>
</div>
""")
