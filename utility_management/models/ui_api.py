# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.exceptions import AccessError

SCREEN_IDS = (
    'utility_dashboard',
    'utility_meter_inventory',
    'utility_electricity_monitoring',
    'utility_water_monitoring',
    'utility_gas_monitoring',
    'utility_power_source',
    'utility_overall_consumption',
    'utility_meter_reading',
    'utility_leak_detection',
    'utility_alerts',
    'utility_reports',
    'utility_settings',
)


class UtilityManagementUiApi(models.AbstractModel):
    _name = 'utility.management.ui.api'
    _description = 'Utility Management UI API'

    def _require_utility_user(self):
        user = self.env.user
        if not user or user._is_public():
            raise AccessError('Utility Management requires an authenticated user.')
        if not user.has_group('utility_management.group_utility_staff'):
            raise AccessError('Only Utility Management users can access this module.')

    @api.model
    def health(self):
        """Foundation ping. No business data and no secrets."""
        self._require_utility_user()
        user = self.env.user
        return {
            'ok': True,
            'module': 'utility_management',
            'version': '18.0.1.0.0',
            'screens': list(SCREEN_IDS),
            'is_utility_staff': user.has_group('utility_management.group_utility_staff'),
            'is_facility_manager': user.has_group(
                'utility_management.group_facility_manager'
            ),
        }

    def _services(self):
        from odoo.addons.utility_management.services.alert_service import AlertService
        from odoo.addons.utility_management.services.consumption_service import ConsumptionService
        from odoo.addons.utility_management.services.electricity_service import ElectricityService
        from odoo.addons.utility_management.services.gas_service import GasService
        from odoo.addons.utility_management.services.leak_service import LeakService
        from odoo.addons.utility_management.services.meter_service import MeterService
        from odoo.addons.utility_management.services.power_source_service import PowerSourceService
        from odoo.addons.utility_management.services.reading_service import ReadingService
        from odoo.addons.utility_management.services.report_service import ReportService
        from odoo.addons.utility_management.services.water_service import WaterService
        return {
            'alert': AlertService(self.env),
            'consumption': ConsumptionService(self.env),
            'electricity': ElectricityService(self.env),
            'gas': GasService(self.env),
            'leak': LeakService(self.env),
            'meter': MeterService(self.env),
            'power': PowerSourceService(self.env),
            'reading': ReadingService(self.env),
            'report': ReportService(self.env),
            'water': WaterService(self.env),
        }

    @api.model
    def get_dashboard(self, filters=None):
        self._require_utility_user()
        return self._services()['meter'].dashboard(filters)

    @api.model
    def list_meters(self, filters=None):
        self._require_utility_user()
        return self._services()['meter'].list(filters)

    @api.model
    def get_meter(self, meter_id):
        self._require_utility_user()
        return self._services()['meter'].detail(meter_id)

    @api.model
    def save_meter(self, values):
        self._require_utility_user()
        service = self._services()['meter']
        if values and values.get('id'):
            return service.write(values['id'], values)
        return service.create(values)

    @api.model
    def set_meter_status(self, meter_id, status, values=None):
        self._require_utility_user()
        values = values or {}
        return self._services()['meter'].set_status(
            meter_id,
            status,
            health=values.get('health'),
            error_message=values.get('error_message'),
        )

    @api.model
    def test_meter_connection(self, meter_id):
        self._require_utility_user()
        return self._services()['meter'].test_connection(meter_id)

    @api.model
    def list_connectivity(self, meter_id):
        self._require_utility_user()
        return self._services()['meter'].connectivity(meter_id)

    @api.model
    def get_electricity_overview(self, filters=None):
        self._require_utility_user()
        return self._services()['electricity'].overview(filters)

    @api.model
    def get_electricity_buildings(self, filters=None):
        self._require_utility_user()
        return self._services()['electricity'].buildings(filters)

    @api.model
    def get_electricity_trends(self, filters=None):
        self._require_utility_user()
        return self._services()['electricity'].trends(filters)

    @api.model
    def get_water_overview(self, filters=None):
        self._require_utility_user()
        return self._services()['water'].overview(filters)

    @api.model
    def get_water_tanks(self, filters=None):
        self._require_utility_user()
        return self._services()['water'].tanks(filters)

    @api.model
    def get_water_trends(self, filters=None):
        self._require_utility_user()
        return self._services()['water'].trends(filters)

    @api.model
    def get_gas_overview(self, filters=None):
        self._require_utility_user()
        return self._services()['gas'].overview(filters)

    @api.model
    def get_gas_safety(self, filters=None):
        self._require_utility_user()
        return self._services()['gas'].safety(filters)

    @api.model
    def get_gas_trends(self, filters=None):
        self._require_utility_user()
        return self._services()['gas'].trends(filters)

    @api.model
    def get_power_overview(self, filters=None):
        self._require_utility_user()
        return self._services()['power'].overview(filters)

    @api.model
    def list_power_sources(self, filters=None):
        self._require_utility_user()
        return self._services()['power'].list(filters)

    @api.model
    def get_power_history(self, source_id):
        self._require_utility_user()
        return self._services()['power'].history(source_id)

    @api.model
    def transition_power_source(self, source_id, status, values=None):
        self._require_utility_user()
        return self._services()['power'].transition(source_id, status, values)

    @api.model
    def get_consumption_overview(self, filters=None):
        self._require_utility_user()
        return self._services()['consumption'].overview(filters)

    @api.model
    def get_consumption_comparison(self, filters=None):
        self._require_utility_user()
        return self._services()['consumption'].comparison(filters)

    @api.model
    def get_consumption_analysis(self, filters=None):
        self._require_utility_user()
        return self._services()['consumption'].analysis(filters)

    @api.model
    def list_readings(self, filters=None):
        self._require_utility_user()
        return self._services()['reading'].list(filters)

    @api.model
    def get_reading(self, reading_id):
        self._require_utility_user()
        return self._services()['reading'].dto(
            self._services()['reading']._reading(reading_id)
        )

    @api.model
    def create_reading(self, values):
        self._require_utility_user()
        return self._services()['reading'].create_manual(values)

    @api.model
    def verify_reading(self, reading_id):
        self._require_utility_user()
        return self._services()['reading'].verify(reading_id)

    @api.model
    def invalidate_reading(self, reading_id, reason):
        self._require_utility_user()
        return self._services()['reading'].invalidate(reading_id, reason)

    @api.model
    def correct_reading(self, reading_id, values):
        self._require_utility_user()
        return self._services()['reading'].correct(reading_id, values)

    @api.model
    def attach_reading_photo(self, reading_id, values):
        self._require_utility_user()
        values = values or {}
        return self._services()['reading'].attach_photo(
            reading_id,
            values.get('datas'),
            values.get('filename'),
            values.get('mimetype'),
        )

    @api.model
    def get_leak_overview(self, filters=None):
        self._require_utility_user()
        return self._services()['leak'].overview(filters)

    @api.model
    def list_leaks(self, filters=None):
        self._require_utility_user()
        return self._services()['leak'].list(filters)

    @api.model
    def get_leak(self, leak_id):
        self._require_utility_user()
        return self._services()['leak'].dto(self._services()['leak']._leak(leak_id))

    @api.model
    def create_leak(self, values):
        self._require_utility_user()
        return self._services()['leak'].create(values)

    @api.model
    def assign_leak(self, leak_id, user_id):
        self._require_utility_user()
        return self._services()['leak'].assign(leak_id, user_id)

    @api.model
    def transition_leak(self, leak_id, state):
        self._require_utility_user()
        return self._services()['leak'].transition(leak_id, state)

    @api.model
    def add_leak_action(self, leak_id, values):
        self._require_utility_user()
        return self._services()['leak'].add_action(leak_id, values)

    @api.model
    def get_alert_overview(self, filters=None):
        self._require_utility_user()
        return self._services()['alert'].overview(filters)

    @api.model
    def list_alerts(self, filters=None):
        self._require_utility_user()
        return self._services()['alert'].list(filters)

    @api.model
    def get_alert(self, alert_id):
        self._require_utility_user()
        return self._services()['alert'].dto(self._services()['alert']._alert(alert_id))

    @api.model
    def acknowledge_alert(self, alert_id):
        self._require_utility_user()
        return self._services()['alert'].transition(alert_id, 'acknowledged')

    @api.model
    def start_alert(self, alert_id):
        self._require_utility_user()
        return self._services()['alert'].transition(alert_id, 'in_progress')

    @api.model
    def resolve_alert(self, alert_id, note=None):
        self._require_utility_user()
        return self._services()['alert'].transition(alert_id, 'resolved', {'resolution_note': note})

    @api.model
    def close_alert(self, alert_id):
        self._require_utility_user()
        return self._services()['alert'].transition(alert_id, 'closed')

    @api.model
    def list_alert_rules(self, filters=None):
        self._require_utility_user()
        return self._services()['alert'].list_rules(filters)

    @api.model
    def save_alert_rule(self, values):
        self._require_utility_user()
        return self._services()['alert'].save_rule(values)

    @api.model
    def get_report_overview(self):
        self._require_utility_user()
        return self._services()['report'].overview()

    @api.model
    def list_report_definitions(self):
        self._require_utility_user()
        return self._services()['report'].list_definitions()

    @api.model
    def save_report_definition(self, values):
        self._require_utility_user()
        return self._services()['report'].save_definition(values)

    @api.model
    def run_report(self, definition_id, export_format, values=None):
        self._require_utility_user()
        return self._services()['report'].run(definition_id, export_format, values)

    @api.model
    def download_private_file(self, attachment_id):
        """Return a private attachment after the parent record is readable."""
        self._require_utility_user()
        attachment = self.env['ir.attachment'].browse(attachment_id)
        if not attachment.exists() or attachment.public:
            raise AccessError('This file is not available.')
        if attachment.res_model not in (
            'utility.management.report.run',
            'utility.management.reading',
        ):
            raise AccessError('This file is not available.')
        parent = self.env[attachment.res_model].browse(attachment.res_id)
        if not parent.exists():
            raise AccessError('This file is not available.')
        parent.check_access('read')
        datas = attachment.datas
        if isinstance(datas, bytes):
            datas = datas.decode()
        return {
            'name': attachment.name,
            'mimetype': attachment.mimetype,
            'datas': datas,
        }

    @api.model
    def list_report_runs(self, filters=None):
        self._require_utility_user()
        return self._services()['report'].list_runs(filters)

    @api.model
    def get_report_run(self, run_id):
        self._require_utility_user()
        run = self.env['utility.management.report.run'].browse(run_id)
        run.check_access('read')
        return self._services()['report'].run_dto(run)

    @api.model
    def get_settings(self):
        self._require_utility_user()
        from odoo.addons.utility_management.services.common import config_for
        config = config_for(self.env, self.env.company)
        if not config:
            return {
                'id': False,
                'company_id': self.env.company.id,
                'verification_required': True,
                'offline_after_minutes': 60,
                'missing_reading_after_minutes': 60,
                'default_anomaly_percent': 20.0,
                'default_escalation_minutes': 60,
                'mail_notifications': False,
            }
        return {
            'id': config.id,
            'company_id': config.company_id.id,
            'verification_required': config.verification_required,
            'offline_after_minutes': config.offline_after_minutes,
            'missing_reading_after_minutes': config.missing_reading_after_minutes,
            'default_anomaly_percent': config.default_anomaly_percent,
            'default_escalation_minutes': config.default_escalation_minutes,
            'mail_notifications': config.mail_notifications,
        }

    @api.model
    def save_settings(self, values):
        self._require_utility_user()
        from odoo.addons.utility_management.services.audit_service import AuditService
        from odoo.addons.utility_management.services.common import require_manager
        require_manager(self.env, 'Only a Facility Manager can change settings.')
        values = dict(values or {})
        model = self.env['utility.management.config'].with_context(utility_config_service=True)
        config = model.search([('company_id', '=', self.env.company.id)], limit=1)
        if config:
            before = {'verification_required': config.verification_required}
            config.write(values)
        else:
            before = {}
            values['company_id'] = self.env.company.id
            config = model.create(values)
        AuditService(self.env).log(
            'config_change', config, 'success', 'Utility settings updated.',
            before=before, after={'verification_required': config.verification_required},
        )
        return self.get_settings()

    @api.model
    def list_scopes(self):
        self._require_utility_user()
        from odoo.addons.utility_management.services.common import require_manager
        require_manager(self.env, 'Only a Facility Manager can view access scope.')
        scopes = self.env['utility.management.access.scope'].search([('active', '=', True)])
        return [{
            'id': scope.id,
            'user_id': scope.user_id.id,
            'dimension': scope.dimension,
            'ref_code': scope.ref_code,
            'label': scope.label,
            'company_id': scope.company_id.id,
        } for scope in scopes]

    @api.model
    def save_scope(self, values):
        self._require_utility_user()
        values = dict(values or {})
        model = self.env['utility.management.access.scope']
        if values.get('id'):
            scope = model.browse(values['id'])
            scope.write({key: values[key] for key in values if key != 'id'})
            return {'id': scope.id, 'active': scope.active}
        scope = model.create(values)
        return {'id': scope.id, 'active': scope.active}

    @api.model
    def list_audit_events(self, filters=None):
        self._require_utility_user()
        from odoo.addons.utility_management.services.audit_service import AuditService
        return AuditService(self.env).list(filters)

    @api.model
    def get_audit_event(self, event_id):
        self._require_utility_user()
        from odoo.addons.utility_management.services.audit_service import AuditService
        return AuditService(self.env).get(event_id)
