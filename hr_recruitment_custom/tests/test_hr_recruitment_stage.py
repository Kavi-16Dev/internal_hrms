# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestHrRecruitmentStage(TransactionCase):

    def test_01_field_exists_and_default(self):
        Stage = self.env["hr.recruitment.stage"]
        self.assertIn("legend_hold_2", Stage._fields)
        stage = Stage.create({"name": "Stage 1"})
        self.assertEqual(stage.legend_hold_2, "New Status")
        self.assertFalse(Stage._fields["legend_hold_2"].readonly)

    def test_02_update_new_status(self):
        stage = self.env["hr.recruitment.stage"].create({"name": "Stage 2"})
        stage.write({"legend_hold_2": "Interview Pending"})
        self.assertEqual(stage.legend_hold_2, "Interview Pending")

    def test_03_standard_legend_fields_are_present(self):
        Stage = self.env["hr.recruitment.stage"]
        for field_name in (
            "legend_normal",
            "legend_blocked",
            "legend_waiting",
            "legend_done",
            "legend_hold_2",
        ):
            self.assertIn(field_name, Stage._fields)
