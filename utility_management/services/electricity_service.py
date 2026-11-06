# -*- coding: utf-8 -*-
from .analytics import buildings, overview, trends


class ElectricityService(object):
    def __init__(self, env):
        self.env = env

    def overview(self, filters=None):
        return overview(self.env, filters, 'electricity', ('voltage', 'current', 'frequency', 'power_factor', 'load_kw'))

    def buildings(self, filters=None):
        return buildings(self.env, filters, 'electricity')

    def trends(self, filters=None):
        return trends(self.env, filters, 'electricity')
