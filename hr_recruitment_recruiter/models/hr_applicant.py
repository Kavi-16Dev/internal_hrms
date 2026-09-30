from odoo import fields, models

RECRUITER_GROUP = 'hr_recruitment_recruiter.group_hr_recruiter'

# Same audience as kavi_hr_job_custom's _OFFER_LETTER_GROUPS, plus Recruiter.
# (Confidential Notes is deliberately NOT opened to Recruiters.)
OFFER_GROUPS = (
    'hr_recruitment.group_hr_recruitment_user,'
    'hr_recruitment.group_hr_recruitment_manager,'
    'kavi_hr_job_custom.group_hr_recruitment_hiring_manager,'
    + RECRUITER_GROUP
)


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    # Read by action_submit_offer; without access a Recruiter gets an
    # AccessError when submitting an offer.
    designation = fields.Char(groups=OFFER_GROUPS)
    kavi_salary_structure_history = fields.Html(groups=OFFER_GROUPS)

    def _kavi_user_is_interviewer_only(self):
        """kavi_hr_job_custom hard-codes its allowed groups here and strips the
        'Offer Letter Components' page and the offer fields for anyone else who
        is an Interviewer. Recruiters must keep them (Offer Submission)."""
        if self.env.user.has_group(RECRUITER_GROUP):
            return False
        return super()._kavi_user_is_interviewer_only()
