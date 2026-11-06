# -*- coding: utf-8 -*-
from odoo.exceptions import UserError

from .common import has_group


class SupplierService:
    def __init__(self, env):
        self.env = env

    def set_status(self, profile, state):
        if not has_group(self.env, 'group_procurement_officer'):
            raise UserError('Only a procurement officer can change supplier status.')
        if state not in ('active', 'preferred', 'suspended'):
            raise UserError('Unknown supplier status.')
        profile.write({'state': state})
        return True

    def add_contact(self, profile, name, email='', phone='', function=''):
        if not has_group(self.env, 'group_procurement_officer'):
            raise UserError('Only a procurement officer can add a supplier contact.')
        return self.env['res.partner'].sudo().create({
            'name': name,
            'email': email,
            'phone': phone,
            'function': function or False,
            'parent_id': profile.partner_id.id,
            'type': 'contact',
        })
