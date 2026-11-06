# -*- coding: utf-8 -*-
from .analytics import meter_rows, property_rows, trends
from .common import require_staff


class ConsumptionService(object):
    def __init__(self, env):
        self.env = env

    def overview(self, filters=None):
        require_staff(self.env)
        meters = self.by_meter(filters)
        payload = {'electricity': 0.0, 'water': 0.0, 'gas': 0.0, 'meters': meters}
        for row in meters:
            if row['utility_type'] in payload:
                payload[row['utility_type']] += row['consumption']
        return payload

    def comparison(self, filters=None):
        filters = dict(filters or {})
        filters['comparison'] = 'previous_period'
        return {
            'electricity': trends(self.env, filters, 'electricity'),
            'water': trends(self.env, filters, 'water'),
            'gas': trends(self.env, filters, 'gas'),
        }

    def by_property(self, filters=None):
        return property_rows(self.env, filters)

    def by_meter(self, filters=None):
        return meter_rows(self.env, filters)

    def analysis(self, filters=None):
        overview = self.overview(filters)
        meters = list(overview['meters'])
        return {
            'overview': overview,
            'properties': self.by_property(filters),
            'meters': meters,
            'abnormal_meters': [row for row in meters if row['abnormal']],
        }
