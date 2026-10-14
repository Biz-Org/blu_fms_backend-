from . import models


def post_init_hook(env):
    env["wf.portal"]._seed_demo()
