# -*- coding: utf-8 -*-
"""Safe field transformation — no arbitrary user code execution."""
from datetime import datetime
import re


class TransformService:
    """Applies only allow-listed transformation types."""

    ALLOWED = {
        'none', 'map', 'format', 'expression',
        'string_normalize', 'to_string', 'to_int', 'to_float',
        'to_bool', 'date_iso', 'default',
    }

    def apply(self, value, transform_type='none', transform_expr=None, context=None):
        transform_type = (transform_type or 'none').lower()
        if transform_type not in self.ALLOWED:
            raise ValueError(f'Unsupported transform type: {transform_type}')

        if transform_type in ('none',):
            return value

        if transform_type == 'default':
            return value if value not in (None, '') else transform_expr

        if transform_type == 'to_string':
            return '' if value is None else str(value)

        if transform_type == 'string_normalize':
            return '' if value is None else str(value).strip().lower()

        if transform_type == 'to_int':
            if value in (None, ''):
                return None
            return int(float(str(value)))

        if transform_type == 'to_float':
            if value in (None, ''):
                return None
            return float(str(value))

        if transform_type == 'to_bool':
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in ('1', 'true', 'yes', 'y', 'on')

        if transform_type == 'date_iso':
            if value in (None, ''):
                return None
            if isinstance(value, datetime):
                return value.date().isoformat()
            text = str(value).strip()
            # Accept YYYY-MM-DD or common slash forms
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d'):
                try:
                    return datetime.strptime(text[:10], fmt).date().isoformat()
                except ValueError:
                    continue
            raise ValueError(f'Cannot parse date: {text}')

        if transform_type == 'map':
            # transform_expr: "a:b,c:d" or JSON-like "a=b;c=d"
            mapping = self._parse_map(transform_expr or '')
            key = '' if value is None else str(value)
            return mapping.get(key, value)

        if transform_type == 'format':
            # Safe format using only {value}
            template = transform_expr or '{value}'
            if re.search(r'\{(?!value\})[^}]+\}', template):
                raise ValueError('Format template may only use {value}')
            return template.replace('{value}', '' if value is None else str(value))

        if transform_type == 'expression':
            # Restricted: only passthrough aliases, no eval
            expr = (transform_expr or '').strip().lower()
            if expr in ('', 'value', 'identity'):
                return value
            if expr.startswith('default:'):
                return value if value not in (None, '') else expr.split(':', 1)[1]
            if expr == 'upper':
                return '' if value is None else str(value).upper()
            if expr == 'lower':
                return '' if value is None else str(value).lower()
            raise ValueError(
                'Unsafe/unsupported expression. Use allow-listed transforms only.'
            )

        return value

    @staticmethod
    def _parse_map(expr):
        mapping = {}
        for part in re.split(r'[;,]', expr):
            part = part.strip()
            if not part:
                continue
            if ':' in part:
                src, dst = part.split(':', 1)
            elif '=' in part:
                src, dst = part.split('=', 1)
            else:
                continue
            mapping[src.strip()] = dst.strip()
        return mapping
