# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestWaitingRotActivity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create({
            "name": "Recruiter Test",
            "login": "recruiter_rot_test",
            "email": "recruiter_rot_test@example.com",
        })
        cls.stage = cls.env["hr.recruitment.stage"].create({
            "name": "Rot Stage",
            "rotting_threshold_days": 2,
        })
        cls.Applicant = cls.env["hr.applicant"]

    def _applicant(self, state="waiting", age_days=3, stage=None):
        applicant = self.Applicant.create({
            "partner_name": "Rot Applicant",
            "stage_id": (stage or self.stage).id,
            "user_id": self.user.id,
        })
        applicant.write({"kanban_state": state})
        applicant.date_last_stage_update = fields.Datetime.now() - timedelta(days=age_days)
        return applicant

    def _activities(self, applicant):
        return self.env["mail.activity"].search([
            ("res_model", "=", "hr.applicant"),
            ("res_id", "=", applicant.id),
            ("user_id", "=", self.user.id),
            ("summary", "=", "Applicant waiting too long"),
        ])

    def test_01_activity_created_once(self):
        applicant = self._applicant()
        self.Applicant._cron_create_waiting_rot_activity()
        self.assertEqual(len(self._activities(applicant)), 1)
        self.assertTrue(applicant.waiting_rot_activity_created)
        self.Applicant._cron_create_waiting_rot_activity()
        self.assertEqual(len(self._activities(applicant)), 1)

    def test_02_not_waiting_no_activity(self):
        applicant = self._applicant(state="normal")
        self.Applicant._cron_create_waiting_rot_activity()
        self.assertFalse(self._activities(applicant))

    def test_03_threshold_not_reached_no_activity(self):
        applicant = self._applicant(age_days=1)
        self.Applicant._cron_create_waiting_rot_activity()
        self.assertFalse(self._activities(applicant))

    def test_04_threshold_zero_disabled(self):
        stage = self.env["hr.recruitment.stage"].create({
            "name": "No Rot Stage",
            "rotting_threshold_days": 0,
        })
        applicant = self._applicant(stage=stage, age_days=30)
        self.Applicant._cron_create_waiting_rot_activity()
        self.assertFalse(self._activities(applicant))

    def test_05_flag_reset_when_status_changes(self):
        applicant = self._applicant()
        self.Applicant._cron_create_waiting_rot_activity()
        self.assertTrue(applicant.waiting_rot_activity_created)
        applicant.write({"kanban_state": "normal"})
        self.assertFalse(applicant.waiting_rot_activity_created)
