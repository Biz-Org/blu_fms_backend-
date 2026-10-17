# -*- coding: utf-8 -*-
"""AI Fishbone Root Cause Analysis — mockup layout, data from maintenance.request."""

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

_BRANCH_SLOTS = [
    ('fb_tl', 'Material', 'c-blue'),
    ('fb_tr', 'Machine', 'c-orange'),
    ('fb_ml', 'Method', 'c-green'),
    ('fb_mr', 'Manpower', 'c-purple'),
    ('fb_bl', 'Measurement', 'c-cyan'),
    ('fb_br', 'Environment', 'c-red'),
]

_MES_STEPS = [
    ('detect', 'Detect'),
    ('analyze', 'Analyze'),
    ('predict', 'AI Prediction'),
    ('escalate', 'Escalate'),
    ('corrective', 'Corrective Action'),
    ('verify', 'Verify'),
    ('optimize', 'Optimize'),
    ('close', 'Close'),
]

_TREND_COLORS = ['c-red', 'c-orange', 'c-yellow', 'c-green', 'c-orange', 'c-red', 'c-green']

_IMPACT_TAG = {
    'high': ('critical', 'Critical'),
    'medium': ('high', 'High'),
    'low': ('low', 'Low'),
}


_FISHBONE_CATEGORY_RE = re.compile(
    r'(?:^|[;\n]|\.)\s*'
    r'(man|manpower|machine|method|material|measurement|environment|planning|mother nature)\s*:\s*',
    re.IGNORECASE | re.MULTILINE,
)

# Copy/paste format for RCA MOM (semicolon or period before each category).
FISHBONE_SUMMARY_FORMAT = (
    'Man: delayed alarm response; '
    'Machine: worn coupling, blocked cooler; '
    'Method: no weekly temperature log; '
    'Material: aged pressure switch; '
    'Environment: dusty production hall'
)


def _parse_fishbone_summary(text):
    """Parse fishbone text into 6M branches (supports ; newline or . between categories)."""
    branches = {label: [] for _pos, label, _color in _BRANCH_SLOTS}
    if not text:
        return branches

    text = text.strip()
    matches = list(_FISHBONE_CATEGORY_RE.finditer(text))
    if matches:
        for idx, match in enumerate(matches):
            head = match.group(1)
            key = _FISHBONE_KEYS.get(head.strip().lower())
            if not key:
                continue
            body = text[match.end():]
            if idx + 1 < len(matches):
                body = text[match.end():matches[idx + 1].start()]
            body = body.strip().strip('.').strip()
            for part in re.split(r'[,/]+', body):
                part = part.strip()
                if part and part.upper() not in ('N/A', 'NA', 'NONE'):
                    branches[key].append(part)
        if any(branches.values()):
            return branches

    # Legacy: one category per semicolon/newline line
    for chunk in re.split(r'[;\n]+', text):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ':' in chunk:
            head, body = chunk.split(':', 1)
            key = _FISHBONE_KEYS.get(head.strip().lower())
            if not key:
                continue
            for part in re.split(r'[,/]+', body):
                part = part.strip()
                if part and part.upper() not in ('N/A', 'NA', 'NONE'):
                    branches[key].append(part)
        else:
            branches['Method'].append(chunk)
    return branches


def _is_hot_cause(item, highlight_text):
    if not highlight_text:
        return False
    item_lower = item.lower()
    hl = highlight_text.lower()
    if item_lower in hl or hl in item_lower:
        return True
    words = [w for w in re.split(r'\W+', item_lower) if len(w) > 4]
    return any(w in hl for w in words)


def _conf_ring_offset(percent):
    percent = int(max(0, min(100, percent or 0)))
    return int(round(301 * (1 - percent / 100.0)))


def _ring_color(confidence):
    if confidence >= 80:
        return '#22c55e'
    if confidence >= 55:
        return '#f97316'
    return '#ef4444'


