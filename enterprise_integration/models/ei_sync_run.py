# -*- coding: utf-8 -*-
from odoo import fields, models


class EiSyncRun(models.Model):
    _name = 'ei.sync.run'
    _description = 'Synchronization Run'
    _order = 'create_date desc'
    _check_company_auto = True

    name = fields.Char(required=True, default='New Run', index=True)
    job_id = fields.Many2one('ei.sync.job', required=True, ondelete='cascade', index=True)
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('partially_completed', 'Partially Completed'),
            ('paused', 'Paused'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending',
        required=True,
        index=True,
    )
    started_at = fields.Datetime()
    ended_at = fields.Datetime()
    records_processed = fields.Integer(string='Total Records', default=0)
    records_success = fields.Integer(string='Successful', default=0)
    records_failed = fields.Integer(default=0)
    records_conflict = fields.Integer(string='Conflicted', default=0)
    records_duplicate = fields.Integer(string='Duplicated', default=0)
    retry_count = fields.Integer(default=0)
    error_message = fields.Text()
    correlation_id = fields.Char(index=True)
    external_ref = fields.Char(string='External Reference', index=True)
    record_ids = fields.One2many('ei.sync.record', 'run_id', string='Records')
    company_id = fields.Many2one(
        related='job_id.company_id', store=True, readonly=True, index=True,
    )

    def action_retry(self):
        self.check_access('write')
        for run in self:
            run.write({'retry_count': run.retry_count + 1})
            new_run = run.job_id._run_internal()
            self.env['ei.log'].sudo().ei_log(
                category='sync',
                level='retrying',
                name=f'Retry sync job {run.job_id.name}',
                operation='sync_retry',
                integration_id=run.job_id.integration_id.id,
                sync_run_id=new_run.id if new_run else False,
                correlation_id=run.correlation_id,
                source_system=run.job_id.source_system,
                destination_system=run.job_id.dest_system,
                retryable=True,
            )
        return True
