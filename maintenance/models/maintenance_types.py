# -*- coding: utf-8 -*-
"""Shared maintenance type constants and classification helpers."""

MAINTENANCE_REQUEST_TYPE_SELECTION = [
    ('corrective', 'Corrective'),
    ('preventive', 'Preventive'),
    ('predictive', 'Predictive'),
]

PLANNING_MAINTENANCE_TYPE_SELECTION = [
    ('breakdown', 'Breakdown (Corrective)'),
    ('preventive', 'Preventive'),
    ('predictive', 'Predictive'),
]

MAINTENANCE_TYPE_EMOJI = {
    'corrective': '🚛',
    'preventive': '🔧',
    'predictive': '📡',
    'breakdown': '⚠',
}


def classify_maintenance_type(maintenance_type):
    """Return corrective | preventive | predictive | other."""
    if maintenance_type in ('corrective', 'breakdown'):
        return 'corrective'
    if maintenance_type == 'preventive':
        return 'preventive'
    if maintenance_type == 'predictive':
        return 'predictive'
    return 'other'


def is_corrective_type(maintenance_type):
    return classify_maintenance_type(maintenance_type) == 'corrective'


def is_preventive_type(maintenance_type):
    return classify_maintenance_type(maintenance_type) == 'preventive'


def is_predictive_type(maintenance_type):
    return classify_maintenance_type(maintenance_type) == 'predictive'


def rca_required_for_request(maintenance_type, failure_found_during_job=False, planning_maintenance_type=None):
    """Plant rule: corrective/breakdown always needs RCA; PM/predictive only if failure found."""
    if is_corrective_type(maintenance_type) or planning_maintenance_type == 'breakdown':
        return True
    return bool(failure_found_during_job)


def rca_analysis_list_domain():
    """Default Analysis work-order list: corrective + jobs with failure on PM/predictive."""
    return [
        '&',
        ('archive', '=', False),
        '|',
        ('maintenance_type', '=', 'corrective'),
        ('failure_found_during_job', '=', True),
    ]


def maintenance_type_domain(kinds=None):
    """Odoo domain fragment for maintenance.request.maintenance_type."""
    kinds = kinds or ('corrective', 'preventive', 'predictive')
    mapping = {
        'corrective': ['corrective', 'breakdown'],
        'preventive': ['preventive'],
        'predictive': ['predictive'],
    }
    values = []
    for kind in kinds:
        values.extend(mapping.get(kind, [kind]))
    return ('maintenance_type', 'in', list(dict.fromkeys(values)))
