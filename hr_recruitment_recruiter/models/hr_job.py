from lxml import etree

from odoo import models
from odoo.exceptions import AccessError


class HrJob(models.Model):
    _inherit = 'hr.job'

    # Same tuple as kavi_hr_job_custom, plus the Recruiter group, so the
    # "Offer Letter Components" page is not stripped from their form.
    _KAVI_HTML_FIELD_EDIT_GROUPS = (
        'hr_recruitment.group_hr_recruitment_user',
        'hr_recruitment.group_hr_recruitment_manager',
        'kavi_hr_job_custom.group_hr_recruitment_hiring_manager',
        'hr_recruitment_recruiter.group_hr_recruiter',
    )

    # Fields a Recruiter may save (Offer Letter Components page).
    RECRUITER_EDITABLE_FIELDS = {
        'working_hours',
        'leave_eligibility',
        'key_responsibilities',
        'html_field_history_metadata',  # written by the HTML field's history feature
    }

    def _is_recruiter_only(self):
        user = self.env.user
        return (
            not self.env.su
            and user.has_group('hr_recruitment_recruiter.group_hr_recruiter')
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
        """UI side of the restriction: everything on the job form is read-only
        for a Recruiter except the Offer Letter Components fields."""
        result = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == 'form' and self._is_recruiter_only():
            doc = etree.fromstring(result['arch'])
            for node in doc.xpath("//field"):
                if node.get('name') not in self.RECRUITER_EDITABLE_FIELDS:
                    node.set('readonly', '1')
            result['arch'] = etree.tostring(doc, encoding='unicode')
        return result