# -*- coding: utf-8 -*-
from .common import DuplicateDetectionCommon


class TestNotifyRecruiterDuplicate(DuplicateDetectionCommon):

    def setUp(self):
        super().setUp()
        self.original = self._create_applicant(
            self.job_a, email='original@example.com', phone='9876543210'
        )

    def test_posts_chatter_note_on_a_candidate(self):
        candidate = self._create_applicant(
            self.job_a, email='new@example.com', phone='1111111111'
        )
        messages_before = len(candidate.message_ids)
        candidate._notify_recruiter_duplicate(self.original)
        self.assertGreater(len(candidate.message_ids), messages_before)
        self.assertTrue(any(
            'Duplicate Application Detected' in (m.body or '')
            for m in candidate.message_ids
        ))
        self.assertEqual(len(self.original.message_ids), 0)

    def test_schedules_activity_for_applicant_user_id_when_set(self):
        recruiter = self.env['res.users'].search([], limit=1)
        candidate = self._create_applicant(
            self.job_a,
            email='new@example.com',
            phone='1111111111',
            user_id=recruiter.id,
        )
        candidate._notify_recruiter_duplicate(self.original)
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'hr.applicant'),
            ('res_id', '=', candidate.id),
        ])
        self.assertTrue(activities)
        self.assertEqual(activities.user_id, recruiter)

    def test_falls_back_to_job_user_id_when_applicant_has_none(self):
        recruiter = self.env['res.users'].search([], limit=1)
        self.job_a.write({'user_id': recruiter.id})
        candidate = self._create_applicant(
            self.job_a, email='new@example.com', phone='1111111111'
        )
        self.assertFalse(candidate.user_id)
        candidate._notify_recruiter_duplicate(self.original)
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'hr.applicant'),
            ('res_id', '=', candidate.id),
        ])
        self.assertTrue(activities)
        self.assertEqual(activities.user_id, recruiter)

    def test_no_activity_scheduled_when_no_recruiter_available(self):
        self.job_a.write({'user_id': False})
        candidate = self._create_applicant(
            self.job_a, email='new@example.com', phone='1111111111'
        )
        self.assertFalse(candidate.user_id)
        self.assertFalse(self.job_a.user_id)
        candidate._notify_recruiter_duplicate(self.original)
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'hr.applicant'),
            ('res_id', '=', candidate.id),
        ])
        self.assertFalse(activities)
        self.assertTrue(candidate.message_ids)


class TestDuplicateCountAndAction(DuplicateDetectionCommon):

    def setUp(self):
        super().setUp()
        self.original = self._create_applicant(
            self.job_a, email='original@example.com', phone='9876543210'
        )

    def test_new_applications_do_not_create_duplicate_links(self):
        candidate = self._create_applicant(
            self.job_a, email='new@example.com', phone='1111111111'
        )
        self.assertEqual(self.original.duplicate_application_count, 0)
        self.assertFalse(candidate.duplicate_of_id)

    def test_action_view_duplicate_applications_empty_for_normal_record(self):
        fresh = self._create_applicant(
            self.job_a, email='no-dupes@example.com', phone='2222222222'
        )
        action = fresh.action_view_duplicate_applications()
        self.assertEqual(action['res_model'], 'hr.applicant')
        self.assertEqual(action['domain'], [('id', 'in', [])])
