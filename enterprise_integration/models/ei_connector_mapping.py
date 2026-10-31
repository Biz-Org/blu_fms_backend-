# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EiConnectorMapping(models.Model):
    _name = 'ei.connector.mapping'
    _description = 'Connector Field Mapping'
    _order = 'sequence, id'

    name = fields.Char(compute='_compute_name', store=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    connector_id = fields.Many2one('ei.connector', ondelete='cascade', index=True)
    sync_job_id = fields.Many2one('ei.sync.job', ondelete='cascade', index=True)
    source_field = fields.Char(required=True)
    target_field = fields.Char(required=True)
    transform_type = fields.Selection(
        [
            ('none', 'None'),
            ('map', 'Value Map'),
            ('expression', 'Expression'),
            ('format', 'Format'),
        ],
        default='none',
        required=True,
    )
    transform_expr = fields.Char(string='Transformation')
    external_ref = fields.Char(string='External Reference', index=True)

    @api.depends('source_field', 'target_field')
    def _compute_name(self):
        for rec in self:
            rec.name = f'{rec.source_field or ""} → {rec.target_field or ""}'

    @api.constrains('connector_id', 'sync_job_id')
    def _check_parent(self):
        for rec in self:
            if not rec.connector_id and not rec.sync_job_id:
                raise ValidationError('Mapping must belong to a connector or a sync job.')

    @api.constrains('transform_type', 'transform_expr')
    def _check_transform(self):
        for rec in self:
            if rec.transform_type != 'none' and not rec.transform_expr:
                raise ValidationError(
                    'Transformation expression is required when transform type is not None.'
                )
