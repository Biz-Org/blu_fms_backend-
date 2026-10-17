# -*- coding: utf-8 -*-
"""AI CAPA Management Dashboard — corrective/preventive actions from maintenance.request."""

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
    'planning': 'Planning',
}

_CAPA_WORKFLOW = [
    ('detect', 'Detect'),
    ('analyze', 'Analyze'),
    ('approve', 'Approve'),
    ('implement', 'Implement'),
    ('verify', 'Verify'),
    ('audit', 'Audit'),
    ('close', 'Close'),
]

_LIFECYCLE_COLUMNS = [
    {
        'top_key': 'detect',
        'top_label': 'Issue detection',
        'top_ico': 'ico-detect',
        'bottom_key': 'close',
        'bottom_label': 'Closure & audit',
        'bottom_ico': 'ico-close',
    },
    {
        'top_key': 'investigate',
        'top_label': 'Root cause investigation',
        'top_ico': 'ico-investigate',
        'bottom_key': 'verify',
        'bottom_label': 'Verification',
        'bottom_ico': 'ico-verify',
    },
    {
        'top_key': 'plan',
        'top_label': 'Corrective action planning',
        'top_ico': 'ico-plan',
        'bottom_key': 'implement',
        'bottom_label': 'Implementation',
        'bottom_ico': 'ico-implement',
    },
    {
        'top_key': 'prevent',
        'top_label': 'Preventive strategy',
        'top_ico': 'ico-prevent',
        'bottom_key': 'approve',
        'bottom_label': 'Approval workflow',
        'bottom_ico': 'ico-approve',
    },
]

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


def _capa_segment_class(segment_idx, active_idx):
    if segment_idx < active_idx - 1:
        return 'is-blue'
    if segment_idx == active_idx - 1 and active_idx > 0:
        return 'is-orange'
    return 'is-grey'


def _parse_fishbone_counts(text):
    from .plant_rca_dashboard_content import _parse_fishbone_summary

    branches = _parse_fishbone_summary(text or '')
    return {label: len(items) for label, items in branches.items() if items}


def _classification_rows(fb_counts):
    mapping = [
        ('Method', 'Process', 'process'),
        ('Machine', 'Machine', 'machine'),
        ('Material', 'Material', 'material'),
        ('Manpower', 'Process', 'process'),
        ('Measurement', 'Process', 'process'),
        ('Environment', 'Process', 'process'),
        ('Planning', 'Process', 'process'),
    ]
    buckets = {'process': 0, 'machine': 0, 'material': 0}
    for key, count in fb_counts.items():
        bucket = 'machine'
        for src, dest, b in mapping:
            if key.lower().startswith(src.lower()):
                bucket = b
                break
        buckets[bucket] = buckets.get(bucket, 0) + count
    total = sum(buckets.values()) or 1
    return [
        {'label': 'Process', 'pct': int(round(100 * buckets['process'] / total)), 'cls': 'seg-process'},
        {'label': 'Machine', 'pct': int(round(100 * buckets['machine'] / total)), 'cls': 'seg-machine'},
        {'label': 'Material', 'pct': int(round(100 * buckets['material'] / total)), 'cls': 'seg-material'},
    ]


def _render_kpis(kpis):
    parts = []
    for kpi in kpis or []:
        trend = kpi.get('trend') or ''
        trend_cls = kpi.get('trend_cls') or 'up'
        trend_html = f'<em class="trend {trend_cls}">{escape(trend)}</em>' if trend else ''
        parts.append(
            f'<div class="o_pm_capa_kpi">'
            f'<b>{escape(kpi.get("label") or "")}</b>'
            f'<div class="kpi_val_row"><strong>{escape(str(kpi.get("value") or _EMPTY))}</strong>'
            f'{trend_html}</div></div>'
        )
    return Markup(''.join(parts))


def _render_issues(issues, current_id):
    if not issues:
        return Markup('<p class="o_pm_capa_empty">No team CAPA issues.</p>')
    rows = []
    for issue in issues:
        active = ' is-active' if issue.get('id') == current_id else ''
        count = issue.get('count')
        badge = f'<span class="issue_count">{int(count)}</span>' if count is not None else ''
        rows.append(
            f'<div class="o_pm_capa_issue_row{active}" data-request-id="{issue.get("id")}" '
            f'role="button" tabindex="0">'
            f'<span class="issue_lbl">{escape((issue.get("name") or _EMPTY)[:42])}</span>'
            f'{badge}</div>'
        )
    return Markup(f'<div class="o_pm_capa_issue_list">{"".join(rows)}</div>')


