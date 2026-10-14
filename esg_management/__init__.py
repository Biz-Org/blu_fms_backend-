from . import models


def post_init_hook(env):
    env["esg.portal"]._seed_demo()
