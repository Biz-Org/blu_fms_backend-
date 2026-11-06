# -*- coding: utf-8 -*-
"""Vendor-neutral CCTV adapter contract. Implementations must not assume a vendor."""
from abc import ABC, abstractmethod


class VaCctvAdapter(ABC):
    """Clean integration boundary for future CCTV systems."""

    key = 'base'
    is_mock = True

    def __init__(self, camera=None):
        self.camera = camera

    @abstractmethod
    def test_connection(self):
        """Return a health payload. Must not raise on missing vendor config."""

    @abstractmethod
    def resolve_stream(self):
        """Return stream metadata already stored on the camera record."""
