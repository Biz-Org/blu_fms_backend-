from . import models


def post_init_hook(env):
    env["ot.portal"]._seed_demo()