def _fishbone_svg(hub_line1, hub_line2, hub_icon='⚠'):
    line1 = escape((hub_line1 or 'Failure')[:22])
    line2 = escape((hub_line2 or 'Event')[:22])
    icon = escape(hub_icon or '⚠')
    return f"""
<svg class="o_pm_ai_rca_fishbone_svg" viewBox="0 0 880 380" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs>
    <filter id="hubGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <line x1="70" y1="190" x2="810" y2="190" stroke="#cbd5e1" stroke-width="2"/>
  <line x1="210" y1="48" x2="392" y2="158" stroke="#3b82f6" stroke-width="2" stroke-dasharray="7 5"/>
  <line x1="210" y1="332" x2="392" y2="222" stroke="#22c55e" stroke-width="2" stroke-dasharray="7 5"/>
  <line x1="670" y1="48" x2="488" y2="158" stroke="#f97316" stroke-width="2" stroke-dasharray="7 5"/>
  <line x1="670" y1="332" x2="488" y2="222" stroke="#ef4444" stroke-width="2" stroke-dasharray="7 5"/>
  <line x1="70" y1="88" x2="270" y2="168" stroke="#8b5cf6" stroke-width="2" stroke-dasharray="7 5"/>
  <line x1="70" y1="292" x2="270" y2="212" stroke="#06b6d4" stroke-width="2" stroke-dasharray="7 5"/>
  <g class="o_pm_fb_hub" transform="translate(440 190)">
    <circle r="58" fill="#ffffff" stroke="#7eb8ff" stroke-width="5" filter="url(#hubGlow)"/>
    <text y="-8" text-anchor="middle" font-size="18">{icon}</text>
    <text y="10" text-anchor="middle" font-size="8.5" font-weight="700" fill="#1e3a8a">{line1}</text>
    <text y="24" text-anchor="middle" font-size="8.5" font-weight="700" fill="#1e3a8a">{line2}</text>
  </g>
</svg>
"""


def _render_issues(issues, current_id):
    if not issues:
        return Markup('<p class="o_pm_plant_empty">No open requests on this team.</p>')
    items = []
    for issue in issues:
        active = ' is-active' if issue.get('id') == current_id else ''
        count = issue.get('count')
        count_badge = (
            f'<span class="issue_count">{int(count)}</span>' if count is not None else ''
        )
        rid = issue.get('id')
        name = (issue.get('name') or _EMPTY).upper()
        items.append(
            f'<div class="o_pm_fb_issue_row{active}" data-request-id="{rid}" role="button" tabindex="0">'
            f'<span class="issue_lbl">{escape(name)}</span>{count_badge}</div>'
        )
    return Markup(f'<div class="o_pm_fb_issue_list">{"".join(items)}</div>')


def _render_context(ctx):
    incident = escape(ctx.get('incident_id') or _EMPTY)
    plant = escape(ctx.get('plant_area') or _EMPTY)
    equip = escape(ctx.get('equipment') or _EMPTY)
    return Markup(
        f'<div class="o_pm_fb_ctx_grid">'
        f'<div class="ctx_cell"><span>Incident ID</span><strong class="ctx_id">{incident}</strong></div>'
        f'<div class="ctx_cell"><span>Plant area</span>'
        f'<span class="ctx_select">{plant}</span></div>'
        f'<div class="ctx_cell ctx_wide"><span>Equipment</span><strong>{equip}</strong></div>'
        f'</div>'
    )


def _render_trend(trend_days):
    if not trend_days:
        return Markup('<p class="o_pm_plant_empty">No team activity in the last 7 days.</p>')
    max_count = max((d.get('count') or 0) for d in trend_days) or 1
    bars = []
    for idx, day in enumerate(trend_days):
        count = day.get('count') or 0
        height = max(int(round(100 * count / max_count)), 6) if max_count else 6
        color = _TREND_COLORS[idx % len(_TREND_COLORS)]
        bars.append(
            f'<div><div class="bar {color}" style="height:{height}%"></div>'
            f'<label>{escape(day.get("label") or "")}</label></div>'
        )
    return Markup(
        '<div class="o_pm_fb_trend">'
        '<div class="o_pm_fb_sec_title">Rejection trend</div>'
        '<div class="trend_chart_wrap">'
        f'<div class="trend_days">{"".join(bars)}</div>'
        '</div></div>'
    )


