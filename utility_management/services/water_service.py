# -*- coding: utf-8 -*-
from .analytics import buildings, overview, tanks, trends


class WaterService(object):
    def __init__(self, env):
        self.env = env

    def overview(self, filters=None):
        payload = overview(self.env, filters, 'water', ('flow_rate', 'inflow', 'outflow'))
        payload['tanks'] = tanks(self.env, filters)
        return payload

    def tanks(self, filters=None):
        return tanks(self.env, filters)

    def trends(self, filters=None):
        return trends(self.env, filters, 'water')

    def buildings(self, filters=None):
        return buildings(self.env, filters, 'water')
