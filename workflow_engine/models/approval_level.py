# -*- coding: utf-8 -*-
from odoo import fields, models

APPROVAL_MODES = [
    ('sequential', 'Sequential'),
    ('parallel', 'Parallel'),
]


class WorkflowEngineApprovalLevel(models.Model):
    _name = 'workflow.engine.approval.level'
    _description = 'Approval Level'
    _order = 'hierarchy_id, sequence, id'
    _check_company_auto = True

    name = fields.Char()
    hierarchy_id = fields.Many2one(
        'workflow.engine.approval.hierarchy',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='hierarchy_id.company_id',
        store=True,
        index=True,
    )
    sequence = fields.Integer(string='Level', default=10, required=True, index=True)
    mode = fields.Selection(APPROVAL_MODES, required=True, default='sequential')
    threshold = fields.Integer(
        string='Approval Threshold',
        default=1,
        help='Number of approvals required for a parallel level.',
    )
    active = fields.Boolean(default=True)
    approver_ids = fields.One2many(
        'workflow.engine.approver',
        'level_id',
        string='Approvers',
    )

    _sql_constraints = [
        (
            'we_level_hierarchy_sequence_uniq',
            'unique(hierarchy_id, sequence)',
            'Approval level order must be unique within a hierarchy.',
        ),
    ]
