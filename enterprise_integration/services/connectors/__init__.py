# -*- coding: utf-8 -*-
from .base import BaseConnectorAdapter
from .registry import ConnectorRegistry, get_adapter
from .mock_adapter import MockAdapter
from .erp_adapter import ErpAdapter
from .crm_adapter import CrmAdapter
from .bank_adapter import BankAdapter
from .whatsapp_adapter import WhatsAppAdapter
from .legacy_adapter import LegacyAdapter

__all__ = [
    'BaseConnectorAdapter',
    'ConnectorRegistry',
    'get_adapter',
    'MockAdapter',
    'ErpAdapter',
    'CrmAdapter',
    'BankAdapter',
    'WhatsAppAdapter',
    'LegacyAdapter',
]
