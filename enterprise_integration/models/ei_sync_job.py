# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EiSyncJob(models.Model):
    _name = 'ei.sync.job'
    _description = 'Synchronization Job'
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(required=True, index=True)
    integration_id = fields.Many2one(
        'ei.integration', required=True, ondelete='cascade', index=True,
    )
    active = fields.Boolean(default=True)
    source_connector_id = fields.Many2one('ei.connector', string='Source Connector', ondelete='restrict')
    dest_connector_id = fields.Many2one('ei.connector', string='Destination Connector', ondelete='restrict')
    source_system = fields.Char(index=True)
    dest_system = fields.Char(index=True)
    entity_name = fields.Char(string='Entity', required=True, index=True)
    direction = fields.Selection(
        [('one_way', 'One-way'), ('two_way', 'Two-way')],
        default='one_way',
        required=True,
        index=True,
    )
    mode = fields.Selection(
        [('full', 'Full'), ('incremental', 'Incremental')],
        default='incremental',
        required=True,
        index=True,
    )
    trigger = fields.Selection(
        [
            ('manual', 'Manual'),
            ('scheduled', 'Scheduled'),
            ('realtime', 'Real-time / Event'),
        ],
        default='manual',
        required=True,
        index=True,
    )
    frequency = fields.Selection(
        [
            ('manual', 'Manual'),
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
        ],
        default='manual',
    )
    conflict_policy = fields.Selection(
        [
            ('source_wins', 'Source Wins'),
            ('destination_wins', 'Destination Wins'),
            ('manual', 'Manual Review'),
            ('skip', 'Skip'),
        ],
        default='manual',
        required=True,
    )
    duplicate_policy = fields.Selection(
        [
            ('skip', 'Skip'),
            ('update', 'Update Existing'),
            ('error', 'Mark Error'),
        ],
        default='update',
        required=True,
    )
    retry_max = fields.Integer(default=3)
    external_ref = fields.Char(string='External Reference', index=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('paused', 'Paused'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft',
        required=True,
        index=True,
    )
    last_success_at = fields.Datetime(readonly=True)
    last_run_state = fields.Char(readonly=True)
    realtime_pending = fields.Boolean(
        string='Realtime Event Pending',
        default=False,
        index=True,
        help='Set when an event triggers a realtime sync job; cleared after cron execution.',
    )
    mapping_ids = fields.One2many('ei.connector.mapping', 'sync_job_id', string='Field Mappings')
    run_ids = fields.One2many('ei.sync.run', 'job_id', string='Runs')
    company_id = fields.Many2one(
        related='integration_id.company_id', store=True, readonly=True, index=True,
    )

    _sql_constraints = [
        ('ei_sync_job_retry_max_positive', 'CHECK(retry_max >= 0)', 'Retry max must be >= 0.'),
    ]

    @api.constrains('source_connector_id', 'dest_connector_id', 'source_system', 'dest_system')
    def _check_source_dest(self):
        for rec in self:
            has_source = bool(rec.source_connector_id or rec.source_system)
            has_dest = bool(rec.dest_connector_id or rec.dest_system)
            if not has_source or not has_dest:
                raise ValidationError(
                    'Synchronization job requires both a source and a destination '
                    '(connector and/or system code).'
                )

    def action_activate(self):
        self.check_access('write')
        for job in self:
            job._check_source_dest()
        self.write({'state': 'active', 'active': True})
        for job in self:
            self.env['ei.log'].sudo().ei_log(
                name=f'Sync job activated {job.name}',
                category='sync',
                level='success',
                operation='sync_activate',
                integration_id=job.integration_id.id,
            )

    def action_pause(self):
        self.check_access('write')
        self.write({'state': 'paused'})

    def action_cancel(self):
        self.check_access('write')
        self.write({'state': 'cancelled', 'active': False, 'realtime_pending': False})

    def action_run_now(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Run Synchronization',
            'res_model': 'ei.sync.run.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_job_id': self.id},
        }

    def action_trigger_realtime(self):
        """Mark realtime jobs pending for near-term cron pickup."""
        self.check_access('write')
        realtime = self.filtered(lambda j: j.trigger == 'realtime' and j.state == 'active')
        realtime.write({'realtime_pending': True})
        for job in realtime:
            self.env['ei.log'].sudo().ei_log(
                name=f'Realtime sync event queued {job.name}',
                category='sync',
                level='warning',
                operation='sync_realtime_queue',
                integration_id=job.integration_id.id,
                retryable=True,
            )
        return True

    def _run_internal(self):
        self.ensure_one()
        from odoo.addons.enterprise_integration.services.sync_service import SyncService
        run = SyncService(self.env).run_job(self)
        self.sudo().write({
            'last_run_state': run.state if run else False,
            'realtime_pending': False,
        })
        return run

    @api.model
    def _cron_run_scheduled_jobs(self):
        jobs = self.search([('state', '=', 'active'), ('trigger', '=', 'scheduled'), ('active', '=', True)])
        for job in jobs:
            job._run_internal()
        return True

    @api.model
    def _cron_process_realtime_jobs(self):
        jobs = self.search([
            ('state', '=', 'active'),
            ('trigger', '=', 'realtime'),
            ('active', '=', True),
            ('realtime_pending', '=', True),
        ])
        for job in jobs:
            job._run_internal()
        return True
