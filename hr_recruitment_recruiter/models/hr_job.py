from odoo import models
from odoo.exceptions import AccessError


class HrJob(models.Model):
    _inherit = 'hr.job'

    # Fields on the "Offer Letter Components" page (hr_contract_salary).
    # Confirm the names in developer mode (hover the fields) and adjust.
    # RECRUITER_EDITABLE_FIELDS = {
    #     'default_contract_id',
    #     'job_title',
    #     'sign_template_id',
    #     'contract_update_template_id',
    #     'sign_copy_partner_id',
    # }

    # Same tuple as kavi_hr_job_custom, plus the Recruiter group.
    # Class attributes in an _inherit class override the parent's.
    _KAVI_HTML_FIELD_EDIT_GROUPS = (
        'hr_recruitment.group_hr_recruitment_user',
        'hr_recruitment.group_hr_recruitment_manager',
        'kavi_hr_job_custom.group_hr_recruitment_hiring_manager',
        'hr_recruitment_recruiter.group_hr_recruiter',
    )

    RECRUITER_EDITABLE_FIELDS = {
    'working_hours', 'leave_eligibility', 'key_responsibilities',
    'html_field_history_metadata',  # written by the HTML field's history feature
    }

    def write(self, vals):
        user = self.env.user
        if (
            not self.env.su
            and user.has_group('hr_recruitment_recruiter.group_hr_recruiter')
            and not user.has_group('hr_recruitment.group_hr_recruitment_user')
            and not user.has_group('hr_recruitment.group_hr_recruitment_manager')
        ):
            if set(vals) - self.RECRUITER_EDITABLE_FIELDS:
                raise AccessError(
                    "Recruiters can only edit the Offer Letter Components of a Job Position."
                )
        return super().write(vals)
