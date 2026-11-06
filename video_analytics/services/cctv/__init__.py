# -*- coding: utf-8 -*-
from .base import VaCctvAdapter
from .stub import VaCctvStubAdapter


def get_adapter(camera=None):
    """Always return the offline stub. No vendor adapters and no network."""
    return VaCctvStubAdapter(camera=camera)


from . import service  # noqa: E402