def _render_fishbone(branches, highlight_text, hub_title):
    parts = []
    for pos, label, color in _BRANCH_SLOTS:
        items = [i for i in (branches.get(label) or []) if i and i != _EMPTY]
        if not items:
            continue
        spans = []
        for item in items[:3]:
            hot = _is_hot_cause(item, highlight_text)
            cls = ' class="is-hot"' if hot else ''
            spans.append(f'<span{cls}>{escape(item)}</span>')
        parts.append(
            f'<div class="fb_branch {pos}"><b class="{color}">{escape(label.upper())}</b>'
            f'{"".join(spans)}</div>'
        )
    if not parts:
        parts.append(
            '<p class="o_pm_plant_empty" style="position:absolute;left:50%;top:50%;'
            'transform:translate(-50%,-50%);z-index:3;text-align:center">'
            'No fishbone factors saved. Use <b>Root Cause Analysis &amp; MOM</b> to edit.</p>'
        )
    title = (hub_title or 'Maintenance failure').strip()
    words = title.split()
    if len(words) > 4:
        mid = len(words) // 2
        hub1 = ' '.join(words[:mid])
        hub2 = ' '.join(words[mid:])
    elif len(words) >= 2:
        hub1, hub2 = words[0], ' '.join(words[1:])
    else:
        hub1, hub2 = title[:18], 'Failure'
    svg = _fishbone_svg(hub1, hub2)
    effect = escape((hub_title or 'Quality failure')[:42].upper())
    return Markup(
        f'<div class="o_pm_ai_rca_fishbone_wrap o_pm_fb_engine">'
        f'{svg}{"".join(parts)}'
        f'<div class="o_pm_fb_effect_head"><span class="fx_warn">!</span><span>{effect}</span></div>'
        f'</div>'
    )


def _render_kpis(kpis):
    if not kpis:
        return Markup('')
    parts = []
    for kpi in kpis:
        val = escape(str(kpi.get('value') or _EMPTY))
        css = kpi.get('class') or 'kpi-network'
        tone = kpi.get('tone') or ''
        tone_cls = f' tone-{tone}' if tone else ''
        accent_tone = tone or 'neutral'
        parts.append(
            f'<div class="o_pm_ai_rca_kpi {css}{tone_cls}">'
            f'<b>{escape(kpi.get("label") or "")}</b>'
            f'<strong>{val}</strong>'
            f'<span class="kpi_accent tone-{accent_tone}"></span></div>'
        )
    return Markup(''.join(parts))


def _mes_segment_class(segment_idx, active_idx):
    """Line between step segment_idx and segment_idx + 1."""
    if segment_idx < active_idx - 1:
        return 'is-teal'
    if segment_idx == active_idx - 1 and active_idx > 0:
        return 'is-orange'
    return 'is-grey'


def _render_mes_steps(active='escalate'):
    active_idx = next((i for i, (key, _label) in enumerate(_MES_STEPS) if key == active), 3)
    last_idx = len(_MES_STEPS) - 1
    steps = []
    for idx, (_key, label) in enumerate(_MES_STEPS):
        if idx < active_idx:
            step_cls = 'is-done'
            icon = '<span class="o_pm_mes_icon o_pm_mes_icon_check" aria-hidden="true"></span>'
        elif idx == active_idx:
            step_cls = 'is-current'
            icon = '<span class="o_pm_mes_icon o_pm_mes_icon_pulse" aria-hidden="true"></span>'
        else:
            step_cls = 'is-pending'
            icon = '<span class="o_pm_mes_icon o_pm_mes_icon_pending" aria-hidden="true"></span>'

        seg_left = ''
        if idx > 0:
            seg_left = (
                f'<span class="o_pm_mes_seg o_pm_mes_seg_left '
                f'{_mes_segment_class(idx - 1, active_idx)}"></span>'
            )
        seg_right = ''
        if idx < last_idx:
            seg_right = (
                f'<span class="o_pm_mes_seg o_pm_mes_seg_right '
                f'{_mes_segment_class(idx, active_idx)}"></span>'
            )

        steps.append(
            f'<li class="o_pm_mes_step {step_cls}">'
            f'<div class="o_pm_mes_step_rail">{seg_left}{icon}{seg_right}</div>'
            f'<span class="o_pm_mes_lbl">{escape(label.upper())}</span></li>'
        )
    return Markup(
        '<div class="o_pm_mes_orchestrator">'
        '<div class="o_pm_mes_head">'
        '<span class="o_pm_mes_head_ico" aria-hidden="true"></span>'
        '<span class="o_pm_mes_head_txt">MES process orchestration</span>'
        '</div>'
        f'<ol class="o_pm_mes_stepper">{"".join(steps)}</ol>'
        '</div>'
    )


