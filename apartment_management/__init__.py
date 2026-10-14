from . import models


def post_init_hook(env):
    env["apartment.portal"]._seed_demo()
