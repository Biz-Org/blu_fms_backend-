# -*- coding: utf-8 -*-
"""CRM connector adapter — mock until a real vendor is provided."""
from .mock_adapter import MockAdapter


class CrmAdapter(MockAdapter):
    key = 'crm'
    category = 'crm'
    is_mock = True