def _render_classification(rows):
    if not rows:
        return Markup('<p class="o_pm_capa_empty">Add fishbone on RCA form.</p>')
    segs = []
    for row in rows:
        w = max(int(row.get('pct') or 0), 4)
        segs.append(
            f'<span class="class_seg {row.get("cls") or ""}" style="flex:{w}" '
            f'title="{escape(row.get("label") or "")} {int(row.get("pct") or 0)}%">'
            f'{escape(row.get("label") or "")} ({int(row.get("pct") or 0)}%)</span>'
        )
    return Markup(f'<div class="o_pm_capa_class_bar">{"".join(segs)}</div>')


def _render_lifecycle(payload):
    p = payload or {}
    hub = escape((p.get('hub_title') or 'Production quality non-conformance')[:48].upper())
    root = escape((p.get('final_root_cause') or _EMPTY)[:80])
    confidence = int(p.get('confidence') or 0)
    top_idx = int(p.get('lifecycle_top_idx') or 0)
    bottom_idx = int(p.get('lifecycle_bottom_idx') or 3)
    rail_idx = int(p.get('lifecycle_rail_idx') if p.get('lifecycle_rail_idx') is not None else top_idx)
    rail_pct = int(max(12, min(100, p.get('lifecycle_rail_percent') or int(round(100 * (rail_idx + 1) / 4)))))
    bullets = p.get('preventive_bullets') or []

    cols_html = []
    for col_idx, col in enumerate(_LIFECYCLE_COLUMNS):
        col_cls = ['o_pm_capa_lc_col']
        if col_idx <= rail_idx:
            col_cls.append('is-rail-blue')
        if col_idx == top_idx:
            col_cls.append('is-top-current')
        if col_idx < top_idx:
            col_cls.append('is-top-done')
        if col_idx == 3 and top_idx >= 2:
            col_cls.append('is-prevent-focus')
        if col_idx == bottom_idx:
            col_cls.append('is-bottom-current')
        if col_idx > bottom_idx or (col['bottom_key'] == 'close' and p.get('lifecycle_close_muted')):
            col_cls.append('is-bottom-muted')

        callout_above = ''
        if col['top_key'] == 'investigate' and root and root != _EMPTY:
            conf_txt = f' ({confidence}%)' if confidence else ''
            callout_above = (
                f'<div class="o_pm_capa_lc_callout identify">'
                f'<b>Identified cause</b><p>{root}{escape(conf_txt)}</p></div>'
            )
        if col['top_key'] == 'prevent' and top_idx >= 2:
            if bullets:
                items = ''.join(f'<li>{escape(b)}</li>' for b in bullets[:3])
            else:
                items = (
                    '<li>Enable predictive maintenance AI</li>'
                    '<li>Implement automated curing alerts</li>'
                )
            callout_above = (
                f'<div class="o_pm_capa_lc_callout strategy">'
                f'<b>AI strategy focus</b><ul>{items}</ul></div>'
            )

        top_node_cls = 'o_pm_capa_lc_node top'
        bottom_node_cls = 'o_pm_capa_lc_node bottom'
        if col_idx == 3 and top_idx >= 2:
            top_node_cls += ' is-hot'

        cols_html.append(
            f'<div class="{" ".join(col_cls)}">'
            f'{callout_above}'
            f'<div class="{top_node_cls}">'
            f'<div class="lc_icon_box {col["top_ico"]}"></div>'
            f'<div class="lc_title">{escape(col["top_label"])}</div>'
            f'</div>'
            f'<div class="lc_stem lc_stem_down"></div>'
            f'<div class="lc_rail_dot"></div>'
            f'<div class="lc_stem lc_stem_up"></div>'
            f'<div class="{bottom_node_cls}">'
            f'<div class="lc_icon_box {col["bottom_ico"]}"></div>'
            f'<div class="lc_title">{escape(col["bottom_label"])}</div>'
            f'</div>'
            f'</div>'
        )

    return Markup(
        f'<div class="o_pm_capa_lifecycle_v2">'
        f'<div class="o_pm_capa_lc_engine_head">'
        f'<h3><span class="pulse"></span> AI-powered CAPA lifecycle</h3>'
        f'<span class="o_pm_capa_lc_hub_badge">Central node: {hub}</span>'
        f'</div>'
        f'<div class="o_pm_capa_lc_timeline">'
        f'<div class="o_pm_capa_lc_rail_track">'
        f'<div class="o_pm_capa_lc_rail_bg"></div>'
        f'<div class="o_pm_capa_lc_rail_fill" style="width:{rail_pct}%"></div>'
        f'</div>'
        f'<div class="o_pm_capa_lc_columns">{"".join(cols_html)}</div>'
        f'</div></div>'
    )


