/** @odoo-module **/

/** Injected on mount — full-width mockup layout (valid selectors). */
export const RUL_TOBM_STYLE_ID = "maintenance_rul_tobm_inline_v1126";

const S = ".o_maint_rul_client, .o_maint_rul_root, .o_maint_rul_dashboard_host";
const A = ".o_action.o_maint_rul_action, .o_action:has(> .o_maint_rul_client), .o_action:has(.o_maint_rul_client)";

export const RUL_TOBM_INLINE_CSS = `
/* Fullscreen shell — height accounts for Odoo top navbar */
html.o_maint_rul_lock_scroll {
    height: 100%;
}
body.o_maint_rul_fullscreen_body {
    --maint-rul-nav-offset: 46px;
    --maint-rul-strip-height: 46px;
    overflow: hidden !important;
    height: 100%;
}
body.o_maint_rul_fullscreen_body .o_web_client {
    overflow: hidden !important;
    height: 100%;
    width: 100% !important;
    max-width: 100% !important;
}
body.o_maint_rul_fullscreen_body .o_action_manager,
body.o_maint_rul_fullscreen_body .o_maint_rul_action_manager {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 1 auto !important;
    min-height: 0 !important;
    min-width: 0 !important;
    width: 100% !important;
    max-width: none !important;
    margin: 0 !important;
    padding: 0 !important;
    height: calc(100vh - var(--maint-rul-nav-offset, 46px)) !important;
    max-height: calc(100vh - var(--maint-rul-nav-offset, 46px)) !important;
    overflow: hidden !important;
    background: #f4f7fb !important;
}
.o_form_view.o_maint_rul_fullscreen_form > header,
.o_maint_rul_fullscreen_form > header,
.o_maint_rul_fullscreen_form .o_maint_rul_controls {
    display: none !important;
}
${A} {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 1 auto !important;
    align-self: stretch !important;
    min-height: 0 !important;
    min-width: 0 !important;
    width: 100% !important;
    max-width: none !important;
    margin: 0 !important;
    padding: 0 !important;
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
    background: #f4f7fb !important;
    box-sizing: border-box;
}
${A} .o_control_panel,
${A} .o_control_panel_main,
${A} .o_control_panel_breadcrumbs,
${A} .o_cp_action_menus {
    display: none !important;
}
${A} .o_content,
${A} .o_form_view_container {
    flex: 1 1 auto !important;
    min-height: 0 !important;
    min-width: 0 !important;
    width: 100% !important;
    max-width: 100% !important;
    overflow: hidden !important;
    padding: 0 !important;
    background: #f4f7fb !important;
}
/* Form view on wide screens: cancel side-by-side (chatter) layout */
.o_form_view.o_maint_rul_fullscreen_form.o_xxl_form_view {
    flex-flow: column nowrap !important;
    width: 100% !important;
    max-width: 100% !important;
}
.o_form_view.o_maint_rul_fullscreen_form.o_xxl_form_view .o_form_view_container,
.o_form_view.o_maint_rul_fullscreen_form.o_xxl_form_view .o_form_sheet_bg,
.o_form_view.o_maint_rul_fullscreen_form .o_form_renderer {
    width: 100% !important;
    max-width: 100% !important;
    flex: 1 1 auto !important;
    margin: 0 !important;
}
.o_form_view.o_maint_rul_fullscreen_form .o-mail-Form-chatter,
.o_form_view.o_maint_rul_fullscreen_form .o-mail-ChatterContainer {
    display: none !important;
    width: 0 !important;
    min-width: 0 !important;
    flex: 0 0 0 !important;
}

/* Page root */
${S} {
    flex: 1 1 auto;
    min-height: 0;
    height: 100%;
    width: 100%;
    max-width: 100%;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    background: #f8f9fa;
}
${S} .o_maint_rul_loading,
${S} .o_maint_rul_error {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 32px;
    text-align: center;
    color: #475569;
    font-size: 14px;
}
${S} .o_maint_rul_dashboard_host {
    flex: 1 1 auto;
    min-height: 0;
    height: 100%;
    width: 100%;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}

/* Full page: Odoo strip + dashboard body */
${S} .o_maint_rul_fullpage {
    flex: 1 1 auto;
    min-height: 0;
    height: 100%;
    width: 100%;
    max-width: none;
    margin: 0;
    padding: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    background: #f4f7fb;
    font-family: "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
    color: #0f172a;
    text-transform: none;
}
${S} .o_maint_rul_odoo_strip {
    display: none !important;
}
${S} .o_maint_rul_odoo_strip--legacy {
    flex: 0 0 var(--maint-rul-strip-height, 46px);
    min-height: var(--maint-rul-strip-height, 46px);
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 0 16px;
    background: #fff;
    border-bottom: 1px solid #d8dde6;
    box-shadow: 0 1px 0 rgba(15, 23, 42, 0.04);
    box-sizing: border-box;
    z-index: 3;
}
${S} .o_maint_rul_odoo_strip_left {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    font-size: 14px;
    font-weight: 600;
    color: #374151;
}
${S} .o_maint_rul_bc_root {
    color: #714b67;
}
${S} .o_maint_rul_bc_sep {
    color: #94a3b8;
    font-weight: 400;
}
${S} .o_maint_rul_bc_current {
    color: #111827;
}
${S} .o_maint_rul_odoo_teams_btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 600;
    color: #374151;
    background: #fff;
    border: 1px solid #d8dde6;
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;
    white-space: nowrap;
}
${S} .o_maint_rul_odoo_teams_btn:hover {
    background: #f8fafc;
    border-color: #94a3b8;
}
${S} .o_maint_rul_viewport {
    flex: 1 1 auto;
    min-height: 0;
    height: 100%;
    width: 100%;
    max-width: none;
    overflow: hidden;
    display: grid !important;
    grid-template-rows: auto auto minmax(0, 1fr) !important;
    grid-template-columns: 1fr !important;
    gap: 8px;
    padding: 12px 16px 10px;
    box-sizing: border-box;
    background: #f8f9fa;
    text-transform: none;
}

/* Header card */
${S} .o_maint_rul_header {
    position: relative;
    flex-shrink: 0;
    margin: 0 !important;
    padding: 10px 12px !important;
    padding-right: 68px !important;
    background: #fff !important;
    border: 1px solid #e8edf4 !important;
    border-radius: 14px !important;
    box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06) !important;
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) auto !important;
    grid-template-rows: auto !important;
    align-items: start !important;
    gap: 12px 20px !important;
    width: 100%;
    box-sizing: border-box;
}
${S} .o_maint_rul_header_text {
    min-width: 0;
    grid-column: 1;
}
${S} .o_maint_rul_header_text h1 {
    font-size: 20px !important;
    font-weight: 800 !important;
    letter-spacing: -0.03em;
    margin: 0 0 4px !important;
    color: #0f172a !important;
    line-height: 1.15 !important;
}
${S} .o_maint_rul_header_text > p {
    margin: 0 !important;
    font-size: 14px !important;
    color: #64748b !important;
    line-height: 1.45 !important;
}
${S} .o_maint_rul_meta {
    display: block !important;
    margin: 8px 0 0 !important;
    font-size: 12px !important;
    color: #94a3b8 !important;
}
${S} .o_maint_rul_pills {
    grid-column: 2;
    grid-row: 1;
    display: flex !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    justify-content: flex-end !important;
    gap: 8px !important;
    flex-shrink: 0;
    align-self: start;
}
${S} .o_maint_rul_pill {
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    padding: 8px 14px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    border-radius: 999px !important;
    border: 1px solid #dde4ee !important;
    background: #fff !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05) !important;
    color: #334155 !important;
    white-space: nowrap !important;
}
${S} .o_maint_rul_pill--scope {
    border-color: #bfdbfe !important;
    background: linear-gradient(180deg, #f8fbff 0%, #eff6ff 100%) !important;
    color: #1d4ed8 !important;
}
${S} .o_maint_rul_pill--badge {
    border-color: #86efac !important;
    background: linear-gradient(180deg, #f0fdf4 0%, #dcfce7 100%) !important;
    color: #166534 !important;
    font-size: 10px !important;
    font-weight: 800 !important;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}
${S} .o_maint_rul_live_corner {
    position: absolute !important;
    top: 14px !important;
    right: 16px !important;
    z-index: 2;
    margin: 0 !important;
}
${S} .o_maint_rul_live_dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #22c55e;
    box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.3);
    flex-shrink: 0;
}
${S} .o_maint_rul_scope_dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #3b82f6;
    display: inline-block;
    flex-shrink: 0;
}
${S} .o_maint_rul_filter_drop {
    position: relative;
    flex-shrink: 0;
}
${S} .o_maint_rul_pill--click {
    cursor: pointer;
    font-family: inherit;
}
${S} .o_maint_rul_drop_menu,
${S} .o_maint_rul_eq_menu {
    position: absolute;
    right: 0;
    top: calc(100% + 6px);
    z-index: 1050;
    min-width: 220px;
    max-height: 280px;
    overflow-y: auto;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.14);
    padding: 6px;
}
${S} .o_maint_rul_drop_item,
${S} .o_maint_rul_eq_option {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 12px;
    border: none;
    border-radius: 8px;
    background: transparent;
    font-size: 13px;
    font-weight: 600;
    color: #334155;
    text-align: left;
    cursor: pointer;
    font-family: inherit;
}
${S} .o_maint_rul_drop_item:hover,
${S} .o_maint_rul_drop_item.is-active,
${S} .o_maint_rul_eq_option:hover,
${S} .o_maint_rul_eq_option.is-active {
    background: #eff6ff;
    color: #1d4ed8;
}

/* KPI row — equal width, full bleed */
${S} .o_maint_rul_kpis {
    margin: 0 !important;
    width: 100% !important;
    display: grid !important;
    grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
    gap: 8px !important;
    align-items: stretch !important;
}
${S} .o_maint_rul_kpi {
    margin: 0 !important;
    padding: 0 !important;
    min-width: 0 !important;
    background: #fff !important;
    border: 1px solid #e8edf4 !important;
    border-radius: 12px !important;
    border-top-width: 3px !important;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.07) !important;
    overflow: hidden;
}
${S} .o_maint_rul_kpi--rul { border-top-color: #2563eb !important; }
${S} .o_maint_rul_kpi--thresh { border-top-color: #f97316 !important; }
${S} .o_maint_rul_kpi--tobm { border-top-color: #22c55e !important; }
${S} .o_maint_rul_kpi--critical { border-top-color: #ef4444 !important; }
${S} .o_maint_rul_kpi_inner {
    padding: 8px 10px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 8px !important;
    height: 100%;
    box-sizing: border-box;
}
${S} .o_maint_rul_kpi_text {
    min-width: 0;
    flex: 1 1 auto;
}
${S} .o_maint_rul_kpi_label {
    font-size: 10px !important;
    font-weight: 700 !important;
    color: #64748b !important;
    text-transform: none !important;
    letter-spacing: 0.02em;
    margin: 0 0 2px !important;
}
${S} .o_maint_rul_kpi_value,
${S} .o_maint_rul_kpi_desc {
    text-transform: none !important;
}
${S} .o_maint_rul_kpi_value {
    font-size: 22px !important;
    font-weight: 800 !important;
    line-height: 1.05 !important;
    color: #0f172a !important;
}
${S} .o_maint_rul_kpi--critical .o_maint_rul_kpi_value {
    font-size: 17px !important;
    line-height: 1.15 !important;
    color: #0f172a !important;
    word-break: break-word;
}
${S} .o_maint_rul_kpi_desc {
    font-size: 10px !important;
    color: #64748b !important;
    margin: 2px 0 0 !important;
    line-height: 1.25 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
${S} .o_maint_rul_kpi_icon {
    width: 34px !important;
    height: 34px !important;
    font-size: 15px !important;
    border-radius: 10px !important;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
${S} .o_maint_rul_kpi--rul .o_maint_rul_kpi_icon {
    background: #dbeafe !important;
    color: #2563eb !important;
}
${S} .o_maint_rul_kpi--thresh .o_maint_rul_kpi_icon {
    background: #ffedd5 !important;
    color: #ea580c !important;
}
${S} .o_maint_rul_kpi--tobm .o_maint_rul_kpi_icon {
    background: #dcfce7 !important;
    color: #16a34a !important;
}
${S} .o_maint_rul_kpi--critical .o_maint_rul_kpi_icon {
    background: #fee2e2 !important;
    color: #dc2626 !important;
}

/* Chart card — fills remaining screen height */
${S} .o_maint_rul_card--detail {
    margin: 0 !important;
    min-height: 0 !important;
    width: 100% !important;
    overflow: hidden !important;
    padding: 12px 14px 8px !important;
    background: #fff !important;
    border: 1px solid #e8edf4 !important;
    border-radius: 16px !important;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.07) !important;
    display: flex !important;
    flex-direction: column !important;
    flex: 1 1 auto !important;
    min-height: 0 !important;
    gap: 0 !important;
    padding: 14px 16px 10px !important;
    box-sizing: border-box;
}
${S} .o_maint_rul_card--detail .o_maint_rul_detail_head,
${S} .o_maint_rul_card--detail .o_maint_rul_phase_stack {
    flex-shrink: 0;
}
${S} .o_maint_rul_card--detail .o_maint_rul_phase_stack {
    margin: 0 0 8px !important;
}
${S} .o_maint_rul_card--detail .o_maint_rul_chart_wrap {
    flex: 1 1 auto !important;
    min-height: 0 !important;
}
${S} .o_maint_rul_card--detail .o_maint_rul_legend {
    flex-shrink: 0 !important;
    margin-top: 10px !important;
}
${S} .o_maint_rul_detail_head {
    margin: 0 !important;
    display: flex !important;
    flex-wrap: nowrap !important;
    justify-content: space-between !important;
    align-items: flex-start !important;
    gap: 16px !important;
    width: 100%;
}
${S} .o_maint_rul_detail_titles {
    min-width: 0;
    flex: 1 1 auto;
}
${S} .o_maint_rul_detail_titles h2 {
    font-size: 16px !important;
    font-weight: 800 !important;
    margin: 0 0 4px !important;
    color: #0f172a !important;
    text-transform: none !important;
    white-space: normal !important;
    line-height: 1.35 !important;
}
${S} .o_maint_rul_detail_titles p {
    margin: 0 !important;
    font-size: 13px !important;
    color: #64748b !important;
    text-transform: none !important;
    line-height: 1.4 !important;
}
${S} .o_maint_rul_eq_select {
    position: relative;
    flex-shrink: 0;
    max-width: 300px;
}
${S} .o_maint_rul_eq_select_btn {
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    padding: 8px 12px !important;
    font-size: 12px !important;
    border: 1px solid #dde4ee !important;
    border-radius: 8px !important;
    background: #fff !important;
    cursor: pointer;
    font-family: inherit;
}
${S} .o_maint_rul_phase_stack {
    width: 100% !important;
    height: 28px !important;
    margin: 0 !important;
    border-radius: 10px !important;
    overflow: hidden;
    display: flex !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    color: #fff !important;
    box-shadow: 0 2px 6px rgba(15, 23, 42, 0.12);
}
${S} .o_maint_rul_phase_seg {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-width: 0;
    padding: 0 8px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
${S} .o_maint_rul_phase_seg--rul { background: #22c55e !important; }
${S} .o_maint_rul_phase_seg--tobm { background: #f97316 !important; }
${S} .o_maint_rul_phase_seg--maint { background: #2563eb !important; }

/* Chart — full width inside detail card (no inner box) */
${S} .o_maint_rul_chart_wrap {
    margin: 0 !important;
    min-height: 0 !important;
    width: 100% !important;
    overflow: visible !important;
    padding: 0 !important;
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    display: block !important;
    box-sizing: border-box;
}
${S} .o_maint_rul_chart_svg {
    width: 100% !important;
    max-width: 100% !important;
    height: auto !important;
    min-height: 340px !important;
    aspect-ratio: 920 / 380 !important;
    display: block !important;
}
${S} .o_maint_rul_legend {
    flex-shrink: 0 !important;
}
${S} .o_maint_rul_pill--teams {
    cursor: pointer;
    font-family: inherit;
    border-color: #c7d2fe !important;
    background: #f5f7ff !important;
    color: #4338ca !important;
}
${S} .o_maint_rul_legend {
    margin: 0 !important;
    padding: 0 !important;
    display: flex !important;
    flex-wrap: wrap !important;
    justify-content: center !important;
    gap: 12px 20px !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    color: #475569 !important;
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    width: 100%;
    box-sizing: border-box;
}
${S} .o_maint_rul_legend span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
${S} .o_maint_rul_legend_dot {
    width: 10px;
    height: 10px;
    border-radius: 3px;
    display: inline-block;
    flex-shrink: 0;
}
${S} .o_maint_rul_legend_dot--rul { background: #22c55e; }
${S} .o_maint_rul_legend_dot--tobm { background: #f97316; }
${S} .o_maint_rul_legend_dot--maint { background: #2563eb; }
${S} .o_maint_rul_legend_line {
    width: 18px;
    height: 0;
    border-top: 2px solid #2563eb;
    display: inline-block;
}
${S} .o_maint_rul_legend_line--curve {
    border-top-color: #2563eb;
    border-top-style: solid;
}
${S} .o_maint_rul_legend_line--fail {
    border-top-color: #ef4444;
    border-top-style: dashed;
}

@media (max-width: 1100px) {
    ${S} .o_maint_rul_kpis {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }
    ${S} .o_maint_rul_header {
        grid-template-columns: 1fr !important;
        padding-right: 20px !important;
    }
    ${S} .o_maint_rul_pills {
        grid-column: 1 !important;
        flex-wrap: wrap !important;
        justify-content: flex-start !important;
    }
    ${S} .o_maint_rul_live_corner {
        position: static !important;
        margin-left: auto !important;
    }
}

/* act_window embed: purple menu bar + full scrollable dashboard (no clip) */
.o_form_view.o_maint_rul_pm_form .o_form_view_container,
.o_form_view.o_maint_rul_pm_form .o_form_sheet_bg,
.o_form_view.o_maint_rul_pm_form .o_form_sheet,
.o_form_view.o_maint_rul_pm_form .o_maint_rul_dashboard_wrap,
.o_form_view.o_maint_rul_pm_form .o_maint_rul_dashboard_wrap .o_field_widget {
    overflow: visible !important;
    max-height: none !important;
    height: auto !important;
    flex: none !important;
}
.o_action.o_pm_rca_action:has(.o_maint_rul_pm_form) .o_content,
.o_action.o_pm_rca_action:has(.o_maint_rul_pm_form) .o_form_view_container {
    overflow: visible !important;
    height: auto !important;
    max-height: none !important;
    min-height: calc(100vh - var(--maint-rul-nav-offset, 46px)) !important;
}
.o_maint_rul_client.o_maint_rul_embedded {
    height: auto !important;
    max-height: none !important;
    min-height: calc(100vh - var(--maint-rul-nav-offset, 46px)) !important;
    overflow: visible !important;
}
.o_maint_rul_client.o_maint_rul_embedded .o_maint_rul_dashboard,
.o_maint_rul_client.o_maint_rul_embedded .o_maint_rul_fullpage {
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
    flex: none !important;
}
.o_maint_rul_client.o_maint_rul_embedded .o_maint_rul_viewport {
    height: auto !important;
    min-height: 560px !important;
    max-height: none !important;
    overflow: visible !important;
    flex: none !important;
}
.o_maint_rul_client.o_maint_rul_embedded .o_maint_rul_card--detail {
    min-height: 360px !important;
}
`;

