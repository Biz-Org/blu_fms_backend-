# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class WorkflowEngineApprover(models.Model):
    _name = 'workflow.engine.approver'
    _description = 'Approver'
    _order = 'level_id, sequence, id'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    level_id = fields.Many2one(
        'workflow.engine.approval.level',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='level_id.company_id',
        store=True,
        index=True,
    )
    sequence = fields.Integer(default=10, index=True)
    user_id = fields.Many2one('res.users', ondelete='restrict', index=True)
    group_id = fields.Many2one('res.groups', ondelete='restrict', index=True)
    role_ref = fields.Char(
        string='Role Reference',
        help='Optional role key. Does not create a separate role-management system.',
    )
    is_fallback = fields.Boolean(string='Fallback Approver')
    active = fields.Boolean(default=True)

    @api.depends('user_id', 'group_id', 'role_ref', 'is_fallback')
    def _compute_name(self):
        for rec in self:
            if rec.user_id:
                rec.name = rec.user_id.display_name
            elif rec.group_id:
                rec.name = rec.group_id.display_name
            elif rec.role_ref:
                rec.name = rec.role_ref
            else:
                rec.name = 'Approver'
            if rec.is_fallback:
                rec.name = '%s (fallback)' % rec.name

    @api.constrains('user_id', 'group_id')
    def _check_user_or_group(self):
        for rec in self:
            if bool(rec.user_id) == bool(rec.group_id) and not rec.role_ref:
                raise ValidationError('An approver must be a user or a group, not both or neither.')
            if rec.user_id and rec.group_id:
                raise ValidationError('An approver cannot be both a user and a group.')
