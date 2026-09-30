# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestApplicantKanbanState(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stage = cls.env["hr.recruitment.stage"].create({
            "name": "Initial Stage",
            "sequence": 1,
            "legend_normal": "In Progress",
            "legend_done": "Ready for Next Stage",
            "legend_blocked": "Blocked",
            "legend_waiting": "Waiting",
            "legend_hold_2": "New Status",
        })

    def test_01_selection_contains_new_status(self):
        selection = dict(self.env["hr.applicant"]._fields["kanban_state"].selection)
        self.assertIn("hold_2", selection)
        self.assertEqual(selection["hold_2"], "New Status")

    def test_02_create_applicant_with_new_status(self):
        applicant = self.env["hr.applicant"].create({
            "name": "Test Applicant",
            "stage_id": self.stage.id,
            "kanban_state": "hold_2",
        })
        self.assertEqual(applicant.kanban_state, "hold_2")

    def test_03_update_kanban_state(self):
        applicant = self.env["hr.applicant"].create({
            "name": "Test Applicant",
            "stage_id": self.stage.id,
        })
        applicant.write({"kanban_state": "hold_2"})
        self.assertEqual(applicant.kanban_state, "hold_2")

    def test_04_related_tooltip_labels_follow_stage(self):
        applicant = self.env["hr.applicant"].create({
            "name": "Test Applicant",
            "stage_id": self.stage.id,
            "kanban_state": "normal",
        })

        self.assertEqual(applicant.legend_normal, "In Progress")
        self.assertEqual(applicant.legend_blocked, "Blocked")
        self.assertEqual(applicant.legend_waiting, "Waiting")
        self.assertEqual(applicant.legend_done, "Ready for Next Stage")
        self.assertEqual(applicant.legend_hold_2, "New Status")

        self.stage.write({
            "legend_normal": "Screening",
            "legend_blocked": "Interview Blocked",
            "legend_waiting": "Candidate Waiting",
            "legend_done": "Interview Completed",
            "legend_hold_2": "Technical Review",
        })

        # Related fields immediately follow the stage tooltip values.
        self.assertEqual(applicant.legend_normal, "Screening")
        self.assertEqual(applicant.legend_blocked, "Interview Blocked")
        self.assertEqual(applicant.legend_waiting, "Candidate Waiting")
        self.assertEqual(applicant.legend_done, "Interview Completed")
        self.assertEqual(applicant.legend_hold_2, "Technical Review")

    def test_05_stage_change_resets_kanban_state_to_normal(self):
        other_stage = self.env["hr.recruitment.stage"].create({
            "name": "Next Stage",
            "sequence": 2,
            "legend_normal": "Next Stage - In Progress",
            "legend_blocked": "Next Stage - Blocked",
            "legend_waiting": "Next Stage - Waiting",
            "legend_done": "Next Stage - Ready",
            "legend_hold_2": "Next Stage - Technical Review",
        })
        applicant = self.env["hr.applicant"].create({
            "name": "Test Applicant",
            "stage_id": self.stage.id,
            "kanban_state": "hold_2",
        })

        applicant.write({"stage_id": other_stage.id})

        self.assertEqual(applicant.kanban_state, "normal")
        self.assertEqual(
            applicant.legend_normal,
            "Next Stage - In Progress",
        )

    def test_06_stage_change_with_explicit_status_still_uses_new_stage_normal(self):
        other_stage = self.env["hr.recruitment.stage"].create({
            "name": "Next Stage 2",
            "sequence": 3,
            "legend_normal": "New Stage Progress",
            "legend_blocked": "New Stage Blocked",
        })
        applicant = self.env["hr.applicant"].create({
            "name": "Test Applicant",
            "stage_id": self.stage.id,
            "kanban_state": "hold_2",
        })

        applicant.write({
            "stage_id": other_stage.id,
            "kanban_state": "blocked",
        })

        self.assertEqual(applicant.kanban_state, "normal")
        self.assertEqual(applicant.legend_normal, "New Stage Progress")

    def test_07_onchange_stage_id_resets_kanban_state(self):
        other_stage = self.env["hr.recruitment.stage"].create({
            "name": "Next Stage 3",
            "sequence": 4,
        })
        applicant = self.env["hr.applicant"].new({
            "name": "Test Applicant",
            "stage_id": self.stage.id,
            "kanban_state": "hold_2",
        })

        applicant.stage_id = other_stage.id
        applicant._onchange_stage_id_sync_kanban_state()

        self.assertEqual(applicant.kanban_state, "normal")
