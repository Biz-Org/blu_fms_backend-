# -*- coding: utf-8 -*-
"""Banking connector adapter — mock until a real provider is provided."""
from .mock_adapter import MockAdapter


class BankAdapter(MockAdapter):
    key = 'bank'
    category = 'bank'
    is_mock = True

    def fetch(self, entity, params=None):
        # Bank-oriented default entity label; still mock data only
        entity = entity or 'transactions'
        return super().fetch(entity, params=params)
