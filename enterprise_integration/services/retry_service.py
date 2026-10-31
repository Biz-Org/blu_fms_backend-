# -*- coding: utf-8 -*-
"""Reusable retry policy for webhooks, connectors, and sync."""
from datetime import datetime, timedelta, timezone


class RetryPolicy:
    """Compute retry decisions without unbounded retries."""

    def __init__(self, max_attempts=5, backoff_seconds=60, backoff_factor=2.0, max_backoff=3600):
        self.max_attempts = max(0, int(max_attempts))
        self.backoff_seconds = max(1, int(backoff_seconds))
        self.backoff_factor = float(backoff_factor) if backoff_factor else 1.0
        self.max_backoff = int(max_backoff)

    def should_retry(self, attempt, retryable=True):
        if not retryable:
            return False
        return attempt < self.max_attempts

    def next_delay_seconds(self, attempt):
        # attempt is 1-based after a failure
        delay = self.backoff_seconds * (self.backoff_factor ** max(0, attempt - 1))
        return int(min(delay, self.max_backoff))

    def next_retry_at(self, attempt, now=None):
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        return now + timedelta(seconds=self.next_delay_seconds(attempt))

    def classify_final_state(self, attempt, retryable=True):
        if self.should_retry(attempt, retryable=retryable):
            return 'retrying'
        return 'failed'


class RetryService:
    """Helper around RetryPolicy for services."""

    def __init__(self, max_attempts=5, backoff_seconds=60, backoff_factor=2.0):
        self.policy = RetryPolicy(
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            backoff_factor=backoff_factor,
        )

    def plan(self, attempt, retryable=True, now=None):
        status = self.policy.classify_final_state(attempt, retryable=retryable)
        result = {
            'attempt': attempt,
            'retryable': retryable,
            'status': status,
            'max_attempts': self.policy.max_attempts,
        }
        if status == 'retrying':
            result['next_retry_at'] = self.policy.next_retry_at(attempt, now=now)
            result['delay_seconds'] = self.policy.next_delay_seconds(attempt)
        else:
            result['next_retry_at'] = None
            result['delay_seconds'] = None
        return result
