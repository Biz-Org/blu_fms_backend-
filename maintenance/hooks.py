# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

LEGACY_ROOT_MENU_XMLIDS = (
    'maintenance_reporting',
    'menu_m_request',
    'menu_maintenance_config',
)

PLANT_NAVBAR_MENU_XMLIDS = (
    ('menu_m_dashboard', 10),
    ('menu_equipment_form', 20),
    ('menu_m_operations', 30),
    ('menu_m_planning_root', 40),
    ('menu_m_analysis_root', 50),
    ('menu_m_reports', 60),
    ('menu_maintenance_configuration', 70),
)


def remove_legacy_root_menus(env):
    """Remove old top-level menus left over from earlier custom menu layouts."""
    data_rows = env['ir.model.data'].sudo().search([
        ('module', '=', 'maintenance'),
        ('model', '=', 'ir.ui.menu'),
        ('name', 'in', LEGACY_ROOT_MENU_XMLIDS),
    ])
    for row in data_rows:
        menu = env['ir.ui.menu'].sudo().browse(row.res_id).exists()
        xmlid = f'maintenance.{row.name}'
        if menu:
            menu.unlink()
            _logger.info('Removed legacy menu %s', xmlid)
        row.unlink()


def apply_plant_navbar_menu_order(env):
    """Keep top navbar:
    Dashboard | Equipment | Operations | Planning | Analysis | Reporting | Configuration
    """
    names = [name for name, _seq in PLANT_NAVBAR_MENU_XMLIDS]
    env['ir.model.data'].sudo().search([
        ('module', '=', 'maintenance'),
        ('model', '=', 'ir.ui.menu'),
        ('name', 'in', names),
    ]).write({'noupdate': False})
    Menu = env['ir.ui.menu'].sudo()
    root = env.ref('maintenance.menu_maintenance_title', raise_if_not_found=False)
    expected_names = {
        'menu_m_dashboard': 'Dashboard',
        'menu_equipment_form': 'Equipment',
        'menu_m_operations': 'Operations',
        'menu_m_planning_root': 'Planning',
        'menu_m_analysis_root': 'Analysis',
        'menu_m_reports': 'Reporting',
        'menu_maintenance_configuration': 'Configuration',
    }
    for xmlid_name, sequence in PLANT_NAVBAR_MENU_XMLIDS:
        menu = env.ref(f'maintenance.{xmlid_name}', raise_if_not_found=False)
        if not menu:
            continue
        vals = {
            'sequence': sequence,
            'active': True,
        }
        if root:
            vals['parent_id'] = root.id
        if xmlid_name in expected_names:
            vals['name'] = expected_names[xmlid_name]
        Menu.browse(menu.id).write(vals)

    extra = env.ref('maintenance.menu_m_dashboard_plant_app', raise_if_not_found=False)
    if extra:
        extra.write({'active': False})

    env.registry.clear_cache()


def _setup_rul_tobm_dashboard(env):
    env['maintenance.rul.tobm.dashboard'].setup_rul_tobm_dashboard_ui()


def _fix_rca_dashboard_setup(env):
    env['maintenance.request'].fix_rca_dashboard_setup()


def _fix_analytics_dashboard_defaults(env):
    dash = env.ref('maintenance.maintenance_analytics_dashboard_main', raise_if_not_found=False)
    if dash:
        dash.sudo().write({
            'analysis_period_days': 365,
            'fleet_vehicle_scope': True,
        })


def _configure_plant_demo_dashboards(env):
    """Point analytics & RUL at fleet vehicle demo data."""
    truck = env.ref('maintenance.equipment_vehicle_01_truck', raise_if_not_found=False)
    category = env.ref('maintenance.equipment_category_fleet_vehicles', raise_if_not_found=False)
    analytics = env.ref('maintenance.maintenance_analytics_dashboard_main', raise_if_not_found=False)
    if analytics:
        analytics.sudo().write({
            'analysis_period_days': 365,
            'fleet_vehicle_scope': True,
            'analytics_mode': 'live',
        })
    rul = env.ref('maintenance.maintenance_rul_tobm_dashboard_main', raise_if_not_found=False)
    if rul:
        vals = {
            'analysis_period_days': 365,
            'fleet_vehicle_scope': True,
        }
        if category:
            vals['category_id'] = category.id
        if truck and truck.exists():
            vals['equipment_id'] = truck.id
        rul.sudo().write(vals)


def _recompute_demo_request_dashboards(env):
    if 'maintenance.request' not in env:
        return
    Request = env['maintenance.request'].sudo()
    demo = Request.search([
        '|', ('work_order_sequence', 'ilike', 'WO-DEMO%'),
        ('equipment_id.serial_no', 'ilike', 'SN-DEMO%'),
    ])
    if demo and hasattr(demo, '_recompute_rca_dashboard_html_fields'):
        demo._recompute_rca_dashboard_html_fields()


def post_init_hook(env):
    """Plant demo: menus, dashboards, fleet data (no demo removal)."""
    remove_legacy_root_menus(env)
    apply_plant_navbar_menu_order(env)
    _setup_rul_tobm_dashboard(env)
    _fix_rca_dashboard_setup(env)
    _fix_analytics_dashboard_defaults(env)
    _configure_plant_demo_dashboards(env)
    env['maintenance.request'].ensure_demo_spare_planning_lines()
    env['maintenance.request'].restore_plant_demo_operational_screens()
    env['maintenance.rul.tobm.dashboard'].restore_maintenance_app()
