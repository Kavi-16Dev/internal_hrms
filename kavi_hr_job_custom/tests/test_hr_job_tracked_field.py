# -*- coding: utf-8 -*-
from psycopg2 import IntegrityError

from odoo.tests.common import Form
from odoo.tools import mute_logger

from .common import KaviHrJobCustomCommon


class TestHrJobTrackedField(KaviHrJobCustomCommon):

    def test_data_file_records_loaded(self):
        self.assertEqual(self.tracked_budgeting.field_key, 'budgeting_information')
        self.assertEqual(self.tracked_key_resp.field_key, 'key_responsibilities')
        self.assertTrue(self.tracked_budgeting.active)
        self.assertTrue(self.tracked_key_resp.active)

    def test_get_tracked_fields_map_only_active(self):
        mapping = self.TrackedField._get_tracked_fields_map()
        self.assertEqual(mapping, {
            'budgeting_information': 'Budgeting Information',
            'key_responsibilities': 'Key Roles and Responsibilities',
        })

        self.tracked_key_resp.active = False
        mapping = self.TrackedField._get_tracked_fields_map()
        self.assertNotIn('key_responsibilities', mapping)
        self.assertIn('budgeting_information', mapping)
        self.tracked_key_resp.active = True

    def test_onchange_field_key_sets_label(self):
        with Form(self.TrackedField) as f:
            f.field_key = 'budgeting_information'
            self.assertEqual(f.field_label, 'Budgeting Information')

    def test_field_key_uniqueness_constraint(self):
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self.TrackedField.create({
                'field_key': 'budgeting_information',
                'field_label': 'Duplicate Budgeting Information',
            })
            self.env.flush_all()

    def test_name_get_uses_field_label(self):
        display = self.tracked_key_resp.display_name
        self.assertEqual(display, 'Key Roles and Responsibilities')
