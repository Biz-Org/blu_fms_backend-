# -*- coding: utf-8 -*-
import secrets
from datetime import datetime, timedelta, timezone


class IdempotencyService:
    def __init__(self, env):
        self.env = env

    def new_key(self):
        return secrets.token_hex(16)

    def seen(self, model, field, key):
        if not key:
            return False
        return bool(self.env[model].sudo().search_count([(field, '=', key)], limit=1))

    def seen_log_idempotency(self, key):
        if not key:
            return False
        return bool(self.env['ei.log'].sudo().search_count([
            ('category', '=', 'api'),
            ('request_summary', '=', f'idempotency:{key}'),
        ], limit=1))


class RateLimitService:
    def __init__(self, env):
        self.env = env

    def allow(self, endpoint, credential=None):
        limit = endpoint.rate_limit or 60
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=60)
        domain = [
            ('category', '=', 'api'),
            ('endpoint_id', '=', endpoint.id),
            ('create_date', '>=', fields_to_odoo(since)),
        ]
        count = self.env['ei.log'].sudo().search_count(domain)
        return count < limit


def fields_to_odoo(dt):
    """Return datetime suitable for ORM domain (naive UTC)."""
    return dt.replace(microsecond=0)
