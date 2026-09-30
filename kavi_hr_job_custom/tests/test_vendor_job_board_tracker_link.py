# -*- coding: utf-8 -*-
from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tools import mute_logger

from .common import KaviHrJobCustomCommon


class TestJobBoard(KaviHrJobCustomCommon):

    def test_create_job_board(self):
        board = self.env['hr.job.board'].create({'name': 'LinkedIn Test'})
        self.assertTrue(board.active)

    def test_job_board_name_uniqueness(self):
        self.env['hr.job.board'].create({'name': 'Naukri Test'})
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self.env['hr.job.board'].create({'name': 'Naukri Test'})
            self.env.flush_all()


class TestVendor(KaviHrJobCustomCommon):

    def setUp(self):
        super().setUp()
        self.source = self.env['utm.source'].create({'name': 'Vendor Source Test'})

    def test_create_vendor(self):
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Foo Staffing',
            'email': 'foo@example.com',
            'source_id': self.source.id,
        })
        self.assertTrue(vendor.active)

    def test_job_ids_is_inverse_of_hr_job_vendor_id(self):
        # The Vendor's job_ids field is a true One2many inverse of
        # hr.job.vendor_id. Job Position data is managed from hr.job;
        # the Vendor form only displays the inverse relationship.
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Job Ids Staffing',
            'email': 'jobids@example.com',
            'source_id': self.source.id,
        })

        self.job.write({'vendor_id': vendor.id})
        self.assertIn(self.job, vendor.job_ids)
        self.assertEqual(self.job.vendor_id, vendor)

        self.job.write({'vendor_id': False})
        self.assertNotIn(self.job, vendor.job_ids)
        self.assertFalse(self.job.vendor_id)

    def test_recruiter_field_uses_odoo19_group_ids_relation(self):
        # Odoo 19 renamed the res.users group relation to group_ids.
        # This guards against reintroducing the invalid groups_id domain.
        self.assertIn('group_ids', self.env['res.users']._fields)
        self.assertNotIn('groups_id', self.env['res.users']._fields)

    def test_default_recruiter_is_allowed_recruitment_user(self):
        officer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Recruitment Officer Test',
            'login': 'recruitment_officer_test',
            'email': 'recruitment_officer_test@example.com',
            'group_ids': [(6, 0, [self.env.ref(
                'hr_recruitment.group_hr_recruitment_user').id])],
        })
        Vendor = self.env['hr.recruitment.vendor'].with_user(officer)
        default_user = Vendor._default_recruiter()
        self.assertEqual(default_user, officer)

    def test_default_recruiter_is_allowed_recruitment_manager(self):
        manager = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Recruitment Administrator Test',
            'login': 'recruitment_manager_test',
            'email': 'recruitment_manager_test@example.com',
            'group_ids': [(6, 0, [self.env.ref(
                'hr_recruitment.group_hr_recruitment_manager').id])],
        })
        Vendor = self.env['hr.recruitment.vendor'].with_user(manager)
        default_user = Vendor._default_recruiter()
        self.assertEqual(default_user, manager)

    def test_default_recruiter_is_empty_for_interviewer_only_user(self):
        interviewer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Interviewer Test',
            'login': 'interviewer_test',
            'email': 'interviewer_test@example.com',
            'group_ids': [(6, 0, [self.env.ref(
                'hr_recruitment.group_hr_recruitment_interviewer').id])],
        })
        Vendor = self.env['hr.recruitment.vendor'].with_user(interviewer)
        self.assertFalse(Vendor._default_recruiter())

    def test_recruiter_constraint_rejects_interviewer(self):
        interviewer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Interviewer Constraint Test',
            'login': 'interviewer_constraint_test',
            'email': 'interviewer_constraint_test@example.com',
            'group_ids': [(6, 0, [self.env.ref(
                'hr_recruitment.group_hr_recruitment_interviewer').id])],
        })
        with self.assertRaises(ValidationError):
            self.env['hr.recruitment.vendor'].create({
                'name': 'Invalid Recruiter Vendor',
                'email': 'invalid-recruiter@example.com',
                'source_id': self.source.id,
                'user_id': interviewer.id,
            })

    def test_recruiter_constraint_allows_recruitment_officer(self):
        officer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Officer Constraint Test',
            'login': 'officer_constraint_test',
            'email': 'officer_constraint_test@example.com',
            'group_ids': [(6, 0, [self.env.ref(
                'hr_recruitment.group_hr_recruitment_user').id])],
        })
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Valid Officer Vendor',
            'email': 'valid-officer@example.com',
            'source_id': self.source.id,
            'user_id': officer.id,
        })
        self.assertEqual(vendor.user_id, officer)

    def test_recruiter_constraint_allows_recruitment_manager(self):
        manager = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Manager Constraint Test',
            'login': 'manager_constraint_test',
            'email': 'manager_constraint_test@example.com',
            'group_ids': [(6, 0, [self.env.ref(
                'hr_recruitment.group_hr_recruitment_manager').id])],
        })
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Valid Manager Vendor',
            'email': 'valid-manager@example.com',
            'source_id': self.source.id,
            'user_id': manager.id,
        })
        self.assertEqual(vendor.user_id, manager)

    def test_vendor_invalid_email_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            self.env['hr.recruitment.vendor'].create({
                'name': 'Bad Email Staffing',
                'email': 'not-an-email',
                'source_id': self.source.id,
            })

    def test_vendor_name_uniqueness(self):
        self.env['hr.recruitment.vendor'].create({
            'name': 'Unique Staffing', 'email': 'a@example.com', 'source_id': self.source.id,
        })
        other_source = self.env['utm.source'].create({'name': 'Other Source Test'})
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self.env['hr.recruitment.vendor'].create({
                'name': 'Unique Staffing', 'email': 'b@example.com', 'source_id': other_source.id,
            })
            self.env.flush_all()

    def test_vendor_source_uniqueness(self):
        self.env['hr.recruitment.vendor'].create({
            'name': 'First Staffing', 'email': 'a@example.com', 'source_id': self.source.id,
        })
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self.env['hr.recruitment.vendor'].create({
                'name': 'Second Staffing', 'email': 'b@example.com', 'source_id': self.source.id,
            })
            self.env.flush_all()

    def test_source_onchange_warns_and_clears_duplicate_source(self):
        first = self.env['hr.recruitment.vendor'].create({
            'name': 'First Source Vendor',
            'email': 'first-source@example.com',
            'source_id': self.source.id,
        })
        second = self.env['hr.recruitment.vendor'].new({
            'name': 'Second Source Vendor',
            'email': 'second-source@example.com',
        })
        second.source_id = self.source
        result = second._onchange_source_id()
        self.assertFalse(second.source_id)
        self.assertEqual(result['warning']['title'], 'Source Already Assigned')
        self.assertIn(first.name, result['warning']['message'])
        self.assertIn(self.source.name, result['warning']['message'])

    # ------------------------------------------------------------------
    # Contacts (res.partner) sync
    # ------------------------------------------------------------------
    def test_active_vendor_grants_portal_access_to_contact_person(self):
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Active Portal Vendor',
            'email': 'active-portal@example.com',
            'contact_person': 'Active Portal Contact',
            'source_id': self.source.id,
            'active': True,
        })

        self.assertTrue(vendor.partner_id.is_vendor)
        self.assertTrue(vendor.partner_id.active)
        self.assertTrue(vendor.contact_person_id.is_vendor)
        self.assertTrue(vendor.contact_person_id.active)
        self.assertEqual(vendor.contact_person_id.email, vendor.email)

        portal_group = self.env.ref('base.group_portal')
        portal_user = vendor.contact_person_id.user_ids[:1]
        self.assertTrue(portal_user)
        self.assertTrue(portal_user.active)
        self.assertIn(portal_group, portal_user.group_ids)
        self.assertEqual(portal_user.login, vendor.email)

        company_messages = vendor.partner_id.message_ids.filtered(
            lambda message: message.body == '<p>Portal access granted</p>'
        )
        contact_messages = vendor.contact_person_id.message_ids.filtered(
            lambda message: message.body == '<p>Portal access granted</p>'
        )
        self.assertTrue(company_messages, 'Portal access granted must be posted on the Company chatter.')
        self.assertTrue(contact_messages, 'Portal access granted must be posted on the Contact Person chatter.')

    def test_portal_access_granted_message_is_posted_on_company_and_contact(self):
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Chatter Portal Vendor',
            'email': 'chatter-portal@example.com',
            'contact_person': 'Chatter Portal Contact',
            'source_id': self.source.id,
            'active': True,
        })

        for partner in (vendor.partner_id, vendor.contact_person_id):
            messages = partner.message_ids.filtered(
                lambda message: message.body == '<p>Portal access granted</p>'
            )
            self.assertEqual(
                len(messages),
                1,
                'Exactly one portal-access-granted message should be created per partner.',
            )

    def test_inactive_vendor_does_not_grant_portal_access(self):
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Inactive Portal Vendor',
            'email': 'inactive-portal@example.com',
            'contact_person': 'Inactive Portal Contact',
            'source_id': self.source.id,
            'active': False,
        })

        self.assertFalse(vendor.partner_id.is_vendor)
        self.assertFalse(vendor.partner_id.active)
        self.assertFalse(vendor.contact_person_id.is_vendor)
        self.assertFalse(vendor.contact_person_id.active)
        self.assertFalse(vendor.contact_person_id.user_ids)

    def test_deactivating_vendor_revokes_portal_access_and_vendor_flag(self):
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Revoke Portal Vendor',
            'email': 'revoke-portal@example.com',
            'contact_person': 'Revoke Portal Contact',
            'source_id': self.source.id,
            'active': True,
        })
        portal_group = self.env.ref('base.group_portal')
        portal_user = vendor.contact_person_id.user_ids[:1]
        self.assertIn(portal_group, portal_user.group_ids)

        vendor.write({'active': False})

        self.assertFalse(vendor.partner_id.is_vendor)
        self.assertFalse(vendor.partner_id.active)
        self.assertFalse(vendor.contact_person_id.is_vendor)
        self.assertFalse(vendor.contact_person_id.active)
        self.assertNotIn(portal_group, portal_user.group_ids)

    def test_reactivating_vendor_restores_portal_access_and_vendor_flag(self):
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Restore Portal Vendor',
            'email': 'restore-portal@example.com',
            'contact_person': 'Restore Portal Contact',
            'source_id': self.source.id,
            'active': True,
        })
        portal_group = self.env.ref('base.group_portal')
        portal_user = vendor.contact_person_id.user_ids[:1]

        vendor.write({'active': False})
        self.assertNotIn(portal_group, portal_user.group_ids)

        vendor.write({'active': True})

        self.assertTrue(vendor.partner_id.is_vendor)
        self.assertTrue(vendor.partner_id.active)
        self.assertTrue(vendor.contact_person_id.is_vendor)
        self.assertTrue(vendor.contact_person_id.active)
        self.assertTrue(portal_user.active)
        self.assertIn(portal_group, portal_user.group_ids)

    def test_inactive_vendor_edit_does_not_restore_vendor_access(self):
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Inactive Edit Vendor',
            'email': 'inactive-edit@example.com',
            'contact_person': 'Inactive Edit Contact',
            'source_id': self.source.id,
            'active': False,
        })

        vendor.write({'name': 'Inactive Edit Vendor Renamed', 'email': 'inactive-edit-2@example.com'})

        self.assertFalse(vendor.partner_id.is_vendor)
        self.assertFalse(vendor.partner_id.active)
        self.assertFalse(vendor.contact_person_id.is_vendor)
        self.assertFalse(vendor.contact_person_id.active)
        self.assertFalse(vendor.contact_person_id.user_ids)

    def test_create_auto_creates_company_partner(self):
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Sync Staffing', 'email': 'sync@example.com', 'phone': '111',
            'source_id': self.source.id,
        })
        self.assertTrue(vendor.partner_id)
        self.assertEqual(vendor.partner_id.name, 'Sync Staffing')
        self.assertEqual(vendor.partner_id.email, 'sync@example.com')
        self.assertEqual(vendor.partner_id.phone, '111')
        self.assertEqual(vendor.partner_id.company_type, 'company')
        self.assertTrue(vendor.partner_id.is_vendor)

    def test_vendor_write_syncs_down_to_existing_partner(self):
        partner = self.env['res.partner'].create({'name': 'Old Name', 'company_type': 'company'})
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Rename Staffing', 'email': 'rename@example.com',
            'source_id': self.source.id, 'partner_id': partner.id,
        })
        # Vendor's own values win and are pushed onto the linked partner.
        self.assertEqual(partner.name, 'Rename Staffing')
        self.assertEqual(partner.email, 'rename@example.com')
        self.assertTrue(partner.is_vendor)

        vendor.write({'name': 'Renamed Again Staffing'})
        self.assertEqual(partner.name, 'Renamed Again Staffing')

    def test_partner_write_syncs_back_to_vendor(self):
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Reverse Sync Staffing', 'email': 'reverse@example.com',
            'source_id': self.source.id,
        })
        partner = vendor.partner_id
        partner.write({'name': 'Edited From Contacts', 'phone': '999'})
        self.assertEqual(vendor.name, 'Edited From Contacts')
        self.assertEqual(vendor.phone, '999')

    def test_address_fields_sync_to_partner(self):
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Address Staffing', 'email': 'address@example.com',
            'source_id': self.source.id,
        })
        country = self.env.ref('base.in')
        vendor.write({'street': '221B Baker Street', 'city': 'Chennai', 'country_id': country.id})
        self.assertEqual(vendor.partner_id.street, '221B Baker Street')
        self.assertEqual(vendor.partner_id.city, 'Chennai')
        self.assertEqual(vendor.partner_id.country_id, country)

        # And the other direction: editing the partner's address updates
        # the Vendor's related fields too (Odoo's own related-field
        # recompute, no custom code involved).
        vendor.partner_id.write({'city': 'Bengaluru'})
        self.assertEqual(vendor.city, 'Bengaluru')

    def test_contact_person_auto_creates_child_partner(self):
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Contact Staffing', 'email': 'contact@example.com',
            'source_id': self.source.id, 'contact_person': 'Jane Contact',
        })
        self.assertTrue(vendor.contact_person_id)
        self.assertEqual(vendor.contact_person_id.name, 'Jane Contact')
        self.assertEqual(vendor.contact_person_id.parent_id, vendor.partner_id)
        self.assertEqual(vendor.contact_person_id.company_name, vendor.partner_id.name)

    def test_contact_person_write_syncs_down_to_existing_partner(self):
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Rename Contact Staffing', 'email': 'renamecontact@example.com',
            'source_id': self.source.id, 'contact_person': 'Original Name',
        })
        contact = vendor.contact_person_id
        vendor.write({'contact_person': 'Updated Name'})
        self.assertEqual(contact.name, 'Updated Name')

    def test_contact_partner_write_syncs_back_to_vendor(self):
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Reverse Contact Staffing', 'email': 'reversecontact@example.com',
            'source_id': self.source.id, 'contact_person': 'Jane Contact',
        })
        contact = vendor.contact_person_id
        contact.write({'name': 'Jane Renamed'})
        self.assertEqual(vendor.contact_person, 'Jane Renamed')

    def test_company_name_change_refreshes_contact_person_company_name(self):
        vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Company Rename Staffing', 'email': 'companyrename@example.com',
            'source_id': self.source.id, 'contact_person': 'Jane Contact',
        })
        vendor.partner_id.write({'name': 'Renamed Company'})
        self.assertEqual(vendor.contact_person_id.company_name, 'Renamed Company')


