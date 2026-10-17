# -*- coding: utf-8 -*-
"""Remove or force-reload plant maintenance demo data."""

import logging

from odoo import api, models, tools

_logger = logging.getLogger(__name__)

# Delete children before parents (maintenance module xmlids).
_PLANT_DEMO_XMLIDS = (
    # Truck example — lines
    'request_example_truck_spare_battery',
    'request_example_truck_spare_fuse',
    'request_example_truck_doc_1',
    'request_example_truck_doc_2',
    'request_example_truck_manpower_1',
    'request_example_truck_manpower_2',
    'request_example_truck_rca_why_1',
    'request_example_truck_rca_why_2',
    'request_example_truck_rca_why_3',
    'request_example_truck_corrective_1',
    'request_example_truck_corrective_2',
    'request_example_truck_corrective_3',
  # Work orders
    'request_demo_history_truck_alternator_2025',
    'request_demo_history_flatbed_brakes_2025',
    'request_example_truck_not_starting',
    'request_example_flatbed_tire_sensor',
    'request_example_truck_pm_monthly',
    'request_example_truck_pm_spare_oil',
    'request_example_truck_pm_spare_filter',
    'request_example_truck_pm_manpower',
    'request_example_trailer_pm_spare_hub',
    'request_example_trailer_pm_spare_brake',
    'request_example_trailer_pm_spare_lights',
    'request_example_trailer_pm_annual',
    'request_example_forklift_hydraulic',
    'request_example_forklift_manpower',
    'request_example_flatbed_predictive',
    'request_example_flatbed_spare_tire',
    'request_example_truck_doc_3',
    'request_example_trailer_axle_nogo',
    'request_demo_history_forklift_hydraulic_2025',
    'request_rul_demo_v01_oil',
    'request_rul_demo_v02_followup',
    # Legacy maintenance.rca.case demo
    'maintenance_rca_case_truck_why_1',
    'maintenance_rca_case_truck_why_2',
    'maintenance_rca_case_truck_why_3',
    'maintenance_rca_case_truck_action_1',
    'maintenance_rca_case_truck_action_2',
    'maintenance_rca_case_truck_action_3',
    'maintenance_rca_case_truck_not_starting',
    # Equipment & team
    'equipment_vehicle_01_truck',
    'equipment_vehicle_03_flatbed',
    'equipment_vehicle_04_forklift',
    'equipment_vehicle_05_trailer',
    'equipment_category_fleet_vehicles',
    'maintenance_team_workflow_examples',
)

_SAFE_XMLID_DELETION_EXCLUSIONS = {
    # These records can be referenced by non-demo requests in live DBs.
    'equipment_category_fleet_vehicles',
    'maintenance_team_workflow_examples',
}

_FORCE_RELOAD_DATA_FILES = (
    'data/maintenance_plant_demo.xml',
    'data/maintenance_rul_tobm_demo_sync.xml',
    'data/maintenance_plant_demo_setup.xml',
)

# Vehicle-02 (Van) demo — delete children before parents.
_VEHICLE_02_DEMO_XMLIDS = (
    'request_example_van_spare_sensor',
    'request_example_van_manpower_1',
    'request_example_van_pm_spare_oil',
    'request_example_van_pm_spare_brake_fluid',
    'request_example_van_pm_spare_bulbs',
    'request_example_van_pm_manpower',
    'request_example_van_pm_quarterly',
    'request_example_van_brake_warning',
    'request_demo_history_van_compressor_2025',
    'request_rul_demo_v04_inspection',
    'request_rul_demo_v05_brake',
    'equipment_vehicle_02_van',
)


