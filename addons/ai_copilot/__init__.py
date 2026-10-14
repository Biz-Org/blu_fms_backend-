# -*- coding: utf-8 -*-

from . import models


def post_init_hook(env):
    env["ai.copilot.config"].sudo()._ensure_config()
