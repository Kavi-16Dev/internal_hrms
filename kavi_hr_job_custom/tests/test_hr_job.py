# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError

from .common import KaviHrJobCustomCommon


class TestHrJobInterviewerViewOnlyAccess(KaviHrJobCustomCommon):
    """Interviewer access to the two confidential Html fields is no
    longer symmetric:

      - key_responsibilities: still view-only. An Interviewer can read
        it once it holds data, but can never edit it - not through the
        form (get_view() readonly injection) and not through a direct
        write() call (server-side AccessError guard).

      - budgeting_information: now fully hidden from Interviewers. It is
        excluded from the field's own `groups` (models/hr_job.py) and
        from the "Budgeting Information" <page>'s `groups` (views/
        hr_job_views.xml), so an Interviewer cannot read OR write it
        through any channel - the ORM enforces this automatically
        (silent empty read, AccessError on write), with no manual
        get_view()/write() guard needed for this field any more.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.interviewer_user = cls._create_user(
            'kavi_interviewer', ['hr_recruitment.group_hr_recruitment_interviewer'])
        # A user who is BOTH an Interviewer and a Recruitment Officer
        # should be treated as an editor, not as view-only.
        cls.interviewer_and_user = cls._create_user(
            'kavi_interviewer_and_user', [
                'hr_recruitment.group_hr_recruitment_interviewer',
                'hr_recruitment.group_hr_recruitment_user',
            ])

        cls.job.write({
            'budgeting_information': '<p>Confidential budget details.</p>',
            'key_responsibilities': '<p>Own the recruitment pipeline.</p>',
        })

    def test_interviewer_only_flag(self):
        self.assertTrue(
            self.job.with_user(self.interviewer_user)._kavi_user_is_interviewer_only())
        self.assertFalse(
            self.job.with_user(self.interviewer_and_user)._kavi_user_is_interviewer_only())
        self.assertFalse(
            self.job.with_user(self.manager_user)._kavi_user_is_interviewer_only())

    def test_interviewer_can_read_key_responsibilities_only(self):
        job_as_interviewer = self.job.with_user(self.interviewer_user)
        self.assertIn(
            'Own the recruitment pipeline', job_as_interviewer.key_responsibilities)

    def test_interviewer_cannot_read_budgeting_information(self):
        # Field-level `groups` restriction: an unauthorized user's read
        # of a restricted field is silently empty, never an error/leak.
        job_as_interviewer = self.job.with_user(self.interviewer_user)
        self.assertFalse(job_as_interviewer.budgeting_information)

    def test_interviewer_not_in_budgeting_information_fields_get(self):
        # Stronger check than a silently-empty read: the field must not
        # even be advertised to an Interviewer via fields_get(), i.e. it
        # is completely absent, not just blank.
        fields_get = self.job.with_user(self.interviewer_user).fields_get(
            ['budgeting_information'])
        self.assertNotIn('budgeting_information', fields_get)

    def test_manager_still_sees_budgeting_information_in_fields_get(self):
        fields_get = self.job.with_user(self.manager_user).fields_get(
            ['budgeting_information'])
        self.assertIn('budgeting_information', fields_get)

    def test_interviewer_cannot_write_budgeting_information(self):
        with self.assertRaises(AccessError):
            self.job.with_user(self.interviewer_user).write({
                'budgeting_information': '<p>Tampered.</p>',
            })

    def test_interviewer_cannot_write_key_responsibilities(self):
        with self.assertRaises(AccessError):
            self.job.with_user(self.interviewer_user).write({
                'key_responsibilities': '<p>Tampered.</p>',
            })

    def test_interviewer_and_user_can_still_edit(self):
        # Holding the Interviewer group alongside an edit group must not
        # regress that user's normal edit access.
        self.job.with_user(self.interviewer_and_user).write({
            'budgeting_information': '<p>Updated by officer.</p>',
        })
        self.assertIn('Updated by officer', self.job.budgeting_information)

    def test_get_view_hides_budgeting_information_page_for_interviewer(self):
        # Budgeting Information must be completely absent from an
        # Interviewer's compiled arch - not present-but-readonly, not
        # present-but-invisible, simply not there at all (both the
        # <page> and the <field> are group-restricted away from them).
        view = self.job.with_user(self.interviewer_user).get_view(view_type='form')
        self.assertNotIn('name="budgeting_information"', view['arch'])
        self.assertNotIn('name="budgeting_information_page"', view['arch'])

    def test_get_view_shows_budgeting_information_for_manager(self):
        view = self.job.with_user(self.manager_user).get_view(view_type='form')
        self.assertIn('name="budgeting_information"', view['arch'])
        self.assertIn('name="budgeting_information_page"', view['arch'])
        self.assertNotRegex(
            view['arch'],
            r'<field[^>]*name="budgeting_information"[^>]*readonly="1"',
        )

    def test_get_view_marks_key_responsibilities_readonly_for_interviewer(self):
        view = self.job.with_user(self.interviewer_user).get_view(view_type='form')
        self.assertIn('name="key_responsibilities"', view['arch'])
        self.assertRegex(
            view['arch'],
            r'<field[^>]*name="key_responsibilities"[^>]*readonly="1"',
        )

    def test_get_view_does_not_mark_readonly_for_manager(self):
        view = self.job.with_user(self.manager_user).get_view(view_type='form')
        self.assertNotRegex(
            view['arch'],
            r'<field[^>]*name="budgeting_information"[^>]*readonly="1"',
        )
        self.assertNotRegex(
            view['arch'],
            r'<field[^>]*name="key_responsibilities"[^>]*readonly="1"',
        )


class TestHrJob(KaviHrJobCustomCommon):

    # ------------------------------------------------------------------
    # _get_versioned_fields / native html history wiring
    # ------------------------------------------------------------------
    def test_get_versioned_fields(self):
        self.assertEqual(
            sorted(self.job._get_versioned_fields()),
            sorted(['budgeting_information', 'key_responsibilities']),
        )

    def test_key_responsibilities_field_registered(self):
        # Regression test for the KeyError('key_responsibilities') RPC
        # error: the field must actually be registered on the model.
        self.assertIn('key_responsibilities', self.job._fields)
        self.assertEqual(self.job._fields['key_responsibilities'].type, 'html')

    # ------------------------------------------------------------------
    # create() baseline history
    # ------------------------------------------------------------------
    def test_create_adds_baseline_history(self):
        history = self.JobHistory.search([('job_id', '=', self.job.id)])
        self.assertEqual(len(history), 1)
        self.assertEqual(history.field_name, '__baseline__')
        self.assertEqual(history.new_value, self.job.name)

    # ------------------------------------------------------------------
    # write() -> structured history for Html tracked fields
    # ------------------------------------------------------------------
    def test_write_creates_history_for_budgeting_information(self):
        self.job.write({'budgeting_information': '<p>Budget v1</p>'})
        rows = self.JobHistory.search([
            ('job_id', '=', self.job.id), ('field_name', '=', 'budgeting_information'),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.field_label, 'Budgeting Information')
        self.assertEqual(rows.old_value, False)
        self.assertIn('Budget v1', rows.new_value)

        self.job.write({'budgeting_information': '<p>Budget v2</p>'})
        rows = self.JobHistory.search([
            ('job_id', '=', self.job.id), ('field_name', '=', 'budgeting_information'),
        ])
        self.assertEqual(len(rows), 2, "A second distinct edit should add a second row")

    def test_write_creates_history_for_key_responsibilities(self):
        self.job.write({'key_responsibilities': '<p>Own the backend.</p>'})
        rows = self.JobHistory.search([
            ('job_id', '=', self.job.id), ('field_name', '=', 'key_responsibilities'),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.field_label, 'Key Roles and Responsibilities')

    def test_write_no_history_row_when_value_unchanged(self):
        self.job.write({'budgeting_information': '<p>Same</p>'})
        count_before = self.JobHistory.search_count([
            ('job_id', '=', self.job.id), ('field_name', '=', 'budgeting_information'),
        ])
        # Writing the identical value again must not create a new row.
        self.job.write({'budgeting_information': '<p>Same</p>'})
        count_after = self.JobHistory.search_count([
            ('job_id', '=', self.job.id), ('field_name', '=', 'budgeting_information'),
        ])
        self.assertEqual(count_before, count_after)

    def test_write_unrelated_field_creates_no_history(self):
        count_before = self.JobHistory.search_count([('job_id', '=', self.job.id)])
        self.job.write({'name': 'Renamed Job Title'})
        count_after = self.JobHistory.search_count([('job_id', '=', self.job.id)])
        self.assertEqual(count_before, count_after)

    # ------------------------------------------------------------------
    # write() -> structured history for the Selection tracked field
    # ------------------------------------------------------------------
    def test_write_creates_history_for_work_mode(self):
        self.job.write({'work_mode': 'hybrid'})
        row = self.JobHistory.search([
            ('job_id', '=', self.job.id), ('field_name', '=', 'work_mode'),
        ])
        self.assertEqual(len(row), 1)
        self.assertEqual(row.field_label, 'Work Mode')
        self.assertEqual(row.old_value_text, '(empty)')
        self.assertEqual(row.new_value_text, 'Hybrid')

        self.job.write({'work_mode': 'onsite'})
        rows = self.JobHistory.search([
            ('job_id', '=', self.job.id), ('field_name', '=', 'work_mode'),
        ], order='changed_on asc, id asc')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1].old_value_text, 'Hybrid')
        self.assertEqual(rows[1].new_value_text, 'Onsite')

    def test_write_multiple_tracked_fields_in_one_call(self):
        count_before = self.JobHistory.search_count([('job_id', '=', self.job.id)])
        self.job.write({
            'budgeting_information': '<p>50k</p>',
            'key_responsibilities': '<p>Lead the team.</p>',
            'work_mode': 'office',
        })
        count_after = self.JobHistory.search_count([('job_id', '=', self.job.id)])
        self.assertEqual(count_after - count_before, 3)

    # ------------------------------------------------------------------
    # _get_kavi_tracked_fields fallback behaviour
    # ------------------------------------------------------------------
    def test_get_kavi_tracked_fields_reads_configuration(self):
        tracked = self.job._get_kavi_tracked_fields()
        self.assertEqual(tracked.get('budgeting_information'), 'Budgeting Information')
        self.assertEqual(tracked.get('key_responsibilities'), 'Key Roles and Responsibilities')

    def test_get_kavi_tracked_fields_falls_back_when_none_configured(self):
        (self.tracked_budgeting | self.tracked_key_resp).write({'active': False})
        tracked = self.job._get_kavi_tracked_fields()
        self.assertEqual(tracked, self.job._KAVI_HTML_TRACKED_FIELDS_FALLBACK)
        (self.tracked_budgeting | self.tracked_key_resp).write({'active': True})

    # ------------------------------------------------------------------
    # action_open_job_version_history
    # ------------------------------------------------------------------
    def test_action_open_job_version_history_no_history(self):
        # Baseline creation is best-effort; simulate the edge case where
        # a job genuinely has zero history rows.
        self.JobHistory.search([('job_id', '=', self.job.id)]).unlink()
        action = self.job.action_open_job_version_history()
        self.assertEqual(action['tag'], 'display_notification')
        self.assertEqual(action['params']['type'], 'info')

    def test_action_open_job_version_history_with_history(self):
        action = self.job.action_open_job_version_history()
        self.assertEqual(action['res_model'], 'hr.job.version.history.wizard')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['context']['default_job_id'], self.job.id)

    # ------------------------------------------------------------------
    # Vendor -> Tracker Link automation
    # ------------------------------------------------------------------
    def test_write_vendor_id_creates_tracker_link(self):
        source = self.env['utm.source'].create({'name': 'LinkedIn Source Test'})
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Acme Staffing',
            'email': 'acme@example.com',
            'source_id': source.id,
        })
        self.job.write({'vendor_id': vendor.id})
        link = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', vendor.id),
        ])
        self.assertEqual(len(link), 1)
        self.assertIn('utm_source=', link.url)

    def test_write_vendor_id_does_not_duplicate_tracker_link(self):
        source = self.env['utm.source'].create({'name': 'Naukri Source Test'})
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Beta Staffing',
            'email': 'beta@example.com',
            'source_id': source.id,
        })
        self.job.write({'vendor_id': vendor.id})
        # Removing and re-adding the same vendor must not create a 2nd link.
        self.job.write({'vendor_id': False})
        self.job.write({'vendor_id': vendor.id})
        links = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', vendor.id),
        ])
        self.assertEqual(len(links), 1)

    # ------------------------------------------------------------------
    # Job Board -> EXISTING Applicant Source (retroactive sync)
    # ------------------------------------------------------------------
    def test_write_job_board_ids_fills_source_on_existing_applicant(self):
        # self.applicant (from common setUp) already exists on self.job,
        # with no Source - exactly the "Job Board added after the
        # Applicant already existed" scenario.
        self.assertFalse(self.applicant.source_id)

        job_board = self.env['hr.job.board'].create({'name': 'Ram'})
        self.job.with_user(self.manager_user).write({
            'job_board_ids': [(6, 0, [job_board.id])],
        })

        self.assertEqual(self.applicant.source_id.name, 'Ram')

    def test_write_job_board_ids_does_not_override_existing_source(self):
        explicit_source = self.env['utm.source'].create({'name': 'Referral Test'})
        self.applicant.write({'source_id': explicit_source.id})

        job_board = self.env['hr.job.board'].create({'name': 'Naukri'})
        self.job.with_user(self.manager_user).write({
            'job_board_ids': [(6, 0, [job_board.id])],
        })

        self.assertEqual(self.applicant.source_id, explicit_source)

    def test_write_job_board_ids_skips_sync_when_ambiguous(self):
        board_a = self.env['hr.job.board'].create({'name': 'LinkedIn Retro'})
        board_b = self.env['hr.job.board'].create({'name': 'Indeed Retro'})
        self.job.with_user(self.manager_user).write({
            'job_board_ids': [(6, 0, [board_a.id, board_b.id])],
        })
        self.assertFalse(self.applicant.source_id)

    def test_build_tracker_url_uses_website_url_when_present(self):
        source = self.env['utm.source'].create({'name': 'Indeed Source Test'})
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Gamma Staffing',
            'email': 'gamma@example.com',
            'source_id': source.id,
        })
        self.job.website_url = '/jobs/custom-slug'
        url = self.job._build_tracker_url(vendor)
        self.assertIn('/jobs/custom-slug', url)
        self.assertIn('utm_source=Indeed+Source+Test', url.replace('%20', '+'))

    def test_build_tracker_url_falls_back_to_default_path(self):
        source = self.env['utm.source'].create({'name': 'Monster Source Test'})
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Delta Staffing',
            'email': 'delta@example.com',
            'source_id': source.id,
        })
        self.job.website_url = False
        url = self.job._build_tracker_url(vendor)
        self.assertIn('/jobs/detail/%s' % self.job.id, url)

    def test_build_tracker_url_falls_back_when_website_url_is_hash_placeholder(self):
        # Regression: website_url is '#' (not False/empty) whenever the
        # job hasn't resolved a real published route yet, e.g. before
        # the Job Position is published. A plain `self.website_url or
        # <fallback>` treats '#' as truthy and never falls through,
        # producing "<base_url>#?utm_source=...&utm_medium=..." instead
        # of a real path.
        source = self.env['utm.source'].create({'name': 'Hash Source Test'})
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Epsilon Staffing',
            'email': 'epsilon@example.com',
            'source_id': source.id,
        })
        self.job.website_url = '#'
        url = self.job._build_tracker_url(vendor)
        self.assertIn('/jobs/detail/%s' % self.job.id, url)
        self.assertNotIn('#?', url)

    # ------------------------------------------------------------------
    # Regression: restoring a native-history field must not leave the
    # native cog-menu History dialog crashing on its next use (RPC_ERROR
    # IndexError in html_editor's apply_patch).
    # ------------------------------------------------------------------
    def test_reset_native_html_history_noop_when_no_metadata(self):
        # Must be a safe no-op when there is nothing to clear (e.g. the
        # field was never edited through the live collaborative editor).
        self.job._kavi_reset_native_html_history(['key_responsibilities'])
        self.assertFalse(self.job.html_field_history_metadata)

    def test_reset_native_html_history_clears_only_requested_field(self):
        self.job.sudo().write({'html_field_history_metadata': {
            'key_responsibilities': {'fake': 'stale-patch-data'},
            'budgeting_information': {'fake': 'keep-me'},
        }})
        self.job._kavi_reset_native_html_history(['key_responsibilities'])
        metadata = self.job.html_field_history_metadata or {}
        self.assertNotIn('key_responsibilities', metadata)
        self.assertIn('budgeting_information', metadata)

    # ------------------------------------------------------------------
    # Regression: key_responsibilities pre-existed this module with real
    # content on some records, populated through a path that never went
    # through write() while native history tracking was active (e.g. the
    # "Offer Letter Components" page added by Studio/another
    # customization). Its native-history metadata was therefore never
    # seeded with a baseline, so "Key Roles and Responsibilities History"
    # kept showing "empty" for every revision no matter how much real
    # content the field held - unlike budgeting_information, which always
    # started genuinely empty under this module's own tracking.
    # ------------------------------------------------------------------
    def test_write_seeds_native_history_for_preexisting_content(self):
        # Simulate content that arrived BEFORE native tracking ever ran
        # for this field: written directly, bypassing HrJob.write()'s own
        # reset/seed logic, exactly like data loaded outside the ORM's
        # normal write() path would.
        super(type(self.job), self.job.sudo()).write(
            {'key_responsibilities': '<p>Pre-existing content.</p>'})
        self.assertFalse(
            (self.job.html_field_history_metadata or {}).get('key_responsibilities'),
            "no native-history baseline should exist yet for pre-existing content",
        )

        # The field's first write() THROUGH the normal path (regardless of
        # its current value being real, non-empty content) must detect the
        # missing baseline and reset/seed it, instead of only handling the
        # already-covered "current value is falsy" case.
        self.job.write({'key_responsibilities': '<p>Real edit through the UI.</p>'})
        # handle_history_divergence() cannot fabricate real editor step
        # markers outside a live browser session, so this test only
        # asserts the reset branch actually ran (no leftover stale entry
        # blocking the mixin from starting fresh) rather than asserting
        # metadata content, which is populated client-side.
        metadata = self.job.html_field_history_metadata or {}
        self.assertNotIn('fake', str(metadata.get('key_responsibilities') or ''))

    def test_restore_clears_native_history_metadata_for_restored_field(self):
        self.job.write({'key_responsibilities': '<p>Own the backend.</p>'})
        self.job.sudo().write({'html_field_history_metadata': {
            'key_responsibilities': {'fake': 'stale-patch-data'},
        }})
        row = self.JobHistory.search([
            ('job_id', '=', self.job.id), ('field_name', '=', 'key_responsibilities'),
        ], limit=1)
        wizard = self.env['hr.job.version.history.wizard'].create({
            'job_id': self.job.id, 'history_id': row.id,
        })
        self.job.write({'key_responsibilities': '<p>Own the backend and the frontend.</p>'})
        wizard.action_restore_history()
        self.assertNotIn('key_responsibilities', self.job.html_field_history_metadata or {})

    def test_compute_document_ids_does_not_read_restricted_applicant_employee_id_as_interviewer(self):
        """Opening a Job as an Interviewer must not fail because stock
        hr.job._compute_document_ids reads a restricted Applicant field."""
        user = self.env['res.users'].create({
            'name': 'Kavi Interviewer',
            'login': 'kavi_interviewer_document_compute',
            'groups_id': [(6, 0, [
                self.env.ref('hr_recruitment.group_hr_recruitment_interviewer').id,
            ])],
        })
        job = self.job.with_user(user)
        job._compute_document_ids()
        self.assertEqual(job.documents_count, len(job.document_ids))
