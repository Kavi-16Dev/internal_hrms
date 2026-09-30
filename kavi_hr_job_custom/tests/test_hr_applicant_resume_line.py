# -*- coding: utf-8 -*-
from psycopg2 import IntegrityError

from odoo.tools import mute_logger

from .common import KaviHrJobCustomCommon


class TestHrApplicantResumeLine(KaviHrJobCustomCommon):

    def setUp(self):
        super().setUp()
        self.line_type = self.env['hr.resume.line.type'].search(
            [('name', '=', 'Experience')], limit=1
        ) or self.env['hr.resume.line.type'].create({'name': 'Experience', 'sequence': 10})

    def test_onchange_external_url_derives_name(self):
        line = self.ResumeLine.new({
            'applicant_id': self.applicant.id,
            'line_type_id': self.line_type.id,
            'external_url': 'https://www.example.com',
        })
        line._onchange_external_url()
        self.assertEqual(line.name, 'Example')

    def test_onchange_external_url_does_not_override_existing_name(self):
        line = self.ResumeLine.new({
            'applicant_id': self.applicant.id,
            'line_type_id': self.line_type.id,
            'name': 'Already Set',
            'external_url': 'https://www.example.com',
        })
        line._onchange_external_url()
        self.assertEqual(line.name, 'Already Set')

    def test_compute_color_for_external_course(self):
        line = self.ResumeLine.create({
            'applicant_id': self.applicant.id,
            'line_type_id': self.line_type.id,
            'name': 'Odoo Certification',
            'course_type': 'external',
            'external_url': 'https://www.odoo.com',
        })
        self.assertEqual(line.color, '#a2a2a2')
        self.assertTrue(line.external_url)

    def test_date_start_must_be_before_date_end(self):
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self.ResumeLine.create({
                'applicant_id': self.applicant.id,
                'line_type_id': self.line_type.id,
                'name': 'Bad Dates',
                'date_start': '2024-06-01',
                'date_end': '2024-01-01',
            })
            self.env.flush_all()

    def test_date_end_optional(self):
        # An ongoing role (no end date) must be perfectly valid.
        line = self.ResumeLine.create({
            'applicant_id': self.applicant.id,
            'line_type_id': self.line_type.id,
            'name': 'Current Role',
            'date_start': '2024-01-01',
        })
        self.assertFalse(line.date_end)

    def test_applicant_id_required(self):
        with self.assertRaises(Exception):
            self.ResumeLine.create({
                'name': 'Missing Applicant',
                'line_type_id': self.line_type.id,
                'date_start': '2024-01-01',
            })
