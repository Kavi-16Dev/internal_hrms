# -*- coding: utf-8 -*-
from odoo.exceptions import UserError

from .common import KaviHrJobCustomCommon


class TestHrApplicantVersionHistoryWizard(KaviHrJobCustomCommon):
    # NOTE: exercised against `confidential_notes` rather than
    # `salary_structure` purely for setup convenience (no dependency on
    # `ats_recruitment_customization` field defaults/groups in this test
    # env). `salary_structure` goes through the exact same native-history/
    # version-history machinery (see test_hr_applicant.py::
    # test_get_versioned_fields), so coverage here is equivalent.

    def setUp(self):
        super().setUp()
        self.Wizard = self.env['hr.applicant.version.history.wizard']
        self.applicant.write({'confidential_notes': '<p>Offer A</p>'})
        self.applicant.write({'confidential_notes': '<p>Offer B</p>'})
        self.baseline_row = self.ApplicantHistory.search([
            ('applicant_id', '=', self.applicant.id), ('field_name', '=', '__baseline__'),
        ], limit=1)
        self.rows = self.ApplicantHistory.search([
            ('applicant_id', '=', self.applicant.id), ('field_name', '=', 'confidential_notes'),
        ], order='changed_on asc, id asc')

    def test_default_get_selects_latest_history(self):
        wizard = self.Wizard.with_context(default_applicant_id=self.applicant.id).create({
            'applicant_id': self.applicant.id,
        })
        latest = self.ApplicantHistory.search(
            [('applicant_id', '=', self.applicant.id)], order='changed_on desc, id desc', limit=1)
        self.assertEqual(wizard.history_id, latest)

    def test_open_field_snapshot_without_history_is_not_an_error(self):
        fresh_applicant = self.HrApplicant.with_user(self.manager_user).create({
            'partner_name': 'Fresh Candidate', 'job_id': self.job.id,
        })
        wizard = self.Wizard.create({'applicant_id': fresh_applicant.id})
        wizard.action_view_confidential_notes()
        self.assertFalse(wizard.history_id)
        self.assertTrue(wizard.field_snapshot_view)
        self.assertEqual(wizard.preview_field_label, 'Confidential Notes')

    def test_is_latest_version_and_diff(self):
        wizard_latest = self.Wizard.create({
            'applicant_id': self.applicant.id, 'history_id': self.rows[-1].id,
        })
        self.assertTrue(wizard_latest.is_latest_version)
        self.assertFalse(wizard_latest.diff_html)

        wizard_older = self.Wizard.create({
            'applicant_id': self.applicant.id, 'history_id': self.rows[0].id,
        })
        self.assertFalse(wizard_older.is_latest_version)
        self.assertTrue(wizard_older.diff_html)

    def test_restore_history_requires_selection(self):
        wizard = self.Wizard.create({'applicant_id': self.applicant.id})
        with self.assertRaises(UserError):
            wizard.action_restore_history()

    def test_restore_history_rejects_latest_version(self):
        wizard = self.Wizard.create({
            'applicant_id': self.applicant.id, 'history_id': self.rows[-1].id,
        })
        with self.assertRaises(UserError):
            wizard.action_restore_history()

    def test_restore_history_rejects_non_trackable_entries(self):
        wizard = self.Wizard.create({
            'applicant_id': self.applicant.id, 'history_id': self.baseline_row.id,
        })
        with self.assertRaises(UserError):
            wizard.action_restore_history()

    def test_restore_history_success(self):
        wizard = self.Wizard.create({
            'applicant_id': self.applicant.id, 'history_id': self.rows[0].id,
        })
        result = wizard.action_restore_history()
        self.assertEqual(result['params']['type'], 'success')
        self.assertIn('Offer A', self.applicant.confidential_notes)

    def test_action_discard_closes_wizard(self):
        wizard = self.Wizard.create({'applicant_id': self.applicant.id})
        self.assertEqual(wizard.action_discard(), {'type': 'ir.actions.act_window_close'})

    def test_restore_clears_native_history_metadata_for_restored_field(self):
        self.applicant.sudo().write({'html_field_history_metadata': {
            'confidential_notes': {'fake': 'stale-patch-data'},
        }})
        wizard = self.Wizard.create({
            'applicant_id': self.applicant.id, 'history_id': self.rows[0].id,
        })
        wizard.action_restore_history()
        self.assertNotIn('confidential_notes', self.applicant.html_field_history_metadata or {})
