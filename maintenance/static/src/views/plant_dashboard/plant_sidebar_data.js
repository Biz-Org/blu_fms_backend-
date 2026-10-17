/** @odoo-module **/

/**
 * Plant Maintenance sidebar — grouped like the reference layout:
 * Dashboard | EQUIPMENT | MAINTENANCE | REPORTS | CONFIGURATION
 */
export const PLANT_SIDEBAR_SECTIONS = [
    {
        id: "dashboard",
        heading: "",
        children: [
            { id: "dash_home", label: "Dashboard", icon: "fa-th-large", xmlId: "maintenance.maintenance_plant_app_action" },
        ],
    },
    {
        id: "equipment",
        heading: "EQUIPMENT",
        children: [
            { id: "eq_list", label: "Equipment", icon: "fa-building", xmlId: "maintenance.maintenance_equipment_overview_action" },
        ],
    },
    {
        id: "maintenance",
        heading: "MAINTENANCE",
        children: [
            { id: "op_requests", label: "Maintenance Requests", icon: "fa-ticket", xmlId: "maintenance.hr_equipment_request_action" },
            {
                id: "pl_planning",
                label: "Maintenance Planning",
                icon: "fa-calendar-check-o",
                xmlId: "maintenance.maintenance_planning_action",
                keepRequestContext: true,
                workflowMethod: "action_workflow_plan_maintenance",
                formViewRef: "maintenance.maintenance_request_planning_form_view",
            },
            {
                id: "pl_manpower",
                label: "Manpower Assignment",
                icon: "fa-user",
                xmlId: "maintenance.maintenance_manpower_action",
                keepRequestContext: true,
                workflowMethod: "action_workflow_assign_technician",
                formViewRef: "maintenance.maintenance_request_manpower_form_view",
            },
            {
                id: "pl_spares",
                label: "Inventory & Spares",
                icon: "fa-cubes",
                xmlId: "maintenance.maintenance_inventory_spares_action",
                keepRequestContext: true,
                workflowMethod: "action_workflow_inventory_spares",
                formViewRef: "maintenance.maintenance_request_spares_form_view",
            },
            {
                id: "op_work_orders",
                label: "Work Orders",
                icon: "fa-cog",
                xmlId: "maintenance.maintenance_work_orders_action",
                keepRequestContext: true,
                workflowMethod: "action_workflow_open_execution",
                formViewRef: "maintenance.maintenance_request_execution_form_view",
            },
            {
                id: "op_workflow",
                label: "Workflow / Timeline",
                icon: "fa-clock-o",
                xmlId: "maintenance.maintenance_workflow_timeline_menu_action",
                keepRequestContext: true,
                workflowMethod: "action_workflow_open_timeline",
                formViewRef: "maintenance.maintenance_request_workflow_timeline_form_view",
            },
            { id: "op_calendar", label: "Maintenance Calendar", icon: "fa-calendar", xmlId: "maintenance.hr_equipment_request_action_cal" },
        ],
    },
    {
        id: "reports",
        heading: "REPORTS",
        children: [
            { id: "rp_analytics", label: "Analysis", icon: "fa-bar-chart", xmlId: "maintenance.maintenance_analytics_dashboard_action" },
            { id: "rp_reports", label: "Reports", icon: "fa-folder-open", xmlId: "maintenance.maintenance_request_action_reports" },
            { id: "rp_rul", label: "RUL & TOBM", icon: "fa-line-chart", xmlId: "maintenance.maintenance_rul_tobm_dashboard_action" },
            {
                id: "an_rca_mom",
                label: "Root Cause Analysis & MOM",
                icon: "fa-search",
                xmlId: "maintenance.maintenance_rca_action",
                keepRequestContext: true,
                workflowMethod: "action_workflow_open_rca_mom",
                formViewRef: "maintenance.maintenance_rca_case_form_view",
            },
            {
                id: "an_fishbone",
                label: "AI Fishbone RCA",
                icon: "fa-share-alt",
                xmlId: "maintenance.maintenance_plant_rca_action",
                keepRequestContext: true,
                workflowMethod: "action_workflow_open_fishbone",
                formViewRef: "maintenance.maintenance_plant_rca_form_view",
            },
            {
                id: "an_why",
                label: "AI Why-Why RCA",
                icon: "fa-question-circle",
                xmlId: "maintenance.maintenance_why_rca_action",
                keepRequestContext: true,
                workflowMethod: "action_workflow_open_why_why",
                formViewRef: "maintenance.maintenance_why_rca_form_view",
            },
            {
                id: "an_agile",
                label: "Agile Investigation",
                icon: "fa-sitemap",
                xmlId: "maintenance.maintenance_agile_rca_action",
                keepRequestContext: true,
                workflowMethod: "action_workflow_open_agile",
                formViewRef: "maintenance.maintenance_agile_rca_form_view",
            },
            {
                id: "an_capa",
                label: "AI CAPA Dashboard",
                icon: "fa-check-square-o",
                xmlId: "maintenance.maintenance_capa_rca_action",
                keepRequestContext: true,
                workflowMethod: "action_workflow_open_capa",
                formViewRef: "maintenance.maintenance_capa_rca_form_view",
            },
            {
                id: "an_nogo",
                label: "No-Go Dashboard",
                icon: "fa-ban",
                xmlId: "maintenance.maintenance_no_go_dashboard_action",
                keepRequestContext: true,
                workflowMethod: "action_workflow_open_nogo",
                formViewRef: "maintenance.maintenance_request_nogo_form_view",
            },
        ],
    },
    {
        id: "configuration",
        heading: "CONFIGURATION",
        children: [
            { id: "cfg_settings", label: "Settings", icon: "fa-cog", xmlId: "maintenance.action_maintenance_configuration" },
            { id: "cfg_teams", label: "Maintenance Teams", icon: "fa-users", xmlId: "maintenance.maintenance_team_action_settings" },
            { id: "cfg_categories", label: "Equipment Categories", icon: "fa-tags", xmlId: "maintenance.hr_equipment_category_action" },
            { id: "cfg_stages", label: "Maintenance Stages", icon: "fa-flag", xmlId: "maintenance.hr_equipment_stage_action" },
            { id: "cfg_activity", label: "Activity Types", icon: "fa-clock-o", xmlId: "maintenance.mail_activity_type_action_config_maintenance" },
        ],
    },
];

export function isMaintenanceApp(app) {
    if (!app) {
        return false;
    }
    if (app.xmlid === "maintenance.menu_maintenance_title") {
        return true;
    }
    const name = (app.name || "").toString().toLowerCase().trim();
    return name === "maintenance";
}
