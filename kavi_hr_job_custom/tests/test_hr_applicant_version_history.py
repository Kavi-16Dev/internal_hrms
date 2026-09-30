# -*- coding: utf-8 -*-
from .common import KaviHrJobCustomCommon


class TestHrApplicantVersionHistory(KaviHrJobCustomCommon):

    def test_compute_value_text_strips_html(self):
        self.applicant.write({'confidential_notes': '<p><i>Great</i> attitude</p>'})
        row = self.ApplicantHistory.search([
            ('applicant_id', '=', self.applicant.id), ('field_name', '=', 'confidential_notes'),
        ], limit=1)
        self.assertEqual(row.new_value_text.strip(), 'Great attitude')

    def test_action_view_version_history_detail(self):
        row = self.ApplicantHistory.search([('applicant_id', '=', self.applicant.id)], limit=1)
        action = row.action_view_version_history_detail()
        self.assertEqual(action['res_model'], 'hr.applicant.version.history')
        self.assertEqual(action['res_id'], row.id)

    def test_action_back_to_version_history_list(self):
        row = self.ApplicantHistory.search([('applicant_id', '=', self.applicant.id)], limit=1)
        action = row.action_back_to_version_history_list()
        self.assertEqual(action['domain'], [('applicant_id', '=', self.applicant.id)])

    def test_action_discard_version_history_detail(self):
        row = self.ApplicantHistory.search([('applicant_id', '=', self.applicant.id)], limit=1)
        action = row.action_discard_version_history_detail()
        self.assertEqual(action['res_model'], 'hr.applicant')
        self.assertEqual(action['res_id'], self.applicant.id)

    def test_name_get_format(self):
        row = self.ApplicantHistory.search([('applicant_id', '=', self.applicant.id)], limit=1)
        self.assertIn(row.field_label, row.display_name)
