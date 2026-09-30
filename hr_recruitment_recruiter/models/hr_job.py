from lxml import etree

from odoo import fields, models
from odoo.exceptions import AccessError

RECRUITER_GROUP = 'hr_recruitment_recruiter.group_hr_recruiter'

# Same groups as kavi_hr_job_custom uses for key_responsibilities, plus Recruiter.
KEY_RESP_GROUPS = (
    'hr_recruitment.group_hr_recruitment_user,'
    'hr_recruitment.group_hr_recruitment_manager,'
    'kavi_hr_job_custom.group_hr_recruitment_hiring_manager,'
    + RECRUITER_GROUP
)


class HrJob(models.Model):
    _inherit = 'hr.job'

    # Fields a Recruiter may save (Offer Letter Components page).
    RECRUITER_EDITABLE_FIELDS = {
        'working_hours',
        'leave_eligibility',
        'key_responsibilities',
        'html_field_history_metadata',  # written by the HTML field's history feature
    }

    # kavi_hr_job_custom restricts this field to Officer/Manager/Hiring Manager.
    # A field the user cannot access is dropped from the compiled form, so the
    # Recruiter would never see "Key Roles and Responsibilities".
    key_responsibilities = fields.Html(groups=KEY_RESP_GROUPS)

    def _kavi_user_is_interviewer_only(self):
        """kavi_hr_job_custom removes the 'Offer Letter Components' page from
        the job form for 'interviewer only' users. A Recruiter implies
        Interviewer, so exclude Recruiters explicitly."""
        if self.env.user.has_group(RECRUITER_GROUP):
            return False
        return super()._kavi_user_is_interviewer_only()

    def _is_recruiter_only(self):
        user = self.env.user
        return (
            not self.env.su
            and user.has_group(RECRUITER_GROUP)
            and not user.has_group('hr_recruitment.group_hr_recruitment_user')
            and not user.has_group('hr_recruitment.group_hr_recruitment_manager')
        )

    def write(self, vals):
        if self._is_recruiter_only() and set(vals) - self.RECRUITER_EDITABLE_FIELDS:
            raise AccessError(
                "Recruiters can only edit the Offer Letter Components of a Job Position."
            )
        return super().write(vals)

    def get_view(self, view_id=None, view_type='form', **options):
        """Everything on the job form is read-only for a Recruiter except the
        Offer Letter Components fields."""
        result = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == 'form' and self._is_recruiter_only():
            doc = etree.fromstring(result['arch'])
            for node in doc.xpath("//field"):
                if node.get('name') not in self.RECRUITER_EDITABLE_FIELDS:
                    node.set('readonly', '1')
            result['arch'] = etree.tostring(doc, encoding='unicode')
        return result