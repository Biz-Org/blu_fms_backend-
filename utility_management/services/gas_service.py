# -*- coding: utf-8 -*-
from .analytics import buildings, overview, trends
from .common import latest_readings, page_window, require_staff


class GasService(object):
    def __init__(self, env):
        self.env = env

    def overview(self, filters=None):
        payload = overview(self.env, filters, 'gas', ('flow_rate', 'pressure'))
        payload['safety'] = self.safety(filters)
        return payload

    def safety(self, filters=None):
        require_staff(self.env)
        domain = [('utility_type', '=', 'gas')]
        filters = filters or {}
        for key in ('property_ref', 'site_ref'):
            if filters.get(key):
                domain.append((key, '=', filters[key]))
        meters_model = self.env['utility.management.meter']
        window = page_window(filters)
        total = meters_model.search_count(domain)
        meters = meters_model.search(domain, order='meter_code, id', **(
            {'limit': window[0], 'offset': window[1]} if window else {}
        ))
        latest = latest_readings(self.env, meters, [('status', '=', 'verified')])
        rows = []
        for meter in meters:
            reading = latest.get(meter.id)
            rows.append({
                'meter_id': meter.id,
                'meter_code': meter.meter_code,
                'status': meter.status,
                'health': meter.health,
                'flow_rate': reading.flow_rate if reading else False,
                'pressure': reading.pressure if reading else False,
                'safety_observation': reading.safety_observation if reading else False,
                'property_ref': meter.property_ref,
                'site_ref': meter.site_ref,
            })
        if window:
            return {
                'rows': rows,
                'total_count': total,
                'limit': window[0],
                'offset': window[1],
            }
        return rows

    def trends(self, filters=None):
        return trends(self.env, filters, 'gas')

    def buildings(self, filters=None):
        return buildings(self.env, filters, 'gas')
