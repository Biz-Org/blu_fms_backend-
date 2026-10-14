from . import models


def post_init_hook(env):
    env["property.property"]._seed_demo_portfolio()