def _render_workflow(active):
    active_idx = next((i for i, (k, _l) in enumerate(_CAPA_WORKFLOW) if k == active), 2)
    last = len(_CAPA_WORKFLOW) - 1
    steps = []
    for idx, (_key, label) in enumerate(_CAPA_WORKFLOW):
        if idx < active_idx:
            step_cls, icon = 'is-done', 'o_pm_capa_wf_icon_check'
        elif idx == active_idx:
            step_cls, icon = 'is-current', 'o_pm_capa_wf_icon_pulse'
        else:
            step_cls, icon = 'is-pending', 'o_pm_capa_wf_icon_pending'
        seg_left = ''
        if idx > 0:
            seg_left = (
                f'<span class="o_pm_capa_wf_seg o_pm_capa_wf_seg_left '
                f'{_capa_segment_class(idx - 1, active_idx)}"></span>'
            )
        seg_right = ''
        if idx < last:
            seg_right = (
                f'<span class="o_pm_capa_wf_seg o_pm_capa_wf_seg_right '
                f'{_capa_segment_class(idx, active_idx)}"></span>'
            )
        steps.append(
            f'<li class="o_pm_capa_wf_step {step_cls}">'
            f'<div class="o_pm_capa_wf_rail">{seg_left}<span class="{icon}"></span>{seg_right}</div>'
            f'<span class="o_pm_capa_wf_lbl">{escape(label.upper())}</span></li>'
        )
    phase = _CAPA_WORKFLOW[active_idx][1] if active_idx < len(_CAPA_WORKFLOW) else 'Approve'
    return Markup(
        f'<div class="o_pm_capa_workflow">'
        f'<div class="o_pm_capa_wf_head"><span class="wf_ico"></span>'
        f'<span>MES process automation: <em>{escape(phase)} phase</em></span></div>'
        f'<ol class="o_pm_capa_wf_stepper">{"".join(steps)}</ol></div>'
    )


def _render_trend_bars(trend_days, anomaly_idx=-1):
    if not trend_days:
        return Markup('<p class="o_pm_capa_empty">No trend data</p>')
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
    return Markup(f'<div class="o_pm_capa_trend_bars">{"".join(bars)}</div>')


def _render_status_board(board):
    if not board:
        return Markup('')
    boxes = []
    for box in board:
        boxes.append(
            f'<div class="status_box {box.get("cls") or ""}">'
            f'<small>{escape(box.get("label") or "")}</small>'
            f'<strong>{int(box.get("count") or 0)}</strong></div>'
        )
    return Markup(f'<div class="o_pm_capa_status_board">{"".join(boxes)}</div>')


def _render_alerts(alerts):
    if not alerts:
        return Markup('<p class="o_pm_capa_empty">No alerts</p>')
    return Markup(''.join(
        f'<div class="o_pm_capa_alert {a.get("level", "info")}">'
        f'<span class="dot"></span>'
        f'<span>{escape(a.get("text") or "")}</span>'
        f'<em>{escape(a.get("time") or "")}</em></div>'
        for a in alerts
    ))


def _render_ai_actions(actions):
    if not actions:
        return Markup('<p class="o_pm_capa_empty">No CAPA actions — add on RCA &amp; MOM form.</p>')
    items = []
    for act in actions:
        done = act.get('done')
        mark = '✓' if done else '○'
        cls = 'is-done' if done else ''
        items.append(
            f'<li class="{cls}"><span class="chk">{mark}</span>'
            f'{escape((act.get("name") or "").strip())}</li>'
        )
    return Markup(f'<ul class="o_pm_capa_action_list">{"".join(items)}</ul>')


