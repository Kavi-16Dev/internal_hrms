# -*- coding: utf-8 -*-
import re

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    is_duplicate_application = fields.Boolean(
        string='Duplicate Application',
        default=False,
        copy=False,
        tracking=True,
        help='Marks an application as a duplicate when its Email or Phone '
             'matches an existing application. Duplicate applications are '
             'blocked before they can be created.',
    )
    duplicate_of_id = fields.Many2one(
        'hr.applicant',
        string='Duplicate Of',
        copy=False,
        tracking=True,
        help='Original application this record was detected as a duplicate of.',
    )
    duplicate_application_ids = fields.One2many(
        'hr.applicant', 'duplicate_of_id',
        string='Duplicate Applications',
    )
    duplicate_application_count = fields.Integer(
        string='Duplicate Count',
        compute='_compute_duplicate_application_count',
    )


    # ------------------------------------------------------------------
    # Compute methods
    # ------------------------------------------------------------------
    @api.depends('duplicate_application_ids')
    def _compute_duplicate_application_count(self):
        for applicant in self:
            applicant.duplicate_application_count = len(applicant.duplicate_application_ids)

    # ------------------------------------------------------------------
    # Source detection - ADAPT THE KEYWORD LISTS BELOW TO YOUR DATA
    # ------------------------------------------------------------------
    def _is_ocr_digitized_record(self):
        """True when THIS applicant actually went through a Resume OCR /
        "Digitize Resume" pipeline.

        Two independent signals are checked - either one is enough:

        1. `ocr_digitized_resume` context key. This is the primary
           signal for the "Digitalize Resume" wizard shipped by the
           custom_ocr_resume_parsing module (model `ocr.resume`,
           button `ocr_action_submit`): that wizard calls Gemini
           synchronously and only creates the `hr.applicant` record
           once the extracted data is already final, then wraps that
           `create()` call with this context key. It never adds an
           `extract_state` field to hr.applicant, so relying on
           `extract_state` alone would NEVER detect its records (see
           point 2) and rule 3 below would silently stop applying to
           every application created through that button.
        2. `extract_state` field/value - the signal used by Odoo's
           native "Digitize Document" (IAP resume extraction)
           pipeline, kept for compatibility with installs that use
           that pipeline instead of, or alongside, the custom wizard.
           The field only exists on such installs, but its mere
           existence on the MODEL says nothing about any individual
           record - every applicant on such an install would
           otherwise be misclassified, including genuine portal and
           job-board submissions. So this checks both: the field must
           exist AND this record must actually carry a value for it
           (i.e. it was created via that pipeline, which always
           populates it - even 'no_extract_requested' is a real value
           set by that pipeline, as opposed to records never touched
           by it).
        """
        self.ensure_one()
        if self.env.context.get('ocr_digitized_resume'):
            return True
        if 'extract_state' not in self._fields:
            return False
        return bool(self.extract_state)

    def _is_ocr_extraction_pending(self):
        """True while OCR is still busy reading the resume and the
        candidate's real Email/Phone have not been written yet.

        Checking for duplicates against a record in this state means
        checking against a placeholder value (often still the sender/
        forwarding address rather than the candidate's own contact
        details), which produces false "duplicate" matches against
        genuinely new, unrelated candidates. So the duplicate check is
        skipped entirely until extraction has actually finished.
        """
        self.ensure_one()
        if 'extract_state' not in self._fields:
            return False
        return self.extract_state in ('waiting_extraction', 'extracting')

    def _detect_source_type(self):
        """Classify the application source for compatibility/reporting.

        Duplicate blocking is NOT source-dependent anymore. This method is
        retained only for compatibility with existing customizations that may
        inspect the source classification.
        """
        self.ensure_one()

        # Digitized / OCR records are trusted backend input - never portal,
        # regardless of UTM naming. Checked first so it always wins over
        # both the keyword fallback and the website_id signal below.
        if self._is_ocr_digitized_record():
            return 'email'

        # Authoritative signal: any create()/write() happening as part of
        # a website page request (public Apply form included) carries a
        # website_id in context. This does NOT depend on UTM tagging.
        if self.env.context.get('website_id'):
            return 'portal'

        medium_name = (self.medium_id.name or '').lower()
        source_name = (self.source_id.name or '').lower()
        combined = '%s %s' % (medium_name, source_name)

        job_board_keywords = (
            'linkedin', 'indeed', 'naukri', 'monster', 'glassdoor',
            'job board', 'jobboard', 'easy apply',
        )
        email_keywords = ('email', 'mail')
        portal_keywords = ('website', 'portal', 'job portal', 'career', 'careers')

        if any(keyword in combined for keyword in job_board_keywords):
            return 'job_board'
        if any(keyword in combined for keyword in email_keywords):
            return 'email'
        if any(keyword in combined for keyword in portal_keywords):
            return 'portal'
        return 'other'

    # ------------------------------------------------------------------
    # Duplicate lookup
    # ------------------------------------------------------------------
    def _get_contact_values(self):
        """Return normalized (email, phone) tuple for this applicant,
        pulling from whichever fields exist on this Odoo instance
        (hr.applicant delegates some fields to hr.candidate in v17+)."""
        self.ensure_one()
        email = (self.email_from or '').strip().lower()

        phone = ''
        for fname in ('partner_phone', 'mobile', 'partner_mobile'):
            if fname in self._fields:
                value = getattr(self, fname, False)
                if value:
                    phone = self._normalize_phone(value)
                    break
        return email, phone

    @staticmethod
    def _normalize_phone(value):
        """Strip spaces, dashes, parentheses, dots and a leading '+' so
        that '+91 98765-43210' and '9876543210' are still recognised as
        the same number when comparing for duplicates."""
        if not value:
            return ''
        digits_only = re.sub(r'[\s\-\.\(\)]', '', value.strip())
        return digits_only.lstrip('+')

    def _find_duplicate_applicants(self):
        """Search existing applicants for the SAME Job Position with a
        matching Email OR Phone.

        A duplicate is scoped to the Job Position: the same candidate
        (same Email and/or Phone) is allowed to apply to different Job
        Positions, but cannot submit more than one application for the
        same Job Position. Candidate Name and LinkedIn are never used
        for duplicate matching.

        Returns a tuple: (duplicate_applicants, matched_email, matched_phone)
        so callers can build a precise error/warning message.
        """
        self.ensure_one()

        email, phone = self._get_contact_values()
        if not email and not phone:
            return self.env['hr.applicant'], False, False

        if not self.job_id:
            # Without a Job Position there is nothing to scope the check
            # to, so no duplicate can be established.
            return self.env['hr.applicant'], False, False

        domain = [
            ('id', '!=', self._origin.id or 0),
            ('job_id', '=', self.job_id.id),
        ]
        candidates = self.env['hr.applicant'].search(domain)

        matched_email = False
        matched_phone = False
        matches = self.env['hr.applicant']

        for other in candidates:
            other_email, other_phone = other._get_contact_values()
            is_match = False
            if email and other_email and other_email == email:
                matched_email = True
                is_match = True
            if phone and other_phone and other_phone == phone:
                matched_phone = True
                is_match = True
            if is_match:
                matches |= other

        return matches, matched_email, matched_phone

    # ------------------------------------------------------------------
    # Live feedback while filling in the form (advisory, non-blocking)
    # ------------------------------------------------------------------
    @api.onchange('email_from', 'partner_phone', 'mobile', 'partner_mobile', 'job_id')
    def _onchange_check_duplicate_contact(self):
        """Warn the user as soon as a duplicate Email or Phone is entered.

        This is only user feedback. The authoritative block is enforced in
        create()/write() for every application source.
        """
        if self._is_ocr_extraction_pending():
            return

        duplicates, matched_email, matched_phone = self._find_duplicate_applicants()
        if not duplicates:
            return

        field_label = self._duplicate_field_label(matched_email, matched_phone)
        job_name = self.job_id.name or _('this position')
        return {
            'warning': {
                'title': _("Duplicate Application"),
                'message': _(
                    "An application already exists for this %(field)s for the "
                    "position '%(job)s'."
                ) % {
                    'field': field_label,
                    'job': job_name,
                },
            }
        }

    @staticmethod
    def _duplicate_field_label(matched_email, matched_phone):
        if matched_email and matched_phone:
            return _('Email and Phone')
        if matched_phone:
            return _('Phone number')
        return _('Email address')

    # ------------------------------------------------------------------
    # Create / Write overrides - core business rule
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        applicants = super().create(vals_list)
        for applicant in applicants:
            applicant._check_duplicate_on_create()
        return applicants

    def write(self, vals):
        res = super().write(vals)
        # Only re-run the duplicate check when a field that affects the
        # match (email, phone, or the job position) actually changed, or
        # when OCR extraction just finished (extract_state moved out of
        # 'waiting_extraction'/'extracting') - the extracted Email/Phone
        # may have been written in an earlier, still-pending call.
        trigger_fields = {'email_from', 'partner_phone', 'mobile', 'partner_mobile', 'job_id', 'extract_state'}
        if trigger_fields.intersection(vals.keys()):
            for applicant in self:
                applicant._check_duplicate_on_write()
        return res

    def _check_duplicate_on_create(self):
        self.ensure_one()
        if self._is_ocr_extraction_pending():
            # Don't evaluate duplicates against a resume that hasn't
            # finished being read yet - Email/Phone at this point may
            # still be a placeholder rather than the candidate's real
            # contact details, which would produce a false match against
            # an entirely unrelated, genuinely new application. The check
            # runs again automatically on the write() that finalizes the
            # extracted data (see write() / _check_duplicate_on_write).
            return
        duplicates, matched_email, matched_phone = self._find_duplicate_applicants()
        if not duplicates:
            return

        # A duplicate Email OR Phone is a hard business-rule violation for
        # EVERY source: website, job board, email, OCR, imports, and manual
        # backend creation. The record is rejected before the caller can
        # successfully submit/save it.
        raise ValidationError(
            self._duplicate_block_message(matched_email, matched_phone)
        )

    def _check_duplicate_on_write(self):
        """Same hard-block rule as create(), applied when an existing
        application is edited so its Email/Phone/Job now matches another
        record. This prevents 'fixing' a record into a duplicate via edit."""
        self.ensure_one()
        if self._is_ocr_extraction_pending():
            # Same reasoning as _check_duplicate_on_create: don't evaluate
            # a resume that's still mid-extraction against placeholder data.
            return
        duplicates, matched_email, matched_phone = self._find_duplicate_applicants()
        if not duplicates:
            return

        # The same hard block applies to edits. A saved application cannot
        # be changed so that its Email OR Phone duplicates another applicant.
        raise ValidationError(
            self._duplicate_block_message(matched_email, matched_phone)
        )

    def _duplicate_block_message(self, matched_email, matched_phone):
        """Return the exact duplicate-blocking message required by the UI.

        The job position is always taken from the current applicant, so the
        position name is dynamic.  The message identifies only the contact
        field(s) that actually matched an existing application.

        The returned string ends after the duplicate field description.
        """
        self.ensure_one()
        job_name = self.job_id.name or _('this position')

        if matched_email and matched_phone:
            return _(
                "Duplicate application blocked: An application already exists "
                "for the position '%(job)s' with the same email address and "
                "Phone number."
            ) % {'job': job_name}

        if matched_email:
            return _(
                "Duplicate application blocked: An application already exists "
                "for the position '%(job)s' with the same email address."
            ) % {'job': job_name}

        if matched_phone:
            return _(
                "Duplicate application blocked: An application already exists "
                "for the position '%(job)s' with the same Phone Number."
            ) % {'job': job_name}

        return False

    def _notify_recruiter_duplicate(self, original):
        self.ensure_one()
        recruiter = self.user_id or self.job_id.user_id

        current_source = self.medium_id.name or self.source_id.name or _('Unknown')
        original_source = original.medium_id.name or original.source_id.name or _('Unknown')

        body = _(
            "<strong>Duplicate Application Detected</strong><br/>"
            "This application from %(candidate)s (%(email)s) for the position "
            "'%(job)s' matches an existing application "
            "(<a href='#' data-oe-model='hr.applicant' data-oe-id='%(orig_id)s'>#%(orig_id)s</a>) "
            "originally submitted via %(orig_source)s.<br/>"
            "Current application source: %(cur_source)s."
        ) % {
            'candidate': self.partner_name or _('Unknown candidate'),
            'email': self.email_from or '',
            'job': self.job_id.name,
            'orig_id': original.id,
            'orig_source': original_source,
            'cur_source': current_source,
        }

        self.message_post(body=body, subtype_xmlid='mail.mt_note')

        if recruiter:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Duplicate Application - Review Required'),
                note=body,
                user_id=recruiter.id,
            )

    # ------------------------------------------------------------------
    # Smart button action
    # ------------------------------------------------------------------
    def action_view_duplicate_applications(self):
        self.ensure_one()
        return {
            'name': _('Duplicate Applications'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.applicant',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.duplicate_application_ids.ids)],
        }
