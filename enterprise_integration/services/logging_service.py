# -*- coding: utf-8 -*-
import uuid


class LoggingService:
    def __init__(self, env):
        self.env = env

    def log(self, **kwargs):
        kwargs.setdefault('correlation_id', str(uuid.uuid4()))
        return self.env['ei.log'].sudo().ei_log(**kwargs)

    def with_correlation(self, correlation_id=None):
        return _BoundLogger(self, correlation_id or str(uuid.uuid4()))


class _BoundLogger:
    def __init__(self, service, correlation_id):
        self.service = service
        self.correlation_id = correlation_id

    def log(self, **kwargs):
        kwargs['correlation_id'] = self.correlation_id
        return self.service.log(**kwargs)
