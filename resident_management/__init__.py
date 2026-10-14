from . import models


def post_init_hook(env):
    env["resident.portal"]._seed_demo()
