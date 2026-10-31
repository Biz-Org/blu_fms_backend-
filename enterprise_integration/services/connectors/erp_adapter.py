# -*- coding: utf-8 -*-
"""ERP connector adapter — mock until a real vendor is provided."""
from .mock_adapter import MockAdapter


class ErpAdapter(MockAdapter):
    """
    ERP adapter stub.

    Uses mock behavior. Do NOT treat as live ERP connectivity.
    Provider-specific logic belongs in a future concrete subclass.
    """

    key = 'erp'
    category = 'erp'
    is_mock = True
