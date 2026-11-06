# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class EiMasterMapping(models.Model):
    _name = 'ei.master.mapping'
    _description = 'Master Data Mapping'
    _order = 'entity_id, name'
    _check_company_auto = True

    name = fields.Char(required=True)
    entity_id = fields.Many2one('ei.master.entity', required=True, ondelete='cascade', index=True)
    integration_id = fields.Many2one('ei.integration', ondelete='set null', index=True)
    active = fields.Boolean(default=True)
    source_connector_id = fields.Many2one('ei.connector', string='Source Connector', ondelete='set null')
    target_connector_id = fields.Many2one('ei.connector', string='Target Connector', ondelete='set null')
    source_system = fields.Char(required=True, index=True)
    target_system = fields.Char(required=True, index=True)
    source_of_truth = fields.Selection(
        [
            ('source', 'Source System'),
            ('target', 'Target System'),
            ('precastmps', 'PrecastMPS'),
            ('manual', 'Manual Decision'),
        ],
        required=True,
        default='manual',
        index=True,
    )
    owner = fields.Char(string='Data Owner')
    record_count = fields.Integer(
        string='Records',
        default=0,
        help='Approximate / last-known record count for this mapping (demo & monitoring).',
    )
    validation_rules = fields.Text()
    field_mapping_json = fields.Text(string='Field Mapping (JSON)')
    transform_rules = fields.Text(string='Transformation Rules')
    duplicate_detection_keys = fields.Char(
        string='Duplicate Detection Keys',
        help='Comma-separated business keys used for duplicate detection.',
    )
    external_ref = fields.Char(string='External Reference', index=True)
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('synced', 'Synced'),
            ('failed', 'Failed'),
            ('updated', 'Updated'),
            ('archived', 'Archived'),
            ('conflict', 'Conflict'),
        ],
        default='pending',
        required=True,
        index=True,
    )
    last_sync_at = fields.Datetime(string='Last Synchronized At')
    change_note = fields.Text(string='Change Tracking Note')
    conflict_ids = fields.One2many('ei.master.conflict', 'mapping_id', string='Conflicts')
    conflict_count = fields.Integer(compute='_compute_conflict_count')
    company_id = fields.Many2one('res.company', index=True)

    _sql_constraints = [
        (
            'ei_master_mapping_entity_systems_uniq',
            'unique(entity_id, source_system, target_system)',
            'Mapping for this entity and system pair already exists.',
        ),
    ]

    @api.depends('conflict_ids')
    def _compute_conflict_count(self):
        for rec in self:
            rec.conflict_count = len(rec.conflict_ids.filtered(lambda c: c.state == 'conflict'))

    @api.constrains('source_system', 'target_system')
    def _check_systems(self):
        for rec in self:
            if rec.source_system == rec.target_system:
                raise ValidationError('Source and target systems must differ.')

    def _validate_sot_direction(self):
        """Source-of-truth must not be violated by write direction."""
        self.ensure_one()
        # If SoT is source, target is writable destination — OK
        # If SoT is target, sync should not overwrite target from source without conflict
        # Enforcement is in MasterDataService; validate config completeness here
        if self.source_of_truth == 'precastmps' and not self.target_system:
            raise UserError('PrecastMPS source of truth requires a target system.')
        if not self.source_system or not self.target_system:
            raise UserError('Source and target systems are required.')

    def action_sync_now(self):
        self.ensure_one()
        if not self.env.user.has_group('enterprise_integration.group_ei_manager'):
            raise AccessError('Only Managers can synchronize master data.')
        self._validate_sot_direction()
        from odoo.addons.enterprise_integration.services.workflow_service import WorkflowService
        result = WorkflowService(self.env).sync_master(self)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Master Data Sync',
                'message': (
                    f"State={result.get('state')} synced={result.get('synced')} "
                    f"conflicts={result.get('conflicts')}"
                ),
                'type': 'warning' if result.get('conflicts') else 'success',
                'sticky': False,
            },
        }

    def action_resolve_conflicts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Resolve Conflict',
            'res_model': 'ei.conflict.resolve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_mapping_id': self.id},
        }

    def action_mark_synced(self):
        self.check_access('write')
        self.write({
            'state': 'synced',
            'last_sync_at': fields.Datetime.now(),
            'change_note': 'Marked synced',
        })
        self.env['ei.log'].sudo().ei_log(
            name=f'Master mapping marked synced {self.name}',
            category='master_data',
            level='success',
            operation='master_mark_synced',
            master_mapping_id=self.id,
            source_system=self.source_system,
            destination_system=self.target_system,
        )
