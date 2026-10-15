# -*- coding: utf-8 -*-

from . import models
from . import controllers


def post_init_hook(env):
    env["analytics.data.source"]._sync_known_sources()
    env["analytics.report"]._ensure_owl_launch()
