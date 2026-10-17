# -*- coding: utf-8 -*-
"""Shared Plant Maintenance / Facility Management domain field and helpers."""

from odoo import api, fields, models


MAINTENANCE_DOMAIN_SELECTION = [
    ('plant', 'Plant Maintenance'),
    ('facility', 'Facility Management'),
]

MAINTENANCE_DOMAIN_FILTER_OPTIONS = [
    {'value': 'all', 'label': 'All Maintenance'},
    {'value': 'plant', 'label': 'Plant Maintenance'},
    {'value': 'facility', 'label': 'Facility Management'},
]


def domain_filter_clause(domain_key, field_name='maintenance_domain'):
    """Build an Odoo domain clause for plant / facility / all."""
    if not domain_key or domain_key in ('all', 'All', False):
        return []
    key = str(domain_key).strip().lower()
    if key not in ('plant', 'facility'):
        return []
    return [(field_name, '=', key)]


def domain_filter_options(env):
    """Localized options for UI domain filters."""
    return [
        {'value': 'all', 'label': env._('All Maintenance')},
        {'value': 'plant', 'label': env._('Plant Maintenance')},
        {'value': 'facility', 'label': env._('Facility Management')},
    ]


def domain_label(env, key):
    mapping = {
        'all': env._('All Maintenance'),
        'plant': env._('Plant Maintenance'),
        'facility': env._('Facility Management'),
    }
    return mapping.get(key or 'all', mapping['all'])


class MaintenanceEquipmentCategoryDomain(models.Model):
    _inherit = 'maintenance.equipment.category'

    maintenance_domain = fields.Selection(
        selection=MAINTENANCE_DOMAIN_SELECTION,
        string='Maintenance Domain',
        default='plant',
        required=True,
        index=True,
        help='Plant = industrial equipment. Facility = building / FMS assets.',
    )


class MaintenanceEquipmentDomain(models.Model):
    _inherit = 'maintenance.equipment'

    maintenance_domain = fields.Selection(
        selection=MAINTENANCE_DOMAIN_SELECTION,
        string='Maintenance Domain',
        default='plant',
        required=True,
        index=True,
        tracking=True,
        help='Plant Maintenance (machines, cranes, compressors) or Facility Management '
             '(AC, elevators, lighting, plumbing, fire safety).',
    )

    @api.onchange('category_id')
    def _onchange_category_id_maintenance_domain(self):
        for equipment in self:
            if equipment.category_id and equipment.category_id.maintenance_domain:
                equipment.maintenance_domain = equipment.category_id.maintenance_domain

    @api.model_create_multi
    def create(self, vals_list):
        Category = self.env['maintenance.equipment.category']
        for vals in vals_list:
            if not vals.get('maintenance_domain') and vals.get('category_id'):
                cat = Category.browse(vals['category_id'])
                if cat.maintenance_domain:
                    vals['maintenance_domain'] = cat.maintenance_domain
        return super().create(vals_list)


class MaintenanceRequestDomain(models.Model):
    _inherit = 'maintenance.request'

    maintenance_domain = fields.Selection(
        selection=MAINTENANCE_DOMAIN_SELECTION,
        string='Maintenance Domain',
        compute='_compute_maintenance_domain',
        store=True,
        readonly=False,
        index=True,
        help='Copied from the linked equipment; used for Plant / Facility filters.',
    )

    @api.depends('equipment_id', 'equipment_id.maintenance_domain', 'category_id', 'category_id.maintenance_domain')
    def _compute_maintenance_domain(self):
        for request in self:
            if request.equipment_id and request.equipment_id.maintenance_domain:
                request.maintenance_domain = request.equipment_id.maintenance_domain
            elif request.category_id and request.category_id.maintenance_domain:
                request.maintenance_domain = request.category_id.maintenance_domain
            elif not request.maintenance_domain:
                request.maintenance_domain = 'plant'


class MaintenanceTeamDomain(models.Model):
    _inherit = 'maintenance.team'

    maintenance_domain = fields.Selection(
        selection=MAINTENANCE_DOMAIN_SELECTION,
        string='Maintenance Domain',
        default='plant',
        required=True,
        index=True,
        help='Primary focus of this team: Plant Maintenance or Facility Management.',
    )
