# Part of the hr_recruitment_duplicate_detection module.

from odoo import _, http
from odoo.http import request
from odoo.addons.website_hr_recruitment.controllers.main import WebsiteHrRecruitment


class WebsiteHrRecruitmentDuplicate(WebsiteHrRecruitment):
    """Public Email/Phone duplicate warning and submission protection.

    The public form checks Email and Phone only. Candidate Name and LinkedIn
    never participate in duplicate matching.

    Duplicate matching is scoped to the selected Job Position: an existing
    Email OR an existing Phone for an application on the SAME Job Position
    is enough to block submission. The same Email/Phone used for a
    DIFFERENT Job Position is not a duplicate and is allowed.
    """

    @staticmethod
    def _duplicate_warning_message(job_name, email_duplicate, phone_duplicate):
        """Build the public duplicate warning using only matched fields."""
        if not job_name:
            return None

        if email_duplicate and phone_duplicate:
            return _(
                "An application already exists for the position '%(job)s' "
                "with the same email address and Phone number."
            ) % {'job': job_name}

        if email_duplicate:
            return _(
                "An application already exists for the position '%(job)s' "
                "with the same email address."
            ) % {'job': job_name}

        if phone_duplicate:
            return _(
                "An application already exists for the position '%(job)s' "
                "with the same Phone Number."
            ) % {'job': job_name}

        return None

    @staticmethod
    def _build_public_applicant(job, email, phone):
        """Create a transient hr.applicant record for duplicate lookup.

        No database record is created here. This only reuses the exact same
        normalization/search logic used by the server-side create()/write()
        protection.
        """
        Applicant = request.env['hr.applicant'].sudo()

        vals = {
            'job_id': job.id,
            'email_from': email or False,
        }

        for field_name in ('partner_phone', 'mobile', 'partner_mobile'):
            if field_name in Applicant._fields:
                vals[field_name] = phone or False
                break

        return Applicant.new(vals)

    @http.route(
        '/website_hr_recruitment/check_recent_application',
        type='jsonrpc',
        auth='public',
        website=True,
    )
    def check_recent_application(self, field, value, job_id, email=None, phone=None):
        # Name and LinkedIn are never duplicate-validated by this module.
        if field not in ('email', 'phone'):
            return {'message': None}

        if field == 'email' and email is None:
            email = value
        if field == 'phone' and phone is None:
            phone = value

        email = (email or '').strip()
        phone = (phone or '').strip()

        if not email and not phone:
            return {'message': None}

        try:
            job = request.env['hr.job'].sudo().browse(int(job_id)).exists()
        except (TypeError, ValueError):
            job = request.env['hr.job']

        if not job:
            return {'message': None}

        applicant = self._build_public_applicant(job, email, phone)
        _, matched_email, matched_phone = applicant._find_duplicate_applicants()

        return {
            'message': self._duplicate_warning_message(
                job.name,
                matched_email,
                matched_phone,
            )
        }
