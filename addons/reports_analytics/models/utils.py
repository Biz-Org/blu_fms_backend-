# -*- coding: utf-8 -*-

import json
from datetime import datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tools.safe_eval import safe_eval

from .source_catalog import DATE_FIELD_CANDIDATES


def parse_json(value, default=None):
    if default is None:
        default = {}
    if value in (None, False, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def dumps_json(value):
    return json.dumps(value or {}, default=str)


def parse_domain(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        domain = safe_eval(value, {"uid": 0})
    except Exception:
        return []
    return domain if isinstance(domain, list) else []


def date_bounds(key, date_from=None, date_to=None, today=None):
    today = today or fields.Date.today()
    key = key or "last_30"
    if key == "custom":
        start = fields.Date.to_date(date_from) if date_from else today - timedelta(days=30)
        end = fields.Date.to_date(date_to) if date_to else today
        return start, end
    if key == "last_7":
        return today - timedelta(days=7), today
    if key == "last_90":
        return today - timedelta(days=90), today
    if key == "this_month":
        return today.replace(day=1), today
    if key == "this_quarter":
        month = ((today.month - 1) // 3) * 3 + 1
        return today.replace(month=month, day=1), today
    if key == "this_year":
        return today.replace(month=1, day=1), today
    if key == "previous":
        end = today - timedelta(days=30)
        return end - timedelta(days=30), end
    return today - timedelta(days=30), today


def previous_bounds(start, end):
    delta = (end - start) or timedelta(days=1)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - delta + timedelta(days=1)
    return prev_start, prev_end


def dt_start(day):
    return datetime.combine(day, time.min)


def dt_end(day):
    return datetime.combine(day, time.max)


def pick_date_field(model):
    names = model._fields
    for candidate in DATE_FIELD_CANDIDATES:
        if candidate in names:
            return candidate
    return False


def field_exists(model, name):
    return name in model._fields


def company_domain(model, company):
    if field_exists(model, "company_id") and company:
        return [("company_id", "in", [company.id, False])]
    return []


def pct_change(current, previous):
    if previous in (None, False) or previous == 0:
        if current in (None, False):
            return None
        return None
    try:
        return round(((float(current) - float(previous)) / abs(float(previous))) * 100.0, 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def trend_label(change):
    if change is None:
        return "Stable"
    if abs(change) < 1:
        return "Stable"
    if abs(change) >= 15:
        return "Significant Change"
    if change > 0:
        return "Increasing"
    return "Decreasing"


def next_schedule_datetime(frequency, weekday=0, month_day=1, hour=8, minute=0, interval_days=1, now=None):
    now = now or fields.Datetime.now()
    hour = int(hour or 8)
    minute = int(minute or 0)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if frequency == "daily":
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate
    if frequency == "weekly":
        weekday = int(weekday or 0)
        days_ahead = (weekday - candidate.weekday()) % 7
        candidate = candidate + timedelta(days=days_ahead)
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate
    if frequency == "monthly":
        day = max(1, min(int(month_day or 1), 28))
        candidate = candidate.replace(day=day)
        if candidate <= now:
            candidate = (candidate + relativedelta(months=1)).replace(day=day)
        return candidate
    if frequency == "quarterly":
        day = max(1, min(int(month_day or 1), 28))
        candidate = candidate.replace(day=day)
        if candidate <= now:
            candidate = (candidate + relativedelta(months=3)).replace(day=day)
        return candidate
    days = max(1, int(interval_days or 1))
    if candidate <= now:
        candidate += timedelta(days=days)
    return candidate
