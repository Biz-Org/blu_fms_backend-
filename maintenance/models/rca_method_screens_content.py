# -*- coding: utf-8 -*-
"""Separate full-page RCA method screens (Fishbone, Why-Why, Dependency, Failure Tree)."""

from markupsafe import Markup, escape

_METHOD_TABS = [
    ('fishbone', 'Fishbone Analysis'),
    ('why_why', 'Why-Why Analysis'),
    ('dependency', 'Dependency Mapping'),
    ('failure_tree', 'Failure Tree'),
]


def _method_tabs_html(active_method):
    tabs = []
    for key, label in _METHOD_TABS:
        cls = 'o_pm_ai_rca_method_tab is-active' if key == active_method else 'o_pm_ai_rca_method_tab'
        tabs.append(
            f'<span class="{cls}" data-rca-method="{key}" role="button" tabindex="0">'
            f'{escape(label)}</span>'
        )
    return Markup(f'<div class="o_pm_ai_rca_tabs o_pm_rca_method_tabs">{"".join(tabs)}</div>')


def _screen_shell(active_method, equip, body_html):
    return Markup(f"""
<div class="o_pm_rca_method_screen" data-rca-method="{escape(active_method)}">
  <div class="o_pm_rca_method_engine_head">
    <h3><span class="pulse-dot"></span> AI Root Cause Intelligence Engine</h3>
    <span class="o_pm_ai_rca_vehicle_select">🚛 {escape(equip)} ▾</span>
  </div>
  {_method_tabs_html(active_method)}
  <div class="o_pm_rca_method_body">{body_html}</div>
</div>
""")


def render_rca_why_why_screen(equipment_label=None, why_chain_html=None, root_cause=None):
    equip = equipment_label or 'Vehicle-01 (Truck-1) / SN-TRK-2024-014'
    chain = why_chain_html or Markup(
        '<div class="o_pm_rca_why_empty text-muted">Add 5 Why lines on the RCA &amp; MOM form below.</div>'
    )
    root = escape((root_cause or '').strip() or '—')
    body = Markup(f"""
  <div class="o_pm_rca_why_screen">
    <div class="o_pm_rca_why_screen_grid">
      <div class="o_pm_rca_why_main">
        <h4>Why–Why Analysis Chain</h4>
        <p class="o_pm_rca_method_hint">Each step asks &quot;why&quot; until the root cause is identified.</p>
        <div class="o_pm_rca_why_chain_wrap">{chain}</div>
      </div>
      <div class="o_pm_rca_why_side">
        <h4>Root Cause Summary</h4>
        <div class="o_pm_rca_why_root_box"><p>{root}</p></div>
        <div class="o_pm_rca_insight"><b>AI Insight:</b> Deepest &quot;why&quot; on the last step is treated as the primary root cause candidate.</div>
      </div>
    </div>
  </div>
""")
    return _screen_shell('why_why', equip, body)


def render_rca_dependency_screen(equipment_label=None, spare_lines=None):
    equip = equipment_label or 'Vehicle-01 (Truck-1) / SN-TRK-2024-014'
    rows = []
    for line in spare_lines or []:
        rows.append(
            f'<tr><td>{escape(line.get("name") or "")}</td>'
            f'<td>{escape(line.get("component") or "")}</td>'
            f'<td>{escape(line.get("stock") or "")}</td>'
            f'<td><span class="tag {escape(line.get("criticality") or "med")}">'
            f'{escape(line.get("criticality_label") or "Medium")}</span></td></tr>'
        )
    if not rows:
        rows = [
            '<tr><td>12V truck battery</td><td>Charging / starting</td><td>In Stock</td><td><span class="tag high">High</span></td></tr>',
            '<tr><td>Fuse / terminal kit</td><td>Starter circuit</td><td>In Stock</td><td><span class="tag med">Medium</span></td></tr>',
            '<tr><td>Starter motor</td><td>Crank system</td><td>3 days</td><td><span class="tag med">Medium</span></td></tr>',
        ]
    body = Markup(f"""
  <div class="o_pm_rca_dep_screen">
    <div class="o_pm_rca_dep_grid">
      <div class="o_pm_rca_dep_map">
        <h4>Component Dependency Map</h4>
        <div class="o_pm_rca_dep_nodes">
          <div class="node root">Engine Start System</div>
          <div class="link"></div>
          <div class="node">Battery → Terminals → Starter → Engine</div>
          <div class="link warn"></div>
          <div class="node hot">Battery (failed load test)</div>
        </div>
      </div>
      <div class="o_pm_rca_dep_table">
        <h4>Spare Parts &amp; Dependencies</h4>
        <table><thead><tr><th>Spare</th><th>Component</th><th>Stock</th><th>Criticality</th></tr></thead>
        <tbody>{Markup("".join(rows))}</tbody></table>
      </div>
    </div>
  </div>
""")
    return _screen_shell('dependency', equip, body)


def render_rca_failure_tree_screen(equipment_label=None, root_cause=None):
    equip = equipment_label or 'Vehicle-01 (Truck-1) / SN-TRK-2024-014'
    root = escape((root_cause or '').strip() or 'Top event: Equipment unavailable for dispatch')
    body = Markup(f"""
  <div class="o_pm_rca_ft_screen">
    <h4>Fault Tree Analysis</h4>
    <div class="o_pm_rca_ft_tree">
      <div class="ft_top">{root}</div>
      <div class="ft_or">OR</div>
      <div class="ft_row">
        <div class="ft_gate and">AND<br/><small>No crank</small></div>
        <div class="ft_gate and">AND<br/><small>No fuel delivery</small></div>
        <div class="ft_gate">OR<br/><small>Electrical fault</small></div>
      </div>
      <div class="ft_row leaves">
        <span>Battery voltage low</span>
        <span>Starter inoperative</span>
        <span>Empty tank</span>
        <span>Clogged filter</span>
        <span>Blown fuse</span>
      </div>
    </div>
    <div class="o_pm_rca_insight"><b>AI Insight:</b> Most probable cut set: battery branch under electrical fault gate.</div>
  </div>
""")
    return _screen_shell('failure_tree', equip, body)
