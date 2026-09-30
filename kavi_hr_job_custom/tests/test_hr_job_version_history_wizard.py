# -*- coding: utf-8 -*-
from odoo.exceptions import UserError

from .common import KaviHrJobCustomCommon


class TestHrJobVersionHistoryWizard(KaviHrJobCustomCommon):

    def setUp(self):
        super().setUp()
        self.Wizard = self.env['hr.job.version.history.wizard']
        self.job.write({'budgeting_information': '<p>Budget A</p>'})
        self.job.write({'budgeting_information': '<p>Budget B</p>'})
        self.baseline_row = self.JobHistory.search([
            ('job_id', '=', self.job.id), ('field_name', '=', '__baseline__'),
        ], limit=1)
        self.rows = self.JobHistory.search([
            ('job_id', '=', self.job.id), ('field_name', '=', 'budgeting_information'),
        ], order='changed_on asc, id asc')

    def test_default_get_selects_latest_history(self):
        wizard = self.Wizard.with_context(default_job_id=self.job.id).create({'job_id': self.job.id})
        latest = self.JobHistory.search([('job_id', '=', self.job.id)], order='changed_on desc, id desc', limit=1)
        self.assertEqual(wizard.history_id, latest)

    def test_action_toggle_comparison(self):
        wizard = self.Wizard.create({'job_id': self.job.id, 'history_id': self.rows[0].id})
        self.assertFalse(wizard.show_comparison)
        wizard.action_toggle_comparison()
        self.assertTrue(wizard.show_comparison)
        wizard.action_toggle_comparison()
        self.assertFalse(wizard.show_comparison)

    def test_open_field_snapshot_with_existing_history(self):
        wizard = self.Wizard.create({'job_id': self.job.id})
        wizard.action_view_budgeting_information()
        latest = self.JobHistory.search([
            ('job_id', '=', self.job.id), ('field_name', '=', 'budgeting_information'),
        ], order='changed_on desc, id desc', limit=1)
        self.assertEqual(wizard.history_id, latest)
        self.assertTrue(wizard.field_snapshot_view)
        self.assertEqual(wizard.snapshot_field_name, 'budgeting_information')

    def test_open_field_snapshot_without_existing_history_is_not_an_error(self):
        # Fresh job: key_responsibilities was never edited yet.
        fresh_job = self.HrJob.with_user(self.manager_user).create({'name': 'Fresh Job'})
        wizard = self.Wizard.create({'job_id': fresh_job.id})
        # Must not raise UserError('No recorded changes yet for this field.')
        wizard.action_view_key_responsibilities()
        self.assertFalse(wizard.history_id)
        self.assertTrue(wizard.field_snapshot_view)
        self.assertEqual(wizard.snapshot_field_name, 'key_responsibilities')
        self.assertEqual(wizard.preview_field_label, 'Key Roles and Responsibilities')
        self.assertIn('Key Roles and Responsibilities', wizard.preview_empty_message)

    def test_action_back_to_full_history_resets_snapshot_state(self):
        wizard = self.Wizard.create({'job_id': self.job.id})
        wizard.action_view_budgeting_information()
        wizard.action_back_to_full_history()
        self.assertFalse(wizard.field_snapshot_view)
        self.assertFalse(wizard.snapshot_field_name)
        self.assertFalse(wizard.show_comparison)

    # ------------------------------------------------------------------
    # diff_html / is_latest_version
    # ------------------------------------------------------------------
    def test_is_latest_version_true_for_most_recent_row(self):
        wizard = self.Wizard.create({'job_id': self.job.id, 'history_id': self.rows[-1].id})
        self.assertTrue(wizard.is_latest_version)
        self.assertFalse(wizard.diff_html)

    def test_is_latest_version_false_for_older_row_and_diff_populated(self):
        wizard = self.Wizard.create({'job_id': self.job.id, 'history_id': self.rows[0].id})
        self.assertFalse(wizard.is_latest_version)
        self.assertTrue(wizard.diff_html)
        self.assertIn('o_kavi_vh_diff_added', wizard.diff_html)
        self.assertIn('o_kavi_vh_diff_removed', wizard.diff_html)

    # ------------------------------------------------------------------
    # action_restore_history
    # ------------------------------------------------------------------
    def test_restore_history_requires_selection(self):
        wizard = self.Wizard.create({'job_id': self.job.id})
        with self.assertRaises(UserError):
            wizard.action_restore_history()

    def test_restore_history_rejects_latest_version(self):
        wizard = self.Wizard.create({'job_id': self.job.id, 'history_id': self.rows[-1].id})
        with self.assertRaises(UserError):
            wizard.action_restore_history()

    def test_restore_history_rejects_non_trackable_entries(self):
        wizard = self.Wizard.create({'job_id': self.job.id, 'history_id': self.baseline_row.id})
        with self.assertRaises(UserError):
            wizard.action_restore_history()

    def test_restore_history_success(self):
        wizard = self.Wizard.create({'job_id': self.job.id, 'history_id': self.rows[0].id})
        result = wizard.action_restore_history()
        self.assertEqual(result['params']['type'], 'success')
        self.assertIn('Budget A', self.job.budgeting_information)

    def test_action_discard_closes_wizard(self):
        wizard = self.Wizard.create({'job_id': self.job.id})
        result = wizard.action_discard()
        self.assertEqual(result, {'type': 'ir.actions.act_window_close'})