export function ensureRulTobmInlineStyles() {
    let el = document.getElementById(RUL_TOBM_STYLE_ID);
    if (!el) {
        el = document.createElement("style");
        el.id = RUL_TOBM_STYLE_ID;
        el.type = "text/css";
        document.head.appendChild(el);
    }
    el.textContent = RUL_TOBM_INLINE_CSS;
    [
        "maintenance_rul_tobm_inline_v1086",
        "maintenance_rul_tobm_inline_v1087",
        "maintenance_rul_tobm_inline_v1088",
        "maintenance_rul_tobm_inline_v1089",
        "maintenance_rul_tobm_inline_v1090",
        "maintenance_rul_tobm_inline_v1091",
        "maintenance_rul_tobm_inline_v1092",
        "maintenance_rul_tobm_inline_v1093",
        "maintenance_rul_tobm_inline_v1094",
        "maintenance_rul_tobm_inline_v1095",
        "maintenance_rul_tobm_inline_v1096",
        "maintenance_rul_tobm_inline_v1097",
        "maintenance_rul_tobm_inline_v1098",
        "maintenance_rul_tobm_inline_v1099",
        "maintenance_rul_tobm_inline_v1100",
        "maintenance_rul_tobm_inline_v1101",
        "maintenance_rul_tobm_inline_v1102",
        "maintenance_rul_tobm_inline_v1109",
    ].forEach((id) => {
        document.getElementById(id)?.remove();
    });
}