class TestTrackerLink(KaviHrJobCustomCommon):

    def setUp(self):
        super().setUp()
        self.source = self.env['utm.source'].create({'name': 'Tracker Source Test'})
        self.vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Tracker Staffing', 'email': 'tracker@example.com', 'source_id': self.source.id,
        })

    def test_tracker_link_uniqueness_per_job_vendor_link_type(self):
        self.env['hr.job.vendor.tracker.link'].create({
            'job_id': self.job.id, 'vendor_id': self.vendor.id,
            'link_type': 'job_page', 'url': 'https://example.com/1',
        })
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self.env['hr.job.vendor.tracker.link'].create({
                'job_id': self.job.id, 'vendor_id': self.vendor.id,
                'link_type': 'job_page', 'url': 'https://example.com/2',
            })
            self.env.flush_all()

    def test_tracker_link_allows_both_link_types_for_same_job_vendor(self):
        Link = self.env['hr.job.vendor.tracker.link']
        Link.create({
            'job_id': self.job.id, 'vendor_id': self.vendor.id,
            'link_type': 'job_page', 'url': 'https://example.com/job-page',
        })
        Link.create({
            'job_id': self.job.id, 'vendor_id': self.vendor.id,
            'link_type': 'email', 'url': 'https://example.com/email',
        })
        links = Link.search([('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id)])
        self.assertEqual(len(links), 2)
        self.assertEqual(set(links.mapped('link_type')), {'job_page', 'email'})

    def test_create_vendor_tracker_links_noop_on_empty_recordset(self):
        # Must not raise when called with nothing to process.
        self.job._create_vendor_tracker_links(self.env['hr.recruitment.vendor'])
        links = self.env['hr.job.vendor.tracker.link'].search([('job_id', '=', self.job.id)])
        self.assertFalse(links)

    def test_create_vendor_tracker_links_creates_single_row_with_email_url(self):
        # Only ONE row is auto-created per Vendor (link_type='job_page');
        # the Email Link lives on `email_url` on that same row, not as a
        # second 'email'-type row.
        self.job._create_vendor_tracker_links(self.vendor)
        links = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id),
        ])
        self.assertEqual(len(links), 1)
        self.assertEqual(links.link_type, 'job_page')
        self.assertIn('utm_medium=Website', links.url)

        if self.job._kavi_has_job_email_alias():
            # Email Link is the canonical mailto link built from the
            # Job Position Email Alias + Vendor Source.
            expected_email = self.job._kavi_build_email_link(self.vendor.source_id)
            self.assertEqual(links.email_url, expected_email)
            self.assertTrue(links.email_url.startswith('mailto:'))
            self.assertTrue(links.email_sent)
        else:
            self.assertFalse(links.email_url)
            self.assertFalse(links.email_sent)

    def test_email_url_empty_without_job_email_alias(self):
        # If the Job Position has no Email Alias, `email_url` must stay
        # empty on the auto-generated row - no vendor email is sent.
        self.job.write({'alias_name': False})
        self.job._create_vendor_tracker_links(self.vendor)
        link = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id),
        ])
        self.assertEqual(len(link), 1)
        self.assertFalse(link.email_url)
        self.assertFalse(link.email_sent)

    def test_email_url_matches_email_tracker_builder(self):
        self.job.write({'alias_name': 'sales-manager'})
        self.job._create_vendor_tracker_links(self.vendor)
        link = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id),
        ])
        self.assertEqual(link.email_url, self.job._kavi_build_email_link(self.vendor.source_id))
        self.assertTrue(link.email_url.startswith('mailto:'))

    def test_email_url_backfills_and_sends_once_alias_is_set(self):
        self.job.write({'alias_name': False})
        self.job._create_vendor_tracker_links(self.vendor)
        link = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id),
        ])
        self.assertFalse(link.email_url)
        self.assertFalse(link.email_sent)

        self.job.write({'alias_name': 'newly-configured-alias'})
        self.assertEqual(link.email_url, self.job._kavi_build_email_link(self.vendor.source_id))
        self.assertTrue(link.email_url.startswith('mailto:'))
        self.assertTrue(link.email_sent)

    def test_trackers_email_url_uses_exact_vendor_email_url(self):
        """The Trackers Email link must be exactly the Vendor Email link."""
        self.job.write({'name': 'Digital Marketing', 'alias_name': 'jobs'})
        self.job._create_vendor_tracker_links(self.vendor)

        vendor_link = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id),
            ('vendor_id', '=', self.vendor.id),
        ], limit=1)
        tracker = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id),
            ('source_id', '=', self.source.id),
        ], limit=1)

        self.assertTrue(vendor_link)
        self.assertTrue(tracker)
        self.assertEqual(tracker.kavi_email_url, vendor_link.email_url)
        self.assertEqual(
            tracker.kavi_email_url,
            self.job._kavi_build_email_link(self.vendor.source_id),
        )
        self.assertTrue(tracker.kavi_email_url.startswith('mailto:'))

    def test_vendor_and_standard_tracker_email_are_identical(self):
        """The Vendors and Trackers tabs must use one shared Email value
        and one shared Email Tracking URL.
        """
        self.job.write({'name': 'powerBi Developer', 'alias_name': 'vishya'})
        self.job._create_vendor_tracker_links(self.vendor)

        vendor_link = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id),
            ('vendor_id', '=', self.vendor.id),
        ], limit=1)

        tracker = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id),
            ('source_id', '=', self.source.id),
        ], limit=1)

        self.assertTrue(vendor_link)
        self.assertTrue(tracker)

        expected_email = 'vishya+vendor-source-test@%s' % (
            self.job._kavi_get_alias_domain(),
        )

        self.assertEqual(vendor_link.email_address, expected_email)
        self.assertEqual(tracker.kavi_email_address, expected_email)

        expected_url = 'mailto:%s' % expected_email
        self.assertEqual(vendor_link.email_url, expected_url)
        self.assertEqual(tracker.kavi_email_url, expected_url)

    def test_shared_email_requires_alias_and_source(self):
        self.job.write({'alias_name': False})
        self.assertFalse(self.job._kavi_build_job_email_address(self.source))

        self.job.write({'alias_name': 'vishya'})
        self.assertFalse(self.job._kavi_build_job_email_address(self.source))

        self.assertEqual(
            self.job._kavi_build_job_email_address(self.source),
            'vishya+vendor-source-test@%s' % self.job._kavi_get_alias_domain(),
        )

    def test_tracker_link_matches_standard_trackers_tab_url(self):
        self.job.write({'alias_name': 'sales-manager'})
        self.job._create_vendor_tracker_links(self.vendor)

        custom_link = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id),
            ('link_type', '=', 'job_page'),
        ], limit=1)
        standard_source = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ], limit=1)

        self.assertTrue(standard_source)
        self.assertEqual(custom_link.url, standard_source.url)
        self.assertIn('utm_campaign=', custom_link.url)
        self.assertIn('utm_medium=Website', custom_link.url)
        self.assertIn('utm_source=', custom_link.url)

    def test_email_link_is_displayed_as_url_and_not_email_address(self):
        self.job.write({'alias_name': 'sales-manager'})
        self.job._create_vendor_tracker_links(self.vendor)
        link = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id),
        ], limit=1)
        self.assertTrue(link.email_url.startswith('mailto:'))
        self.assertIn('sales-manager+vendor-source-test', link.email_url)
        self.assertIn('@example.com', link.email_url)

    def test_email_address_uses_alias_plus_source(self):
        self.job.write({'name': 'Digital Marketing', 'alias_name': 'jobs'})
        expected = 'jobs+vendor-source-test@%s' % self.job._kavi_get_alias_domain()

        self.assertEqual(self.job._kavi_build_job_email_address(self.source), expected)
        self.assertEqual(self.job._kavi_build_email_link(self.source), 'mailto:%s' % expected)

        self.job._create_vendor_tracker_links(self.vendor)
        vendor_link = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id),
        ], limit=1)
        tracker = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ], limit=1)

        self.assertEqual(vendor_link.email_address, expected)
        self.assertEqual(tracker.kavi_email_address, expected)
        self.assertEqual(vendor_link.email_url, tracker.kavi_email_url)
        self.assertEqual(vendor_link.email_url, 'mailto:%s' % expected)

    def test_second_row_only_created_manually_not_automatically(self):
        # Calling the automatic path a second time (e.g. via write()
        # re-adding the same vendor) must NOT create a second Link Type
        # row - only "Add a line" (a manual create()) can do that.
        self.job._create_vendor_tracker_links(self.vendor)
        self.job._create_vendor_tracker_links(self.vendor)
        links = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id),
        ])
        self.assertEqual(len(links), 1)

        # A manually-added row (explicit create(), as "Add a line" does)
        # is still allowed to add a second Link Type for the same Vendor.
        self.env['hr.job.vendor.tracker.link'].create({
            'job_id': self.job.id, 'vendor_id': self.vendor.id,
            'link_type': 'email', 'url': 'https://example.com/manual-email',
        })
        links = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id),
        ])
        self.assertEqual(len(links), 2)

    def test_create_rebuilds_url_ignoring_stale_newid_placeholder(self):
        # Regression: a row added via "Add a line" on the Vendors tab of
        # a still-unsaved Job Position gets its `url` computed by the
        # onchange while job_id is a virtual NewId - baking a bogus
        # "/jobs/detail/NewId_7"-style path into the stored value. By
        # the time create() runs, job_id in vals is already the real,
        # persisted id, so create() must rebuild `url` from that rather
        # than trust the stale value carried over from the onchange.
        link = self.env['hr.job.vendor.tracker.link'].create({
            'job_id': self.job.id, 'vendor_id': self.vendor.id,
            'link_type': 'job_page',
            'url': 'http://localhost:8069/jobs/detail/NewId_7?utm_source=stale',
        })
        self.assertNotIn('NewId', link.url)
        self.assertEqual(link.url, self.job._build_tracker_url(self.vendor, 'job_page'))

    def test_email_link_recomputes_when_job_name_changes(self):
        self.job.write({'alias_name': 'jobs'})
        self.job._create_vendor_tracker_links(self.vendor)
        link = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id),
        ], limit=1)
        old_url = link.email_url

        self.job.write({'name': 'Changed Position'})
        self.assertNotEqual(link.email_url, old_url)
        self.assertEqual(link.email_url, self.job._kavi_build_email_link(self.vendor.source_id))

    def test_create_vendor_tracker_links_idempotent(self):
        self.job._create_vendor_tracker_links(self.vendor)
        self.job._create_vendor_tracker_links(self.vendor)
        links = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id),
        ])
        self.assertEqual(len(links), 1)

    # ------------------------------------------------------------------
    # Mirroring onto the standard "Trackers" tab (hr.recruitment.source)
    # ------------------------------------------------------------------
    def test_vendor_tracker_link_creates_matching_trackers_tab_row(self):
        # Adding a Vendor to a Job Position (the automatic path) must
        # create a matching hr.recruitment.source row for the same
        # Job/Source pair, so the Vendor shows up on the standard
        # Trackers tab with no manual data entry - see
        # hr.job.vendor.tracker.link._sync_recruitment_source_tracker().
        self.job._create_vendor_tracker_links(self.vendor)
        source_row = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ])
        self.assertEqual(len(source_row), 1)
        # The standard Trackers-tab URL is computed by Odoo itself.
        # The custom Vendor Tracker Link must match it exactly.
        if self.job._kavi_has_job_email_alias():
            self.assertTrue(source_row.email)

    def test_trackers_tab_row_not_duplicated_for_same_job_source(self):
        # A Vendor added twice (e.g. re-added or edited) must not create
        # a second hr.recruitment.source row for the same Job/Source.
        self.job._create_vendor_tracker_links(self.vendor)
        self.job._create_vendor_tracker_links(self.vendor)
        source_rows = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ])
        self.assertEqual(len(source_rows), 1)

    def test_setting_alias_later_backfills_trackers_tab_row(self):
        # Vendor added while the Job Position has NO Email Alias yet -
        # the Trackers-tab row is still created (it never waits on the
        # alias - see _sync_recruitment_source_tracker()), just with an
        # empty Email until the alias exists.
        self.job.write({'alias_name': False})
        self.job._create_vendor_tracker_links(self.vendor)
        source_row = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ])
        self.assertEqual(len(source_row), 1)

        # Simulate the row having been removed some other way (e.g. an
        # older module version, or a user deleting it by hand) - setting
        # the Email Alias now must self-heal it rather than require the
        # Vendor to be re-added.
        source_row.unlink()
        self.assertFalse(self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ]))

        self.job.write({'alias_name': 'consultant-alias'})
        healed_row = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ])
        self.assertEqual(len(healed_row), 1)

    def test_manually_added_vendors_tab_row_also_syncs_trackers_tab(self):
        # A row added directly via "Add a line" on the Vendors tab
        # (a plain create() on hr.job.vendor.tracker.link, not through
        # hr.job._create_vendor_tracker_links()) must sync the Trackers
        # tab too - both creation paths funnel through the same
        # create() override.
        other_source = self.env['utm.source'].create({'name': 'Manual Source Test'})
        other_vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Manual Add Staffing', 'email': 'manual@example.com',
            'source_id': other_source.id,
        })
        self.env['hr.job.vendor.tracker.link'].create({
            'job_id': self.job.id, 'vendor_id': other_vendor.id,
            'link_type': 'job_page', 'url': 'https://example.com/manual',
        })
        source_row = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', other_source.id),
        ])
        self.assertEqual(len(source_row), 1)

    # ------------------------------------------------------------------
    # BUG FIX: the Trackers tab "Email" column (RecruitmentCopyClipboardChar
    # widget, invisible="not has_domain") must only appear/generate an
    # address once THIS Job Position has its own Email Alias set - not
    # merely because the company has some alias domain configured
    # anywhere. See models/hr_recruitment_source.py for the full
    # explanation of core Odoo's has_domain/create_alias() behaviour.
    # ------------------------------------------------------------------
    def test_email_column_hidden_when_job_has_no_alias(self):
        self.job.write({'alias_name': False})
        self.job._create_vendor_tracker_links(self.vendor)
        source_row = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ])
        self.assertFalse(source_row.has_domain)

    def test_email_column_shown_once_job_alias_is_set(self):
        self.job.write({'alias_name': False})
        self.job._create_vendor_tracker_links(self.vendor)
        source_row = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ])
        self.assertFalse(source_row.has_domain)

        self.job.write({'alias_name': 'trackertest-alias'})
        self.assertTrue(source_row.has_domain)

    def test_create_alias_blocked_when_job_has_no_alias(self):
        self.job.write({'alias_name': False})
        self.job._create_vendor_tracker_links(self.vendor)
        source_row = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ])
        with self.assertRaises(UserError):
            source_row.create_alias()

    # ------------------------------------------------------------------
    # BUG FIX: deleting a vendor's row from the Vendors tab (unlink() on
    # hr.job.vendor.tracker.link) previously left that vendor sitting in
    # hr.job.vendor_id forever - the field the Vendor Portal actually
    # filters on - so the Job Position kept appearing on their portal
    # even after being "removed" in the backend.
    # ------------------------------------------------------------------
    def test_unlink_clears_job_vendor_when_last_link_gone(self):
        self.job._create_vendor_tracker_links(self.vendor)
        self.assertEqual(self.job.vendor_id, self.vendor)

        link = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id),
        ])
        link.unlink()
        self.assertFalse(self.job.vendor_id)

    def test_unlink_keeps_job_vendor_if_another_link_remains(self):
        # Vendor has two rows (job_page + email link_type). Deleting only
        # one of them must NOT drop the vendor from job vendor yet.
        Link = self.env['hr.job.vendor.tracker.link']
        self.job._create_vendor_tracker_links(self.vendor)
        Link.create({
            'job_id': self.job.id, 'vendor_id': self.vendor.id,
            'link_type': 'email', 'url': 'https://example.com/manual-email',
        })
        links = Link.search([('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id)])
        self.assertEqual(len(links), 2)

        links.filtered(lambda l: l.link_type == 'email').unlink()
        self.assertEqual(self.job.vendor_id, self.vendor)

        links.filtered(lambda l: l.link_type == 'job_page').unlink()
        self.assertFalse(self.job.vendor_id)

    def test_multiple_vendors_are_allowed_on_same_job(self):
        """Regression test for the Vendors-tab Validation Error.

        A Job Position may have more than one Vendor. The legacy
        ``job.vendor_id`` remains the primary Vendor, while all Vendors are
        represented by tracker_link_ids.
        """
        other_vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Other Staffing Test', 'email': 'other@example.com',
            'source_id': self.env['utm.source'].create({
                'name': 'Other Source Test',
            }).id,
        })

        self.job._create_vendor_tracker_links(self.vendor)
        self.job._create_vendor_tracker_links(other_vendor)

        links = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id),
        ])
        self.assertEqual(
            set(links.mapped('vendor_id').ids),
            {self.vendor.id, other_vendor.id},
        )
        self.assertEqual(self.job.vendor_id, self.vendor)

    def test_removing_primary_vendor_promotes_remaining_vendor(self):
        """Removing the primary Vendor must not remove the remaining
        Vendor assignment from the Job Position.
        """
        other_vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Remaining Staffing Test', 'email': 'remaining@example.com',
            'source_id': self.env['utm.source'].create({
                'name': 'Remaining Source Test',
            }).id,
        })
        self.job._create_vendor_tracker_links(self.vendor)
        self.job._create_vendor_tracker_links(other_vendor)

        primary_link = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id),
            ('vendor_id', '=', self.vendor.id),
        ], limit=1)
        primary_link.unlink()

        self.assertEqual(self.job.vendor_id, other_vendor)
        self.assertTrue(self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id),
            ('vendor_id', '=', other_vendor.id),
        ], limit=1))


    def test_unlink_removes_orphaned_recruitment_source_row(self):
        self.job._create_vendor_tracker_links(self.vendor)
        source_row = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ])
        self.assertTrue(source_row)

        link = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id),
        ])
        link.unlink()

        source_row = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ])
        self.assertFalse(source_row)

    def test_unlink_keeps_recruitment_source_row_if_another_link_shares_it(self):
        # Two rows for the same vendor (job_page + email link_type) share
        # the same Source. Deleting only one must NOT remove the
        # Trackers row yet.
        Link = self.env['hr.job.vendor.tracker.link']
        self.job._create_vendor_tracker_links(self.vendor)
        Link.create({
            'job_id': self.job.id, 'vendor_id': self.vendor.id,
            'link_type': 'email', 'url': 'https://example.com/manual-email',
        })
        links = Link.search([('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id)])
        self.assertEqual(len(links), 2)

        links.filtered(lambda l: l.link_type == 'email').unlink()
        source_row = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ])
        self.assertTrue(source_row)

        links.filtered(lambda l: l.link_type == 'job_page').unlink()
        source_row = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ])
        self.assertFalse(source_row)

    def test_write_vendor_change_moves_recruitment_source_row(self):
        other_source = self.env['utm.source'].create({'name': 'Other Source Test 2'})
        other_vendor = self.env['hr.recruitment.vendor'].create({
            'name': 'Other Staffing Test 2', 'email': 'other2@example.com',
            'source_id': other_source.id,
        })
        self.job._create_vendor_tracker_links(self.vendor)
        link = self.env['hr.job.vendor.tracker.link'].search([
            ('job_id', '=', self.job.id), ('vendor_id', '=', self.vendor.id),
        ])

        link.write({'vendor_id': other_vendor.id})

        old_source_row = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', self.source.id),
        ])
        new_source_row = self.env['hr.recruitment.source'].search([
            ('job_id', '=', self.job.id), ('source_id', '=', other_source.id),
        ])
        self.assertFalse(old_source_row)
        self.assertTrue(new_source_row)
