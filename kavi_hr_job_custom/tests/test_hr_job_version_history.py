# -*- coding: utf-8 -*-
from .common import KaviHrJobCustomCommon


class TestHrJobVersionHistory(KaviHrJobCustomCommon):

    def test_selection_field_name_includes_all_kinds(self):
        options = dict(self.JobHistory._selection_field_name())
        self.assertIn('__baseline__', options)
        self.assertIn('budgeting_information', options)
        self.assertIn('key_responsibilities', options)
        self.assertIn('work_mode', options)

    def test_selection_field_changed_picker_excludes_baseline_and_work_mode(self):
        options = dict(self.JobHistory._selection_field_changed_picker())
        self.assertNotIn('__baseline__', options)
        self.assertNotIn('work_mode', options)
        self.assertIn('budgeting_information', options)
        self.assertIn('key_responsibilities', options)

    def test_compute_field_changed_picker(self):
        self.job.write({'budgeting_information': '<p>X</p>'})
        row = self.JobHistory.search([
            ('job_id', '=', self.job.id), ('field_name', '=', 'budgeting_information'),
        ], limit=1)
        self.assertEqual(row.field_changed_picker, 'budgeting_information')

        baseline = self.JobHistory.search([
            ('job_id', '=', self.job.id), ('field_name', '=', '__baseline__'),
        ], limit=1)
        # Not part of the visible picker options, so falsy.
        self.assertFalse(baseline.field_changed_picker)

    def test_onchange_field_changed_picker_loads_latest_values(self):
        self.job.write({'budgeting_information': '<p>Budget A</p>'})
        self.job.write({'key_responsibilities': '<p>Own delivery.</p>'})
        row = self.JobHistory.search([('job_id', '=', self.job.id)], limit=1, order='id asc')

        row.field_changed_picker = 'key_responsibilities'
        row._onchange_field_changed_picker()
        self.assertEqual(row.field_label, 'Key Roles and Responsibilities')
        self.assertIn('Own delivery', row.new_value)

    def test_compute_value_text_strips_html(self):
        self.job.write({'budgeting_information': '<p><b>50,000</b> USD</p>'})
        row = self.JobHistory.search([
            ('job_id', '=', self.job.id), ('field_name', '=', 'budgeting_information'),
        ], limit=1)
        self.assertEqual(row.new_value_text.strip(), '50,000 USD')

    # ------------------------------------------------------------------
    # write() protection: audit rows are immutable outside the internal
    # bypass context.
    # ------------------------------------------------------------------
    def test_write_protected_fields_dropped_without_context_flag(self):
        row = self.JobHistory.search([('job_id', '=', self.job.id)], limit=1)
        original_label = row.field_label
        row.write({'field_label': 'Tampered Label'})
        self.assertEqual(row.field_label, original_label)

    def test_write_protected_fields_allowed_with_context_flag(self):
        row = self.JobHistory.search([('job_id', '=', self.job.id)], limit=1)
        row.with_context(kavi_allow_history_write=True).write({'field_label': 'Corrected Label'})
        self.assertEqual(row.field_label, 'Corrected Label')

    def test_write_with_no_effective_vals_is_noop(self):
        row = self.JobHistory.search([('job_id', '=', self.job.id)], limit=1)
        result = row.write({'field_label': 'Should be dropped'})
        self.assertTrue(result)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def test_action_view_version_history_detail(self):
        row = self.JobHistory.search([('job_id', '=', self.job.id)], limit=1)
        action = row.action_view_version_history_detail()
        self.assertEqual(action['res_model'], 'hr.job.version.history')
        self.assertEqual(action['res_id'], row.id)
        self.assertEqual(action['view_mode'], 'form')

    def test_action_back_to_version_history_list(self):
        row = self.JobHistory.search([('job_id', '=', self.job.id)], limit=1)
        action = row.action_back_to_version_history_list()
        self.assertEqual(action['res_model'], 'hr.job.version.history')
        self.assertEqual(action['domain'], [('job_id', '=', self.job.id)])

    def test_action_discard_version_history_detail(self):
        row = self.JobHistory.search([('job_id', '=', self.job.id)], limit=1)
        action = row.action_discard_version_history_detail()
        self.assertEqual(action['res_model'], 'hr.job')
        self.assertEqual(action['res_id'], self.job.id)

    def test_name_get_format(self):
        row = self.JobHistory.search([('job_id', '=', self.job.id)], limit=1)
        self.assertIn(row.field_label, row.display_name)
