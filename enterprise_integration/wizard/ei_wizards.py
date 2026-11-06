# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.enterprise_integration.services.health_service import HealthService
from odoo.addons.enterprise_integration.services.webhook_service import WebhookService
from odoo.addons.enterprise_integration.services.workflow_service import WorkflowService


class EiConnectionTestWizard(models.TransientModel):
    _name = 'ei.connection.test.wizard'
    _description = 'Connection / Endpoint Test Wizard'

    test_type = fields.Selection(
        [
            ('connector', 'Connector'),
            ('webhook', 'Webhook'),
            ('api', 'API Endpoint'),
        ],
        required=True,
        default='connector',
    )
    connector_id = fields.Many2one('ei.connector')
    webhook_id = fields.Many2one('ei.webhook')
    endpoint_id = fields.Many2one('ei.api.endpoint')
    api_key = fields.Char(string='API Key (optional, never stored)')
    result_message = fields.Text(readonly=True)
    result_ok = fields.Boolean(readonly=True)

    def action_run_test(self):
        self.ensure_one()
        if not self.env.user.has_group('enterprise_integration.group_ei_manager'):
            from odoo.exceptions import AccessError
            raise AccessError('Only Managers can test connections.')
        if self.test_type == 'connector' and self.connector_id:
            result = HealthService(self.env).check_connector(self.connector_id)
            self.write({
                'result_ok': bool(result.get('ok')),
                'result_message': (
                    f"{'[MOCK / DEMO] ' if self.connector_id.is_mock else ''}"
                    f"{result.get('message') or result.get('error') or result}"
                ),
            })
        elif self.test_type == 'webhook' and self.webhook_id:
            msg = (
                f'[MOCK / DEMO] Webhook test for {self.webhook_id.name} '
                f'({self.webhook_id.direction}). Not a live delivery.'
            )
            self.write({'result_ok': True, 'result_message': msg})
            WebhookService(self.env).logs.log(
                name=f'Webhook test {self.webhook_id.name}',
                category='webhook',
                level='success',
                operation='webhook_test',
                webhook_id=self.webhook_id.id,
                integration_id=self.webhook_id.integration_id.id,
                response_summary='mock_test',
            )
        elif self.test_type == 'api' and self.endpoint_id:
            result = WorkflowService(self.env).test_api_endpoint(
                self.endpoint_id, api_key=self.api_key or None,
            )
            self.endpoint_id.write({
                'last_test_at': fields.Datetime.now(),
                'last_test_result': str(result)[:2000],
            })
            self.write({
                'result_ok': bool(result.get('ok')),
                'result_message': result.get('message') or str(result),
            })
            # Never persist the provided API key
            self.api_key = False
        else:
            self.write({
                'result_ok': False,
                'result_message': 'Select a connector, webhook, or API endpoint to test.',
            })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class EiSyncRunWizard(models.TransientModel):
    _name = 'ei.sync.run.wizard'
    _description = 'Manual Sync Run Wizard'

    job_id = fields.Many2one('ei.sync.job', required=True)
    note = fields.Char()

    def action_confirm_run(self):
        self.ensure_one()
        if not self.env.user.has_group('enterprise_integration.group_ei_manager'):
            from odoo.exceptions import AccessError
            raise AccessError('Only Managers can run synchronizations.')
        run = WorkflowService(self.env).run_sync(self.job_id)
        self.job_id.sudo().write({
            'last_run_state': run.state if run else False,
            'realtime_pending': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Synchronization Run',
            'res_model': 'ei.sync.run',
            'res_id': run.id,
            'view_mode': 'form',
            'target': 'current',
        }


class EiCredentialRotateWizard(models.TransientModel):
    _name = 'ei.credential.rotate.wizard'
    _description = 'Credential Rotate Wizard'

    credential_type = fields.Selection(
        [('api', 'API Credential'), ('connector', 'Connector Credential')],
        required=True,
        default='api',
    )
    api_credential_id = fields.Many2one('ei.api.credential')
    connector_credential_id = fields.Many2one('ei.connector.credential')
    new_secret = fields.Char(required=True)
    one_time_display = fields.Char(readonly=True)

    def action_rotate(self):
        self.ensure_one()
        if not self.env.user.has_group('enterprise_integration.group_ei_manager'):
            from odoo.exceptions import AccessError
            raise AccessError('Only Managers can rotate credentials.')
        target_name = False
        if self.credential_type == 'api' and self.api_credential_id:
            self.api_credential_id.write({'plaintext_key': self.new_secret, 'state': 'active'})
            target_name = self.api_credential_id.name
            self.env['ei.log'].sudo().ei_log(
                name=f'API credential rotated {target_name}',
                category='api',
                level='success',
                operation='credential_rotate',
                endpoint_id=self.api_credential_id.endpoint_id.id,
                integration_id=self.api_credential_id.integration_id.id,
                response_summary='Credential rotated; plaintext never logged',
            )
        elif self.credential_type == 'connector' and self.connector_credential_id:
            self.connector_credential_id.write({'secret': self.new_secret, 'state': 'active'})
            target_name = self.connector_credential_id.name
            self.env['ei.log'].sudo().ei_log(
                name=f'Connector credential rotated {target_name}',
                category='connector',
                level='success',
                operation='credential_rotate',
                connector_id=self.connector_credential_id.connector_id.id,
                response_summary='Credential rotated; plaintext never logged',
            )
        # Show once in wizard, clear write-only field immediately
        self.write({'one_time_display': self.new_secret, 'new_secret': False})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class EiConflictResolveWizard(models.TransientModel):
    _name = 'ei.conflict.resolve.wizard'
    _description = 'Master Data Conflict Resolve Wizard'

    mapping_id = fields.Many2one('ei.master.mapping', required=True)
    conflict_id = fields.Many2one('ei.master.conflict')
    resolution = fields.Text(required=True)

    def action_resolve(self):
        self.ensure_one()
        if not self.env.user.has_group('enterprise_integration.group_ei_manager'):
            from odoo.exceptions import AccessError
            raise AccessError('Only Managers can resolve conflicts.')
        from odoo.addons.enterprise_integration.services.master_data_service import MasterDataService
        conflict = self.conflict_id
        if not conflict:
            conflict = self.env['ei.master.conflict'].search([
                ('mapping_id', '=', self.mapping_id.id),
                ('state', '=', 'conflict'),
            ], limit=1)
        if conflict:
            MasterDataService(self.env).resolve(conflict, self.resolution, self.env.user)
        return {'type': 'ir.actions.act_window_close'}


class EiLogExportWizard(models.TransientModel):
    _name = 'ei.log.export.wizard'
    _description = 'Log Export Wizard'

    category = fields.Selection(
        [
            ('api', 'API'),
            ('webhook', 'Webhook'),
            ('connector', 'Connector'),
            ('sync', 'Synchronization'),
            ('master_data', 'Master Data'),
            ('system', 'System'),
            ('all', 'All'),
        ],
        default='all',
        required=True,
    )
    date_from = fields.Datetime()
    date_to = fields.Datetime()
    export_format = fields.Selection(
        [('csv', 'CSV'), ('json', 'JSON')],
        default='csv',
        required=True,
    )
    export_data = fields.Text(readonly=True)

    def action_export(self):
        self.ensure_one()
        if not self.env.user.has_group('enterprise_integration.group_ei_manager'):
            from odoo.exceptions import AccessError
            raise AccessError('Only Managers can export logs.')
        domain = []
        if self.category != 'all':
            domain.append(('category', '=', self.category))
        if self.date_from:
            domain.append(('create_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('create_date', '<=', self.date_to))
        logs = self.env['ei.log'].search(domain, limit=5000)
        # Never export request/response bodies that may contain secrets —
        # only safe metadata fields.
        if self.export_format == 'json':
            import json
            payload = [{
                'name': l.name,
                'category': l.category,
                'level': l.level,
                'operation': l.operation,
                'correlation_id': l.correlation_id,
                'create_date': str(l.create_date),
            } for l in logs]
            self.export_data = json.dumps(payload, indent=2)
        else:
            lines = ['name,category,level,operation,correlation_id,create_date']
            for l in logs:
                lines.append(
                    f'"{l.name}",{l.category},{l.level},{l.operation or ""},'
                    f'{l.correlation_id or ""},{l.create_date or ""}'
                )
            self.export_data = '\n'.join(lines)
        self.env['ei.log'].sudo().ei_log(
            name='Log export completed',
            category='system',
            level='success',
            operation='log_export',
            response_summary=f'format={self.export_format} count={len(logs)}',
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