def _render_capa(actions):
    if not actions:
        return Markup('<p class="o_pm_plant_empty">No CAPA yet — add on <b>Root Cause Analysis &amp; MOM</b>.</p>')
    items = []
    for action in actions:
        done = action.get('done')
        cls = 'capa_done' if done else 'capa_open'
        mark = '✓' if done else '○'
        items.append(
            f'<li class="{cls}"><span class="capa_mark">{mark}</span>'
            f'{escape((action.get("name") or "").strip())}</li>'
        )
    return Markup('<ul>' + ''.join(items) + '</ul>')


def _render_alerts(alerts):
    if not alerts:
        return Markup('<p class="o_pm_plant_empty">No open alerts.</p>')
    return Markup(''.join(
        f'<div class="o_pm_plant_alert {a.get("level", "info")}">'
        f'<span class="alert_dot"></span>{escape(a.get("text") or "")}</div>'
        for a in alerts
    ))


def _render_impact_bars(downtime_pct):
    pct = int(max(0, min(100, downtime_pct or 0)))
    heights = [30, 45, 40, 55, 50, 65, max(pct, 15)]
    bars = []
    for idx, h in enumerate(heights):
        cls = 'bar hot' if idx == len(heights) - 1 else 'bar'
        bars.append(f'<div class="{cls}" style="height:{h}%"></div>')
    return Markup(''.join(bars))