class MaintenanceDemoCleanup(models.AbstractModel):
    _name = 'maintenance.demo.cleanup'
    _description = 'Plant maintenance demo data removal / reload'

    @api.model
    def _unlink_maintenance_xmlid(self, name):
        imd = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'maintenance'),
            ('name', '=', name),
        ], limit=1)
        if not imd:
            return False
        record = self.env[imd.model].sudo().browse(imd.res_id).exists() if imd.res_id else False
        if record:
            record.unlink()
        imd.unlink()
        return True

    @api.model
    def _purge_orphan_demo_lines(self):
        """Remove child lines still linked to demo work orders."""
        Request = self.env['maintenance.request'].sudo()
        demo_req = Request.search([
            '|',
            ('work_order_sequence', 'ilike', 'WO-DEMO%'),
            ('equipment_id.serial_no', 'ilike', 'SN-DEMO%'),
        ])
        if not demo_req:
            return
        req_ids = demo_req.ids
        for model in (
            'maintenance.request.spare.line',
            'maintenance.request.manpower.line',
            'maintenance.request.document',
            'maintenance.request.rca.line',
            'maintenance.request.corrective.action',
        ):
            if model not in self.env:
                continue
            lines = self.env[model].sudo().search([('request_id', 'in', req_ids)])
            if lines:
                lines.unlink()

    @api.model
    def _unlink_request_tree(self, requests):
        """Delete maintenance requests and their child lines."""
        requests = requests.exists()
        if not requests:
            return 0
        req_ids = requests.ids
        for model in (
            'maintenance.request.spare.line',
            'maintenance.request.manpower.line',
            'maintenance.request.document',
            'maintenance.request.rca.line',
            'maintenance.request.corrective.action',
        ):
            if model not in self.env:
                continue
            self.env[model].sudo().search([('request_id', 'in', req_ids)]).unlink()
        count = len(req_ids)
        requests.unlink()
        return count

    @api.model
    def remove_vehicle_02_van_permanently(self):
        """Delete Vehicle-02 (Van), all linked requests, and demo XML ids."""
        Equipment = self.env['maintenance.equipment'].sudo()
        Request = self.env['maintenance.request'].sudo()
        deleted_requests = 0

        equipment = self.env.ref(
            'maintenance.equipment_vehicle_02_van',
            raise_if_not_found=False,
        )
        if not equipment:
            equipment = Equipment.search([
                ('serial_no', '=', 'SN-DEMO-VAN-02'),
            ], limit=1)
        if not equipment:
            equipment = Equipment.search([
                ('name', 'ilike', 'Vehicle-02'),
                ('name', 'ilike', 'Van'),
            ], limit=1)

        had_equipment = bool(equipment)
        if equipment:
            reqs = Request.with_context(active_test=False).search([
                ('equipment_id', '=', equipment.id),
            ])
            deleted_requests = self._unlink_request_tree(reqs)
            self.env['maintenance.rul.tobm.dashboard'].sudo().search([
                ('equipment_id', '=', equipment.id),
            ]).write({'equipment_id': False})
            equipment.unlink()
            _logger.info(
                'Removed Vehicle-02 (Van) and %s linked request(s).',
                deleted_requests,
            )
        else:
            # Equipment already gone — remove orphan requests still tagged to demo van.
            orphan_reqs = Request.with_context(active_test=False).search([
                '|',
                ('equipment_id.serial_no', '=', 'SN-DEMO-VAN-02'),
                ('equipment_id.name', 'ilike', 'Vehicle-02 (Van)'),
            ])
            deleted_requests = self._unlink_request_tree(orphan_reqs)
            had_equipment = False

        for xmlid in _VEHICLE_02_DEMO_XMLIDS:
            self._unlink_maintenance_xmlid(xmlid)

        return {
            'deleted_requests': deleted_requests,
            'equipment_removed': had_equipment,
        }

    @api.model
    def remove_plant_demo_data(self):
        """Drop fleet/workflow demo records."""
        removed = 0
        self._purge_orphan_demo_lines()
        for xmlid in _PLANT_DEMO_XMLIDS:
            if xmlid in _SAFE_XMLID_DELETION_EXCLUSIONS:
                continue
            if self._unlink_maintenance_xmlid(xmlid):
                removed += 1

        Equipment = self.env['maintenance.equipment'].sudo()
        Request = self.env['maintenance.request'].sudo()
        demo_equipment = Equipment.search([('serial_no', 'ilike', 'SN-DEMO%')])
        if demo_equipment:
            Request.search([('equipment_id', 'in', demo_equipment.ids)]).unlink()
            demo_equipment.unlink()
            removed += 1

        demo_requests_by_wo = Request.search([('work_order_sequence', 'ilike', 'WO-DEMO%')])
        if demo_requests_by_wo:
            demo_requests_by_wo.unlink()
            removed += 1

        if 'maintenance.rca.case' in self.env:
            legacy_cases = self.env['maintenance.rca.case'].sudo().search([
                '|',
                ('work_order_ref', 'ilike', 'WO-DEMO%'),
                ('equipment_label', 'ilike', 'SN-DEMO'),
            ])
            if legacy_cases:
                legacy_cases.unlink()
                removed += 1

        # Do not delete team/category by name here: users may link non-demo requests
        # to these records, which can cause FK errors during module upgrade.

        _logger.info('Plant maintenance demo cleanup finished (%s steps).', removed)
        return True

    @api.model
    def _reload_demo_xml_file(self, filename, idref):
        tools.convert_file(
            self.env(su=True),
            'maintenance',
            filename,
            idref,
            mode='update',
            noupdate=False,
            kind='data',
        )

    @api.model
    def _finalize_demo_on_all_screens(self):
        """Dashboards, Analysis, menus, and list visibility after XML reload."""
        env = self.env
        truck = env.ref('maintenance.equipment_vehicle_01_truck', raise_if_not_found=False)
        category = env.ref('maintenance.equipment_category_fleet_vehicles', raise_if_not_found=False)

        analytics = env.ref(
            'maintenance.maintenance_analytics_dashboard_main',
            raise_if_not_found=False,
        )
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

        env['maintenance.rul.tobm.dashboard'].setup_rul_tobm_dashboard_ui()
        env['maintenance.request'].fix_rca_dashboard_setup()

        demo = env['maintenance.request'].sudo().search([
            '|',
            ('work_order_sequence', 'ilike', 'WO-DEMO%'),
            ('equipment_id.serial_no', 'ilike', 'SN-DEMO%'),
        ])
        if demo and hasattr(demo, '_recompute_rca_dashboard_html_fields'):
            demo._recompute_rca_dashboard_html_fields()

        env['maintenance.request'].restore_plant_demo_operational_screens()
        env['maintenance.rul.tobm.dashboard'].restore_maintenance_app()

        try:
            from odoo.addons.maintenance.hooks import apply_plant_navbar_menu_order
            apply_plant_navbar_menu_order(env)
        except ImportError:
            env['maintenance.rul.tobm.dashboard'].apply_plant_navbar_menu_order()

        env.registry.clear_cache()

    @api.model
    def force_reload_plant_demo_data(self):
        """Wipe SN-DEMO / WO-DEMO data and reload from XML (all Maintenance screens)."""
        _logger.info('Force reload: plant maintenance demo starting...')
        self.remove_plant_demo_data()

        self.env['ir.model.data'].sudo().search([
            ('module', '=', 'maintenance'),
            ('name', 'in', list(_PLANT_DEMO_XMLIDS)),
        ]).write({'noupdate': False})

        idref = {}
        for filename in _FORCE_RELOAD_DATA_FILES:
            _logger.info('Force reload: loading maintenance/%s', filename)
            self._reload_demo_xml_file(filename, idref)

        self._finalize_demo_on_all_screens()

        eq_count = self.env['maintenance.equipment'].sudo().search_count([
            ('serial_no', 'ilike', 'SN-DEMO%'),
        ])
        wo_count = self.env['maintenance.request'].sudo().search_count([
            ('work_order_sequence', 'ilike', 'WO-DEMO%'),
        ])
        _logger.info(
            'Force reload complete: %s demo vehicles, %s demo work orders.',
            eq_count,
            wo_count,
        )
        if not eq_count:
            _logger.error(
                'Demo reload produced no SN-DEMO equipment — check maintenance_plant_demo.xml.'
            )
            return False
        return True
