from . import models


def post_init_hook(env):
    env["gate.portal"]._seed_demo()
