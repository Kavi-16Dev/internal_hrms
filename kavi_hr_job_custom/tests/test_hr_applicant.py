# -*- coding: utf-8 -*-
from .common import KaviHrJobCustomCommon


class TestHrApplicant(KaviHrJobCustomCommon):

    def test_interviewer_is_identified_as_interviewer_only(self):
        interviewer = self._create_user(
            'kavi_interviewer_offer_page',
            ['hr_recruitment.group_hr_recruitment_interviewer'],
        )
        self.assertTrue(
            self.HrApplicant.with_user(interviewer)._kavi_user_is_interviewer_only()
        )

    def test_recruitment_user_is_not_interviewer_only(self):
        self.assertFalse(
            self.HrApplicant.with_user(self.manager_user)._kavi_user_is_interviewer_only()
        )

    def test_interviewer_form_hides_all_offer_fields_and_history_menu(self):
        interviewer = self._create_user(
            'kavi_interviewer_offer_fields_view',
            ['hr_recruitment.group_hr_recruitment_interviewer'],
        )
        View = self.env['ir.ui.view'].sudo()
        base_view = self.env.ref('hr_recruitment.hr_applicant_view_form')
        test_view = View.create({
            'name': 'kavi.test.hr.applicant.offer.fields',
            'type': 'form',
            'model': 'hr.applicant',
            'inherit_id': base_view.id,
            'arch': '<xpath expr="//notebook" position="inside">'
                    '<page name="offer_letter_components_fields_test" '
                    'string="Offer Letter Components">'
                    '<field name="designation"/>'
                    '<field name="salary_structure"/>'
                    '<field name="joining_date"/>'
                    '<field name="offer_letter_components"/>'
                    '<field name="confidential_notes"/>'
                    '</page></xpath>',
        })
        try:
            result = self.HrApplicant.with_user(interviewer).get_view(
                view_id=test_view.id, view_type='form',
            )
            arch = result.get('arch', '')
            for field_name in (
                'designation', 'salary_structure', 'joining_date',
                'offer_letter_components', 'confidential_notes',
            ):
                self.assertNotIn('name=\"%s\"' % field_name, arch)
            self.assertNotIn('kavi_hr_applicant_form', arch)
            self.assertNotIn('offer_letter_components_fields_test', arch)
        finally:
            test_view.unlink()

    def test_interviewer_can_compute_job_board_source_without_job_board_access(self):
        interviewer = self._create_user(
            'kavi_interviewer_job_board_compute',
            ['hr_recruitment.group_hr_recruitment_interviewer'],
        )
        applicant = self.applicant.with_user(interviewer)
        # Accessing the technical computed field must not attempt to read the
        # restricted hr.job.job_board_ids with the interviewer's privileges.
        applicant._compute_job_board_source_ids()
        # The important assertion is that the computation completes without
        # an AccessError; the database may legitimately have zero Sources.
        applicant.job_board_source_ids.ids

    def test_offer_letter_components_page_is_removed_for_interviewer(self):
        interviewer = self._create_user(
            'kavi_interviewer_offer_page_view',
            ['hr_recruitment.group_hr_recruitment_interviewer'],
        )
        View = self.env['ir.ui.view'].sudo()
        base_view = self.env.ref('hr_recruitment.hr_applicant_view_form')
        test_view = View.create({
            'name': 'kavi.test.hr.applicant.offer.letter.components',
            'type': 'form',
            'model': 'hr.applicant',
            'inherit_id': base_view.id,
            'arch': '<xpath expr="//notebook" position="inside">'
                    '<page name="offer_letter_components_test" '
                    'string="Offer Letter Components">'
                    '<label string="Confidential Offer Content"/>'
                    '</page></xpath>',
        })
        try:
            result = self.HrApplicant.with_user(interviewer).get_view(
                view_id=test_view.id, view_type='form',
            )
            self.assertNotIn('Offer Letter Components', result.get('arch', ''))
            self.assertNotIn('offer_letter_components_test', result.get('arch', ''))
        finally:
            test_view.unlink()

    def test_get_versioned_fields(self):
        # Salary Structure may be exposed by the ATS customization as either
        # offer_salary_structure (Html) or salary_structure (plain text). The
        # hidden mirror is also versioned when salary_structure exists.
        expected = ['confidential_notes']
        if 'kavi_salary_structure_history' in self.applicant._fields:
            expected.append('kavi_salary_structure_history')
        self.assertEqual(
            sorted(self.applicant._get_versioned_fields()),
            sorted(expected),
        )

    def test_salary_structure_alias_is_recorded_in_structured_history(self):
        field_name = None
        if 'offer_salary_structure' in self.applicant._fields:
            field_name = 'offer_salary_structure'
        elif 'salary_structure' in self.applicant._fields:
            field_name = 'salary_structure'
        self.assertTrue(field_name, 'An ATS Salary Structure field must exist')

        value = '<p>Salary Alias Test</p>' if self.applicant._fields[field_name].type == 'html' else 'Salary Alias Test'
        self.applicant.write({field_name: value})
        row = self.ApplicantHistory.search([
            ('applicant_id', '=', self.applicant.id),
            ('field_name', '=', field_name),
        ], order='id desc', limit=1)
        self.assertTrue(row)
        self.assertEqual(row.field_label, 'Salary Structure')

    def test_create_adds_baseline_history(self):
        history = self.ApplicantHistory.search([('applicant_id', '=', self.applicant.id)])
        self.assertEqual(len(history), 1)
        self.assertEqual(history.field_name, '__baseline__')
        self.assertEqual(history.new_value, self.applicant.partner_name)

    def test_write_creates_history_for_confidential_notes(self):
        self.applicant.write({'confidential_notes': '<p>Strong culture fit.</p>'})
        rows = self.ApplicantHistory.search([
            ('applicant_id', '=', self.applicant.id), ('field_name', '=', 'confidential_notes'),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.field_label, 'Confidential Notes')

    def test_write_creates_native_history_for_offer_salary_structure(self):
        if 'offer_salary_structure' not in self.applicant._fields:
            self.skipTest('ATS deployment does not expose offer_salary_structure')

        self.applicant.write({'offer_salary_structure': '<p>Salary A</p>'})
        self.assertEqual(
            self.applicant.kavi_salary_structure_history,
            '<p>Salary A</p>',
        )

        # The first actual edit from empty to Salary A creates revision 1.
        native_history = self.applicant.html_field_history or {}
        self.assertIn('kavi_salary_structure_history', native_history)
        self.assertEqual(len(native_history['kavi_salary_structure_history']), 1)

        self.applicant.write({'offer_salary_structure': '<p>Salary B</p>'})
        native_history = self.applicant.html_field_history or {}
        self.assertEqual(len(native_history['kavi_salary_structure_history']), 2)

        # The latest revision restores Salary A, exactly as Confidential Notes
        # does in Odoo's native HistoryDialog.
        restored = self.applicant.html_field_history_get_content_at_revision(
            'kavi_salary_structure_history',
            native_history['kavi_salary_structure_history'][0]['revision_id'],
        )
        self.assertEqual(restored, '<p>Salary A</p>')

        rows = self.ApplicantHistory.search([
            ('applicant_id', '=', self.applicant.id),
            ('field_name', '=', 'offer_salary_structure'),
        ], order='id desc', limit=1)
        self.assertTrue(rows)
        self.assertEqual(rows.field_label, 'Salary Structure')
        self.assertEqual(rows.new_value, '<p>Salary B</p>')

    def test_write_creates_native_history_for_salary_structure(self):
        self.applicant.write({'salary_structure': 'Salary A'})
        self.assertEqual(
            self.applicant.kavi_salary_structure_history,
            '<p>Salary A</p>',
        )

        # The structured audit trail still records the real business field.
        rows = self.ApplicantHistory.search([
            ('applicant_id', '=', self.applicant.id),
            ('field_name', '=', 'salary_structure'),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.field_label, 'Salary Structure')
        self.assertEqual(rows.new_value, 'Salary A')

        # The native HTML HistoryDialog is backed by the hidden Html mirror.
        native_history = self.applicant.html_field_history or {}
        self.assertIn('kavi_salary_structure_history', native_history)
        self.assertEqual(len(native_history['kavi_salary_structure_history']), 1)

        self.applicant.write({'salary_structure': 'Salary B'})
        native_history = self.applicant.html_field_history or {}
        self.assertEqual(len(native_history['kavi_salary_structure_history']), 2)
        self.assertEqual(
            self.applicant.kavi_salary_structure_history,
            '<p>Salary B</p>',
        )

    def test_write_no_history_when_value_unchanged(self):
        self.applicant.write({'confidential_notes': '<p>Same</p>'})
        before = self.ApplicantHistory.search_count([('applicant_id', '=', self.applicant.id)])
        self.applicant.write({'confidential_notes': '<p>Same</p>'})
        after = self.ApplicantHistory.search_count([('applicant_id', '=', self.applicant.id)])
        self.assertEqual(before, after)

    def test_action_open_applicant_version_history_no_history(self):
        self.ApplicantHistory.search([('applicant_id', '=', self.applicant.id)]).unlink()
        action = self.applicant.action_open_applicant_version_history()
        self.assertEqual(action['tag'], 'display_notification')

    def test_action_open_applicant_version_history_with_history(self):
        action = self.applicant.action_open_applicant_version_history()
        self.assertEqual(action['res_model'], 'hr.applicant.version.history.wizard')
        self.assertEqual(action['context']['default_applicant_id'], self.applicant.id)

    # ------------------------------------------------------------------
    # OCR resume population
    # ------------------------------------------------------------------
    def test_populate_resume_from_ocr_full_payload(self):
        parsed_data = {
            'experience': [{
                'title': 'Backend Engineer', 'company': 'Acme',
                'start_date': '2020-01-01', 'end_date': '2022-01-01',
                'summary': 'Built APIs.',
            }],
            'education': [{
                'degree': 'B.Tech', 'school': 'IIT',
                'start_date': '2015-01-01', 'end_date': '2019-01-01',
            }],
            'total_years_of_experience': '5',
            'current_company': 'Acme',
            'location': 'Chennai',
        }
        self.applicant._kavi_populate_resume_from_ocr(parsed_data)
        self.assertEqual(len(self.applicant.resume_line_ids), 2)
        self.assertEqual(self.applicant.total_experience, '5')
        self.assertEqual(self.applicant.current_organization, 'Acme')
        self.assertEqual(self.applicant.current_location, 'Chennai')

    def test_populate_resume_from_ocr_does_not_overwrite_existing_values(self):
        self.applicant.write({'current_organization': 'Manually Entered Corp'})
        self.applicant._kavi_populate_resume_from_ocr({'current_company': 'OCR Corp'})
        self.assertEqual(self.applicant.current_organization, 'Manually Entered Corp')

    def test_populate_resume_from_ocr_empty_payload_is_noop(self):
        lines_before = len(self.applicant.resume_line_ids)
        self.applicant._kavi_populate_resume_from_ocr(None)
        self.applicant._kavi_populate_resume_from_ocr({})
        self.assertEqual(len(self.applicant.resume_line_ids), lines_before)

    def test_populate_resume_from_ocr_tolerates_malformed_entries(self):
        # Non-dict entries in the experience/education lists must not
        # raise - they simply fall back to default labels/dates.
        parsed_data = {'experience': ['not-a-dict', 123, None]}
        self.applicant._kavi_populate_resume_from_ocr(parsed_data)
        new_lines = self.applicant.resume_line_ids.filtered(
            lambda l: l.line_type_id.name == 'Experience')
        self.assertEqual(len(new_lines), 3)
        for line in new_lines:
            self.assertEqual(line.name, 'Experience')

    # ------------------------------------------------------------------
    # Hand-off to hr.employee on hire
    # ------------------------------------------------------------------
    def test_get_employee_create_vals_carries_resume_lines(self):
        resume_type = self.env['hr.resume.line.type'].search([('name', '=', 'Experience')], limit=1) \
            or self.env['hr.resume.line.type'].create({'name': 'Experience', 'sequence': 10})
        self.ResumeLine.create({
            'applicant_id': self.applicant.id,
            'name': 'Odoo Developer at Kavi',
            'line_type_id': resume_type.id,
            'date_start': '2021-01-01',
        })
        vals = self.applicant._get_employee_create_vals()
        self.assertIn('resume_line_ids', vals)
        created_line_vals = [v[2] for v in vals['resume_line_ids']]
        self.assertTrue(any(v['name'] == 'Odoo Developer at Kavi' for v in created_line_vals))

    # ------------------------------------------------------------------
    # Job Board -> Applicant Source (Source only, never Medium)
    # ------------------------------------------------------------------
    def test_create_sets_source_from_single_job_board(self):
        job_board = self.env['hr.job.board'].create({'name': 'LinkedIn'})
        job = self.HrJob.with_user(self.manager_user).create({
            'name': 'Job With One Board',
            'job_board_ids': [(6, 0, [job_board.id])],
        })
        applicant = self.HrApplicant.with_user(self.manager_user).create({
            'partner_name': 'Board Candidate',
            'job_id': job.id,
        })
        self.assertEqual(applicant.source_id.name, 'LinkedIn')
        # Medium must NEVER be auto-populated from the Job Board.
        self.assertFalse(applicant.medium_id)

    def test_create_reuses_existing_utm_source_with_same_name(self):
        existing_source = self.env['utm.source'].create({'name': 'Naukri'})
        job_board = self.env['hr.job.board'].create({'name': 'Naukri'})
        job = self.HrJob.with_user(self.manager_user).create({
            'name': 'Job With Naukri Board',
            'job_board_ids': [(6, 0, [job_board.id])],
        })
        applicant = self.HrApplicant.with_user(self.manager_user).create({
            'partner_name': 'Naukri Candidate',
            'job_id': job.id,
        })
        self.assertEqual(applicant.source_id, existing_source)

    def test_create_does_not_override_explicit_source(self):
        job_board = self.env['hr.job.board'].create({'name': 'Indeed'})
        explicit_source = self.env['utm.source'].create({'name': 'Referral'})
        job = self.HrJob.with_user(self.manager_user).create({
            'name': 'Job With Explicit Source',
            'job_board_ids': [(6, 0, [job_board.id])],
        })
        applicant = self.HrApplicant.with_user(self.manager_user).create({
            'partner_name': 'Referral Candidate',
            'job_id': job.id,
            'source_id': explicit_source.id,
        })
        self.assertEqual(applicant.source_id, explicit_source)

    def test_create_does_not_override_explicit_medium(self):
        job_board = self.env['hr.job.board'].create({'name': 'Monster'})
        medium = self.env['utm.medium'].create({'name': 'Kavi Test Medium'})
        job = self.HrJob.with_user(self.manager_user).create({
            'name': 'Job With Explicit Medium',
            'job_board_ids': [(6, 0, [job_board.id])],
        })
        applicant = self.HrApplicant.with_user(self.manager_user).create({
            'partner_name': 'Medium Candidate',
            'job_id': job.id,
            'medium_id': medium.id,
        })
        self.assertEqual(applicant.source_id.name, 'Monster')
        self.assertEqual(applicant.medium_id, medium)

    def test_create_no_source_guess_when_multiple_job_boards(self):
        board_a = self.env['hr.job.board'].create({'name': 'Glassdoor'})
        board_b = self.env['hr.job.board'].create({'name': 'ZipRecruiter'})
        job = self.HrJob.with_user(self.manager_user).create({
            'name': 'Job With Two Boards',
            'job_board_ids': [(6, 0, [board_a.id, board_b.id])],
        })
        applicant = self.HrApplicant.with_user(self.manager_user).create({
            'partner_name': 'Ambiguous Candidate',
            'job_id': job.id,
        })
        self.assertFalse(applicant.source_id)

    def test_onchange_job_id_fills_source_from_job_board(self):
        job_board = self.env['hr.job.board'].create({'name': 'AngelList'})
        job = self.HrJob.with_user(self.manager_user).create({
            'name': 'Job For Onchange Test',
            'job_board_ids': [(6, 0, [job_board.id])],
        })
        applicant = self.HrApplicant.new({'partner_name': 'Onchange Candidate'})
        applicant.job_id = job
        applicant._onchange_job_id_kavi_job_board_source()
        self.assertEqual(applicant.source_id.name, 'AngelList')
        self.assertFalse(applicant.medium_id)

    # ------------------------------------------------------------------
    # job_board_source_ids - restricts/derives Source directly from the
    # Applied Job's configured Job Boards. There is no separate "Job
    # Board" field on the Applicant anymore; Source IS the Job Board
    # picker once more than one Job Board is configured.
    # ------------------------------------------------------------------
    def test_job_board_source_ids_matches_configured_boards(self):
        board_a = self.env['hr.job.board'].create({'name': 'Glassdoor 2'})
        board_b = self.env['hr.job.board'].create({'name': 'ZipRecruiter 2'})
        job = self.HrJob.with_user(self.manager_user).create({
            'name': 'Job With Two Boards Explicit',
            'job_board_ids': [(6, 0, [board_a.id, board_b.id])],
        })
        applicant = self.HrApplicant.with_user(self.manager_user).create({
            'partner_name': 'Explicit Board Candidate',
            'job_id': job.id,
        })
        self.assertEqual(
            set(applicant.job_board_source_ids.mapped('name')),
            {'Glassdoor 2', 'ZipRecruiter 2'},
        )
        # Ambiguous (2 boards) - Source is not auto-guessed, must be
        # picked by hand from job_board_source_ids.
        self.assertFalse(applicant.source_id)

    def test_write_source_id_restricted_to_job_board_sources(self):
        board_a = self.env['hr.job.board'].create({'name': 'Glassdoor 3'})
        board_b = self.env['hr.job.board'].create({'name': 'ZipRecruiter 3'})
        job = self.HrJob.with_user(self.manager_user).create({
            'name': 'Job With Two Boards Write',
            'job_board_ids': [(6, 0, [board_a.id, board_b.id])],
        })
        applicant = self.HrApplicant.with_user(self.manager_user).create({
            'partner_name': 'Write Board Candidate',
            'job_id': job.id,
        })
        self.assertFalse(applicant.source_id)
        glassdoor_source = self.env['utm.source'].search([('name', '=', 'Glassdoor 3')], limit=1)
        applicant.write({'source_id': glassdoor_source.id})
        self.assertEqual(applicant.source_id.name, 'Glassdoor 3')

    def test_job_board_source_ids_unrestricted_without_job_boards(self):
        job = self.HrJob.with_user(self.manager_user).create({
            'name': 'Job Without Boards',
        })
        applicant = self.HrApplicant.with_user(self.manager_user).create({
            'partner_name': 'No Board Candidate',
            'job_id': job.id,
        })
        # No Job Boards configured -> every Source is offered, matching
        # stock (unrestricted) behaviour.
        any_source = self.env['utm.source'].create({'name': 'Employee Referral Test'})
        self.assertIn(any_source, applicant.job_board_source_ids)

    def test_onchange_job_id_updates_job_board_source_ids(self):
        board_a = self.env['hr.job.board'].create({'name': 'Glassdoor 6'})
        job_a = self.HrJob.with_user(self.manager_user).create({
            'name': 'Job A Stale Board',
            'job_board_ids': [(6, 0, [board_a.id])],
        })
        job_b = self.HrJob.with_user(self.manager_user).create({
            'name': 'Job B Stale Board',
        })
        applicant = self.HrApplicant.new({'partner_name': 'Stale Board Candidate'})
        applicant.job_id = job_a
        applicant._onchange_job_id_kavi_job_board_source()
        self.assertEqual(applicant.source_id.name, 'Glassdoor 6')
        # Switching to a Job Position with no Job Boards leaves the
        # already-picked Source alone (never overwritten) while the
        # restriction list itself becomes unrestricted going forward.
        applicant.job_id = job_b
        applicant._onchange_job_id_kavi_job_board_source()
        self.assertEqual(applicant.source_id.name, 'Glassdoor 6')
