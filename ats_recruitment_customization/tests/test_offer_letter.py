from odoo.tests.common import TransactionCase
from odoo import fields


class TestOfferLetter(TransactionCase):

    # ===================================================
    # SETUP
    # ===================================================

    def setUp(self):
        super().setUp()

        # ---------------------------------------------------
        # Create Department
        # ---------------------------------------------------

        self.department = self.env['hr.department'].create({
            'name': 'Development'
        })

        # ---------------------------------------------------
        # Create Job Position
        # ---------------------------------------------------

        self.job_position = self.env['hr.job'].create({
            'name': 'Software Engineer',
            'department_id': self.department.id,
        })

        # ---------------------------------------------------
        # Create Applicant
        # ---------------------------------------------------

        self.applicant = self.env['hr.applicant'].create({

            'partner_name': 'John David',

            'job_id': self.job_position.id,

            'department_id': self.department.id,

            'offer_date': fields.Date.today(),

            'joining_date': fields.Date.today(),

            'manager_name': 'Sravani',

            'job_address': 'Chennai',

            'company_name': 'Kavi Software',

            'compensation': '8 LPA',

            'medical_retirement_benefits':
                'Medical Insurance Included',

            'reimbursement_of_expenses':
                'Travel Reimbursement',

            'right_to_transfer':
                'Transfer based on business needs',

            'company_policies':
                'Follow company policies',

            'maintain_confidentiality':
                'Maintain confidentiality',

            'offer_salary_structure':
                '<p>Basic Salary : 50000</p>',

            'roles_responsibilities':
                '<ul><li>Develop Features</li></ul>',

            'terms_and_conditions':
                '<p>Standard Terms and Conditions</p>',
        })

    # ===================================================
    # TEST 1
    # Applicant Creation
    # ===================================================

    def test_applicant_creation(self):
        """Check applicant record created"""

        self.assertTrue(self.applicant)

    # ===================================================
    # TEST 2
    # Offer Date
    # ===================================================

    def test_offer_date(self):
        """Check offer date exists"""

        self.assertTrue(
            self.applicant.offer_date
        )

    # ===================================================
    # TEST 3
    # Joining Date
    # ===================================================

    def test_joining_date(self):
        """Check joining date exists"""

        self.assertTrue(
            self.applicant.joining_date
        )

    # ===================================================
    # TEST 4
    # Compensation
    # ===================================================

    def test_compensation(self):
        """Check compensation value"""

        self.assertEqual(
            self.applicant.compensation,
            '8 LPA'
        )

    # ===================================================
    # TEST 5
    # Roles and Responsibilities
    # ===================================================

    def test_roles_responsibilities(self):
        """Check roles and responsibilities"""

        self.assertIn(
            'Develop Features',
            self.applicant.roles_responsibilities
        )

    # ===================================================
    # TEST 6
    # Terms and Conditions
    # ===================================================

    def test_terms_conditions(self):
        """Check terms and conditions"""

        self.assertIn(
            'Standard Terms',
            self.applicant.terms_and_conditions
        )

    # ===================================================
    # TEST 7
    # Report Action
    # ===================================================

    def test_report_action(self):
        """Check report action exists"""

        report = self.env.ref(
            'ats_recruitment_customization.action_report_offer_letter'
        )

        self.assertTrue(report)

    # ===================================================
    # TEST 8
    # PDF Generation
    # ===================================================

    def test_offer_letter_pdf_generation(self):
        """Check Offer Letter PDF generation"""

        report = self.env.ref(
            'ats_recruitment_customization.action_report_offer_letter'
        )

        pdf_content, content_type = report._render_qweb_pdf(
            report.report_name,
            self.applicant.id
        )

        # Validate report generated
        self.assertTrue(pdf_content)

        # Validate report content length
        self.assertGreater(
            len(pdf_content),
            0
        )

        # Validate content type exists
        self.assertTrue(content_type)

    # ===================================================
    # TEST 9
    # Company Name
    # ===================================================

    def test_company_name(self):
        """Check company name"""

        self.assertEqual(
            self.applicant.company_name,
            'Kavi Software'
        )

    # ===================================================
    # TEST 10
    # Manager Name
    # ===================================================

    def test_manager_name(self):
        """Check manager name"""

        self.assertEqual(
            self.applicant.manager_name,
            'Sravani'
        )

    # ===================================================
    # TEST 11
    # Medical Benefits
    # ===================================================

    def test_medical_benefits(self):
        """Check medical benefits"""

        self.assertEqual(
            self.applicant.medical_retirement_benefits,
            'Medical Insurance Included'
        )

    # ===================================================
    # TEST 12
    # Reimbursement
    # ===================================================

    def test_reimbursement(self):
        """Check reimbursement details"""

        self.assertEqual(
            self.applicant.reimbursement_of_expenses,
            'Travel Reimbursement'
        )

    # ===================================================
    # TEST 13
    # Company Policies
    # ===================================================

    def test_company_policies(self):
        """Check company policies"""

        self.assertEqual(
            self.applicant.company_policies,
            'Follow company policies'
        )

    # ===================================================
    # TEST 14
    # Confidentiality
    # ===================================================

    def test_confidentiality(self):
        """Check confidentiality"""

        self.assertEqual(
            self.applicant.maintain_confidentiality,
            'Maintain confidentiality'
        )

    # ===================================================
    # TEST 15
    # Salary Structure HTML
    # ===================================================

    def test_offer_salary_structure(self):
        """Check salary structure"""

        self.assertIn(
            'Basic Salary',
            self.applicant.offer_salary_structure
        )

    # ===================================================
    # TEST 16
    # Update Compensation
    # ===================================================

    def test_update_compensation(self):
        """Check compensation update"""

        self.applicant.compensation = '10 LPA'

        self.assertEqual(
            self.applicant.compensation,
            '10 LPA'
        )

    # ===================================================
    # TEST 17
    # Multiple Applicants
    # ===================================================

    def test_multiple_applicants(self):
        """Check multiple applicants"""

        applicant_2 = self.env['hr.applicant'].create({

            'partner_name': 'David',

            'job_id': self.job_position.id,

            'department_id': self.department.id,
        })

        self.assertNotEqual(
            self.applicant.partner_name,
            applicant_2.partner_name
        )

    # ===================================================
    # TEST 18
    # Empty Roles
    # ===================================================

    def test_empty_roles(self):
        """Check empty roles"""

        self.applicant.roles_responsibilities = False

        self.assertFalse(
            self.applicant.roles_responsibilities
        )