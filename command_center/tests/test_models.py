# -*- coding: utf-8 -*-
"""Phase 3 domain model tests."""
import unittest

try:
    from odoo.exceptions import AccessError, UserError, ValidationError
    from odoo.tests import TransactionCase, tagged
    from odoo.tests.common import get_db_name
    _HAS_ODOO = True
except ImportError:  # pragma: no cover
    _HAS_ODOO = False
    TransactionCase = unittest.TestCase
    AccessError = UserError = ValidationError = Exception

    def tagged(*_args, **_kwargs):
        return lambda cls: cls

    def get_db_name():
        return False


def _odoo_db_ready():
    try:
        return bool(get_db_name())
    except Exception:
        return False


@unittest.skipUnless(_HAS_ODOO, 'Requires Odoo')
@tagged('post_install', '-at_install', 'cc_models')
class TestCcModels(TransactionCase):
    @classmethod
    def setUpClass(cls):
        if not _odoo_db_ready():
            raise unittest.SkipTest('Requires Odoo test runner')
        super().setUpClass()

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.site = self.env['cc.site'].create({
            'code': 'SITE-A',
            'location_label': 'North campus',
        })

    def test_models_load_and_mixin(self):
        expected = [
            'cc.mixin', 'cc.site', 'cc.alert', 'cc.incident',
            'cc.escalation.rule', 'cc.escalation.history',
            'cc.investigation.note', 'cc.report.definition',
            'cc.report.export', 'cc.ui.api',
        ]
        for name in expected:
            self.assertIn(name, self.env.registry)
        self.assertTrue(self.env['cc.mixin']._abstract)
        self.assertTrue(self.env['cc.ui.api']._transient)
        self.assertNotIn('cc.alert.type', self.env.registry)
        self.assertNotIn('va.event', self.env['cc.alert']._fields)
        for model in expected[1:]:
            self.assertTrue(hasattr(self.env[model], '_cc_require_user'))
            self.assertTrue(hasattr(self.env[model], '_cc_require_manager'))
            self.assertTrue(hasattr(self.env[model], '_cc_require_admin'))

    def test_site_required_fields_defaults_and_sequence_name(self):
        self.assertTrue(self.site.name)
        self.assertNotEqual(self.site.name, self.site.code)
        self.assertTrue(self.site.name.startswith('CC-SITE') or self.site.name)
        self.assertEqual(self.site.company_id, self.company)
        self.assertEqual(self.site.operational_status, 'normal')
        self.assertTrue(self.site.active)
        with self.assertRaises(Exception):
            self.env['cc.site'].create({'name': 'No code'})
        for status in ('normal', 'degraded', 'emergency', 'offline'):
            rec = self.env['cc.site'].create({'code': 'ST-%s' % status, 'operational_status': status})
            self.assertEqual(rec.operational_status, status)

    def test_site_code_unique_per_company(self):
        with self.assertRaises(ValidationError):
            self.env['cc.site'].create({'code': 'SITE-A', 'name': 'Dup'})

    def test_alert_fields_defaults_and_plain_source_pointer(self):
        alert = self.env['cc.alert'].create({
            'alert_type': 'intrusion',
            'severity': 'high',
            'source': 'video_analytics',
            'source_model': 'va.event',
            'source_id': 99,
            'site_id': self.site.id,
        })
        self.assertTrue(alert.name.startswith('CC-ALT') or alert.name)
        self.assertEqual(alert.state, 'open')
        self.assertFalse(alert.is_emergency)
        self.assertEqual(alert.source, 'video_analytics')
        self.assertEqual(alert.source_model, 'va.event')
        self.assertEqual(alert.source_id, 99)
        self.assertEqual(self.env['cc.alert']._fields['source_model'].type, 'char')
        self.assertEqual(self.env['cc.alert']._fields['source_id'].type, 'integer')
        self.assertFalse(self.env['cc.alert']._fields['source_id'].relational)
        for severity in ('low', 'medium', 'high', 'critical'):
            rec = self.env['cc.alert'].create({
                'alert_type': 'ops',
                'severity': severity,
            })
            self.assertEqual(rec.severity, severity)
        for source in ('manual', 'command_center', 'video_analytics', 'other'):
            rec = self.env['cc.alert'].create({
                'alert_type': 'ops',
                'source': source,
            })
            self.assertEqual(rec.source, source)
        for state in ('open', 'acknowledged', 'investigating', 'resolved', 'closed'):
            rec = self.env['cc.alert'].with_context(cc_lifecycle=True).create({
                'alert_type': 'ops',
                'state': state,
            })
            self.assertEqual(rec.state, state)

    def test_alert_protected_lifecycle_write(self):
        alert = self.env['cc.alert'].create({'alert_type': 'ops'})
        with self.assertRaises(UserError):
            alert.write({'state': 'acknowledged'})
        with self.assertRaises(UserError):
            alert.write({'is_emergency': True})
        alert.with_context(cc_lifecycle=True).write({
            'state': 'acknowledged',
            'acknowledged_uid': self.env.uid,
        })
        self.assertEqual(alert.state, 'acknowledged')

    def test_incident_fields_defaults_and_protection(self):
        incident = self.env['cc.incident'].create({
            'severity': 'medium',
            'site_id': self.site.id,
            'summary': 'Smoke reported',
        })
        self.assertTrue(incident.name.startswith('CC-INC') or incident.name)
        self.assertEqual(incident.state, 'open')
        self.assertTrue(incident.opened_at)
        with self.assertRaises(UserError):
            incident.write({'state': 'investigating'})
        incident.with_context(cc_lifecycle=True).write({'state': 'investigating'})
        self.assertEqual(incident.state, 'investigating')
        for severity in ('low', 'medium', 'high', 'critical'):
            rec = self.env['cc.incident'].create({'severity': severity})
            self.assertEqual(rec.severity, severity)

    def test_escalation_rule_and_history_fields(self):
        rule = self.env['cc.escalation.rule'].create({
            'name': 'Level 1',
            'level': 1,
            'delay_minutes': 15,
            'mode': 'automatic',
            'site_id': self.site.id,
        })
        self.assertTrue(rule.active)
        self.assertEqual(rule.mode, 'automatic')
        alert = self.env['cc.alert'].create({
            'alert_type': 'ops',
            'site_id': self.site.id,
        })
        history = self.env['cc.escalation.history'].create({
            'alert_id': alert.id,
            'rule_id': rule.id,
            'level': 1,
            'result': 'triggered',
            'actor_id': self.env.uid,
        })
        self.assertEqual(history.company_id, alert.company_id)
        self.assertTrue(history.timestamp)
        for result in ('triggered', 'notified', 'failed', 'acknowledged'):
            rec = self.env['cc.escalation.history'].create({
                'alert_id': alert.id,
                'result': result,
            })
            self.assertEqual(rec.result, result)
        for mode in ('automatic', 'manual'):
            rec = self.env['cc.escalation.rule'].create({
                'name': 'Mode %s' % mode,
                'mode': mode,
            })
            self.assertEqual(rec.mode, mode)

    def test_investigation_note_rules(self):
        alert = self.env['cc.alert'].create({'alert_type': 'ops', 'site_id': self.site.id})
        incident = self.env['cc.incident'].create({'site_id': self.site.id})
        with self.assertRaises(ValidationError):
            self.env['cc.investigation.note'].create({'body': 'No parent'})
        with self.assertRaises(ValidationError):
            self.env['cc.investigation.note'].create({
                'alert_id': alert.id,
                'body': '   ',
            })
        note = self.env['cc.investigation.note'].create({
            'alert_id': alert.id,
            'incident_id': incident.id,
            'body': 'Reviewed cameras',
            'user_id': False,
        })
        self.assertEqual(note.user_id, self.env.user)
        self.assertEqual(note.company_id, alert.company_id)
        with self.assertRaises(UserError):
            note.write({'body': 'edited'})

    def test_report_definition_and_export(self):
        for source in ('alerts', 'incidents', 'sites', 'emergency'):
            rec = self.env['cc.report.definition'].create({
                'name': 'R %s' % source,
                'source': source,
            })
            self.assertEqual(rec.source, source)
            self.assertTrue(rec.active)
            self.assertEqual(rec.owner_id, self.env.user)
        definition = self.env['cc.report.definition'].create({
            'name': 'Alerts export',
            'source': 'alerts',
            'field_names': ['name', 'state'],
            'filters_json': {'state': 'open'},
        })
        export_csv = self.env['cc.report.export'].create({
            'definition_id': definition.id,
            'export_format': 'csv',
            'filename': 'alerts.csv',
        })
        export_json = self.env['cc.report.export'].create({
            'definition_id': definition.id,
            'export_format': 'json',
            'filename': 'alerts.json',
        })
        self.assertEqual(export_csv.export_format, 'csv')
        self.assertEqual(export_json.export_format, 'json')
        self.assertEqual(export_csv.user_id, self.env.user)

    def _assert_rejected(self, error_types, func):
        try:
            func()
        except error_types:
            return
        self.fail('Expected %s' % (error_types,))

    def test_company_consistency(self):
        company_b = self.env['res.company'].create({'name': 'CC Other Co'})
        site_b = self.env['cc.site'].create({
            'code': 'SITE-B',
            'company_id': company_b.id,
        })
        mismatch = (UserError, ValidationError)
        self._assert_rejected(mismatch, lambda: self.env['cc.alert'].create({
            'alert_type': 'ops',
            'site_id': site_b.id,
            'company_id': self.company.id,
        }))
        self._assert_rejected(mismatch, lambda: self.env['cc.incident'].create({
            'site_id': site_b.id,
            'company_id': self.company.id,
        }))
        self._assert_rejected(mismatch, lambda: self.env['cc.escalation.rule'].create({
            'name': 'Bad rule',
            'site_id': site_b.id,
            'company_id': self.company.id,
        }))
        alert_a = self.env['cc.alert'].create({'alert_type': 'ops', 'site_id': self.site.id})
        incident_b = self.env['cc.incident'].create({
            'company_id': company_b.id,
            'site_id': site_b.id,
        })
        self._assert_rejected(mismatch, lambda: self.env['cc.investigation.note'].create({
            'alert_id': alert_a.id,
            'incident_id': incident_b.id,
            'body': 'mixed companies',
        }))

    def test_alert_incident_relationship(self):
        incident = self.env['cc.incident'].create({'site_id': self.site.id})
        alert = self.env['cc.alert'].create({
            'alert_type': 'ops',
            'site_id': self.site.id,
            'incident_id': incident.id,
        })
        self.assertIn(alert, incident.alert_ids)
        self.assertEqual(alert.incident_id, incident)