def render_plant_rca_dashboard_html(payload=None):
    p = payload or {}
    confidence = int(max(0, min(100, p.get('confidence') or 0)))
    ring_offset = _conf_ring_offset(confidence)
    ring_color = _ring_color(confidence)
    failure_risk = int(max(0, min(100, p.get('failure_risk_percent') or 0)))
    root_raw = (p.get('final_root_cause') or '').strip()
    root = escape(root_raw or _EMPTY)
    insight_raw = (p.get('ai_insight') or '').strip() or root_raw
    insight = escape(insight_raw or 'Complete fishbone summary and final root cause on this request.')
    equip = escape(p.get('equipment_select') or _EMPTY)
    impact = escape(p.get('impact_label') or _EMPTY)
    branches = _parse_fishbone_summary(p.get('fishbone_summary') or '')
    owner_initials = escape(p.get('owner_initials') or '—')
    owner_name = escape(p.get('owner_name') or '')
    owner_role = escape(p.get('owner_role') or 'Maintenance')
    notif = int(p.get('notification_count') or 0)
    health_display = escape(p.get('health_display') or p.get('health_score') or _EMPTY)
    hub_title = p.get('fishbone_hub_title') or p.get('problem_title') or 'Maintenance failure'
    downtime_label = escape(p.get('downtime_risk_label') or impact)
    cost_label = escape(p.get('cost_label') or _EMPTY)
    version = escape(p.get('build_version') or '1.0.72')

    ctx = p
    fishbone_html = _render_fishbone(branches, root_raw, hub_title)
    capa_block = (
        '<div class="o_pm_ai_rca_actions"><b>Corrective actions (CAPA)</b>'
        f'{_render_capa(p.get("corrective_actions"))}</div>'
    )

    return Markup(f"""
<div class="o_pm_ai_rca_dash o_pm_plant_rca_dash o_pm_fb_compact" data-dashboard="plant-rca" data-version="{version}">
  <header class="o_pm_fb_top">
    <div class="o_pm_fb_top_left">
      <div class="o_pm_fb_title_row">
        <h1>AI Fishbone Root Cause Analysis</h1>
        <span class="o_pm_fb_live"><span class="live_dot"></span> Plant sync live</span>
      </div>
      <p class="o_pm_fb_sub">Real-time diagnostics from saved work orders, equipment life, and CAPA.</p>
    </div>
    <div class="o_pm_fb_top_right">
      <div class="o_pm_fb_head_kpi">
        <small>Production health</small>
        <strong>{health_display}</strong>
        <div class="o_pm_fb_health_bar"><span style="width:{escape(str(p.get("health_bar_percent") or 0))}%"></span></div>
      </div>
      <div class="o_pm_fb_head_kpi">
        <small>Shift status</small>
        <strong>{escape(p.get("shift_label") or _EMPTY)}</strong>
      </div>
      <span class="o_pm_ai_rca_bell" title="Open alerts">&#128276;<em>{notif}</em></span>
      <span class="o_pm_ai_rca_user"><span class="avatar">{owner_initials}</span><span class="u_txt">{owner_name}</span></span>
    </div>
  </header>

  <section class="o_pm_ai_rca_kpis o_pm_fb_kpis">{_render_kpis(p.get("kpis"))}</section>

  <section class="o_pm_ai_rca_body o_pm_fb_grid">
    <aside class="o_pm_ai_rca_col o_pm_fb_col_left">
      <div class="o_pm_fb_sec_title">Issue selection</div>
      {_render_issues(p.get("team_issues"), p.get("current_request_id"))}
      <div class="o_pm_fb_sec_title">Incident context</div>
      {_render_context(ctx)}
      {_render_trend(p.get("trend_days"))}
    </aside>

    <main class="o_pm_ai_rca_col o_pm_fb_col_center">
      <div class="o_pm_fb_engine_bar">
        <div class="o_pm_fb_sec_title"><span class="pulse-dot"></span> Ishikawa AI engine</div>
        <span class="o_pm_ai_rca_equipment_select" title="{equip}">{equip}</span>
      </div>
      {fishbone_html}
      <div class="o_pm_ai_rca_insight o_pm_fb_insight"><b>AI insight:</b> {insight}</div>
    </main>

    <aside class="o_pm_ai_rca_col o_pm_fb_col_right">
      <div class="o_pm_fb_sec_title"><span class="gear_ico">&#9881;</span> AI root cause intelligence</div>
      <div class="o_pm_ai_rca_result_top o_pm_fb_intel_top">
        <div class="o_pm_ai_rca_conf_ring">
          <svg viewBox="0 0 120 120" aria-hidden="true">
            <circle cx="60" cy="60" r="48" fill="none" stroke="#ecfdf5" stroke-width="11"/>
            <circle cx="60" cy="60" r="48" fill="none" stroke="{ring_color}" stroke-width="11"
              stroke-linecap="round" stroke-dasharray="301" stroke-dashoffset="{ring_offset}"
              transform="rotate(-90 60 60)"/>
          </svg>
          <div class="conf_txt">{confidence}%<small>Confidence</small></div>
        </div>
        <div class="o_pm_ai_rca_root">
          <b>Predicted root cause</b>
          <p>{root}</p>
        </div>
      </div>
      <div class="o_pm_ai_rca_stats o_pm_fb_impact_pair">
        <span class="stat-risk"><b>{downtime_label}</b><small>Downtime risk ({failure_risk}%)</small></span>
        <span class="stat-money"><b>{cost_label}</b><small>Financial impact (est.)</small></span>
      </div>
      {capa_block}
    </aside>
  </section>

  <footer class="o_pm_plant_footer o_pm_ai_rca_footer o_pm_fb_footer">
    <div class="footer_block mes">
      {_render_mes_steps(p.get("mes_active_step") or "escalate")}
    </div>
    <div class="footer_block impact">
      <div class="o_pm_fb_sec_title">Prod. impact (downtime)</div>
      <div class="impact_bars">{_render_impact_bars(failure_risk)}</div>
      <div class="impact_pct_label">{failure_risk}%</div>
    </div>
    <div class="footer_block alerts">
      <div class="o_pm_fb_sec_title">Live ops alerts</div>
      {_render_alerts(p.get("live_alerts"))}
    </div>
  </footer>
</div>
""")
