# -*- coding: utf-8 -*-
from .mock_adapter import MockAdapter
from .erp_adapter import ErpAdapter
from .crm_adapter import CrmAdapter
from .bank_adapter import BankAdapter
from .whatsapp_adapter import WhatsAppAdapter
from .legacy_adapter import LegacyAdapter


class ConnectorRegistry:
    """Maps adapter_key → adapter class. No provider logic scattered in models."""

    _registry = {
        'mock': MockAdapter,
        'erp': ErpAdapter,
        'crm': CrmAdapter,
        'bank': BankAdapter,
        'whatsapp': WhatsAppAdapter,
        'legacy': LegacyAdapter,
    }

    @classmethod
    def register(cls, key, adapter_cls):
        cls._registry[key] = adapter_cls

    @classmethod
    def get(cls, key):
        return cls._registry.get(key) or MockAdapter

    @classmethod
    def keys(cls):
        return list(cls._registry.keys())

    @classmethod
    def for_category(cls, category):
        """Prefer category-named adapter; fallback mock."""
        return cls.get(category or 'mock')


def get_adapter(env, connector, scenario=None):
    adapter_key = getattr(connector, 'adapter_key', None) or getattr(connector, 'category', None) or 'mock'
    adapter_cls = ConnectorRegistry.get(adapter_key)
    return adapter_cls(env, connector, scenario=scenario)