def render_capa_rca_dashboard_html(payload=None):
    p = payload or {}
    confidence = int(max(0, min(100, p.get('confidence') or 0)))
    ring_offset = _conf_ring_offset(confidence)
    ring_color = _ring_color(confidence)
    insight = escape((p.get('ai_insight') or '').strip() or _EMPTY)
    version = escape(p.get('build_version') or '1.0.81')
    severity_cls = escape(p.get('severity_cls') or 'med')

    return Markup(f"""
<div class="o_pm_capa_rca_dash o_pm_capa_viewport" data-dashboard="capa-rca" data-version="{version}">
  <header class="o_pm_capa_top">
    <div class="o_pm_capa_top_left">
      <h1>AI CAPA Management Dashboard <span class="o_pm_capa_build_tag">v{version}</span></h1>
      <p class="o_pm_capa_method_line">
        <span class="o_pm_capa_method_badge">RCA method: CAPA lifecycle</span>
        Corrective and preventive action orchestration from saved work orders, RCA, and CAPA lines.
      </p>
    </div>
    <div class="o_pm_capa_top_right">
      <span class="o_pm_capa_pill pill-sync"><span class="live_dot"></span> SAP sync live</span>
      <span class="o_pm_capa_pill pill-ai"><span class="live_dot teal"></span> AI monitoring</span>
      <div class="o_pm_capa_head_kpi">
        <small>Production health</small>
        <strong>{escape(p.get("health_display") or _EMPTY)}</strong>
        <div class="o_pm_capa_health_bar"><span style="width:{int(p.get("health_bar_percent") or 0)}%"></span></div>
      </div>
      <div class="o_pm_capa_head_kpi">
        <small>Active shift</small>
        <strong>{escape(p.get("shift_label") or _EMPTY)}</strong>
      </div>
      <span class="o_pm_capa_bell">&#128276;<em>{int(p.get("notification_count") or 0)}</em></span>
      <span class="o_pm_capa_user"><span class="avatar">{escape(p.get("owner_initials") or "—")}</span>
        <span>{escape(p.get("owner_name") or _EMPTY)}<br/><small>{escape(p.get("owner_role") or "")}</small></span></span>
    </div>
  </header>

  <section class="o_pm_capa_kpis">{_render_kpis(p.get("kpis"))}</section>

  <section class="o_pm_capa_grid">
    <aside class="o_pm_capa_col_left">
      <div class="o_pm_capa_sec_title">Issue &amp; initiation</div>
      {_render_issues(p.get("team_issues"), p.get("current_request_id"))}
      <div class="o_pm_capa_context">
        <div class="o_pm_capa_sec_title">CAPA context</div>
        <div class="ctx_row"><span>CAPA ID</span><strong class="linkish">{escape(p.get("capa_id") or _EMPTY)}</strong></div>
        <div class="ctx_row"><span>Incident ID</span><strong>{escape(p.get("incident_id") or _EMPTY)}</strong></div>
        <div class="ctx_row"><span>Project</span><strong>{escape(p.get("project_label") or _EMPTY)}</strong></div>
        <div class="ctx_row"><span>Severity</span><strong class="sev_badge {severity_cls}">{escape(p.get("severity_label") or _EMPTY)}</strong></div>
        <div class="ctx_row"><span>Assigned dept</span><strong>{escape(p.get("assigned_dept") or _EMPTY)}</strong></div>
        <div class="ctx_row"><span>Due date</span><strong class="due_warn">{escape(p.get("due_date_label") or _EMPTY)}</strong></div>
      </div>
      <div class="o_pm_capa_sec_title">Issue classification (AI)</div>
      {_render_classification(p.get("classification_rows"))}
    </aside>

    <main class="o_pm_capa_col_center">
      <div class="o_pm_capa_lifecycle_wrap">
        {_render_lifecycle(p)}
      </div>
    </main>

    <aside class="o_pm_capa_col_right">
      <div class="o_pm_capa_sec_title">AI quality intelligence</div>
      <div class="o_pm_capa_intel_top">
        <div class="o_pm_capa_ring">
          <svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="48" fill="none" stroke="#eff6ff" stroke-width="11"/>
          <circle cx="60" cy="60" r="48" fill="none" stroke="{ring_color}" stroke-width="11" stroke-linecap="round"
            stroke-dasharray="301" stroke-dashoffset="{ring_offset}" transform="rotate(-90 60 60)"/></svg>
          <div class="ring_txt">{confidence}%<small>Confidence</small></div>
        </div>
        <div class="o_pm_capa_predict">
          <b>AI predicted insight</b>
          <p>{insight}</p>
        </div>
      </div>
      <div class="o_pm_capa_intel_grid">
        <div class="intel_box loss"><small>Est. financial loss</small><strong>{escape(p.get("cost_label") or _EMPTY)}</strong></div>
        <div class="intel_box risk"><small>Downtime prob.</small><strong>{int(p.get("failure_risk_percent") or 0)}% <small>({escape(p.get("risk_level") or "")})</small></strong></div>
        <div class="intel_box audit"><small>Audit compliance</small><strong>{escape(p.get("audit_status") or _EMPTY)}</strong></div>
        <div class="intel_box esc"><small>Escalation priority</small><strong>{escape(p.get("escalation_priority") or _EMPTY)}</strong></div>
      </div>
      <div class="o_pm_capa_actions_blk">
        <b>AI-generated actions</b>
        {_render_ai_actions(p.get("corrective_actions"))}
      </div>
    </aside>
  </section>

  <section class="o_pm_capa_mid_footer">
    {_render_workflow(p.get("capa_workflow_step") or "approve")}
  </section>

  <footer class="o_pm_capa_footer">
    <div class="o_pm_capa_footer_card">
      <div class="o_pm_capa_sec_title">Rejection &amp; defect trend</div>
      {_render_trend_bars(p.get("trend_days"), p.get("trend_anomaly_idx"))}
    </div>
    <div class="o_pm_capa_footer_card">
      <div class="o_pm_capa_sec_title">CAPA status board</div>
      {_render_status_board(p.get("status_board"))}
    </div>
    <div class="o_pm_capa_footer_card">
      <div class="o_pm_capa_sec_title">Real-time operational alerts</div>
      {_render_alerts(p.get("live_alerts"))}
    </div>
  </footer>
</div>
""")
