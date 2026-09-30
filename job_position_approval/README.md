# Job Position Publish Approval Flow (Odoo 19 CE)

## What this module does
- Adds a boolean field **"Job Position Approver"** on `res.users`
  (Settings > Users & Companies > Users > Preferences tab). Anyone with this
  flag acts as the Recruitment Administrator.
- Adds an `approval_state` field on `hr.job` with values:
  `Draft → Submitted → Approved (Published) → Closed (Unpublished)`, plus `Cancelled`.
- Adds workflow buttons: **Submit for Approval**, **Approve**, **Reject**,
  **Position Filled – Notify Admin**, **Close (Unpublish)**, **Cancel**,
  **Reset to Draft**.
- Approve/Reject/Close/Cancel/Archive are restricted to users flagged as
  Job Position Approver (enforced both in the view and in `write()`, so it
  can't be bypassed from the list view or the Archive action in the cog menu).
- On **Submit**: an activity ("Job Position Approval") is scheduled for every
  Approver.
- On **Approve**: state → Approved, `is_published` is set to `True`
  (auto-publish to the website), the pending activity is marked done, and an
  email is sent to the requester (`user_id` / Recruiter on the job).
- On **Reject**: state → Draft, `is_published` is set to `False`, the pending
  activity is marked done, and a rejection email is sent to the requester.
- **Position Filled – Notify Admin**: available to non-approvers once a job
  is Approved; posts a log note to the Approver(s) and schedules a follow-up
  activity, replacing the need to manually type an `@mention` log note.
- **Close (Unpublish)**: Approver-only; sets `is_published = False` (the
  single flag that controls visibility everywhere the job appears — career
  page, `/jobs` website, etc.) and closes the follow-up activity.
- Archiving is only allowed for Approvers, and only once a job is Closed or
  Cancelled.

## Install
1. Copy the `job_position_approval` folder into your Odoo `addons` path.
2. Restart the Odoo service.
3. Apps > Update Apps List > search **"Job Position Publish Approval Flow"** > Install.
4. Go to **Settings > Users & Companies > Users**, open each Recruitment
   Administrator's record, and enable **Job Position Approver**.

## ⚠️ Please verify after install (important)
This module was written and syntax-validated offline, without a live Odoo 19
database to test against, so two things depend on your exact installed
modules and should be checked once you install it:

1. **Parent view IDs** — the module inherits `hr.view_hr_job_form` (classic
   Job Position form) and `hr_recruitment.hr_job_simple_form` (the quick-create
   form used from the Recruitment dashboard). If your instance names these
   views differently (rare, but possible depending on installed
   localizations/apps), the module will fail to install with an error naming
   the missing `inherit_id`. Fix: enable Developer Mode, go to
   **Settings > Technical > Views**, filter by Model = `hr.job`, note the
   actual XML ID of the form view(s), and update
   `views/hr_job_views.xml` accordingly.
2. **`is_published` field name** — confirmed as the standard field Odoo uses
   for "Is Published" on `hr.job` (added by `website_hr_recruitment`). If you
   have a customization that renamed it, update `models/hr_job.py`.

If install fails on a view inheritance error, this is a 2-minute fix (just
correcting one `ref=` attribute) — it does not affect the model/business
logic in `models/hr_job.py`, which is independent of the view layer.

## Notes / assumptions
- "Approve/Reject" only applies while `approval_state == 'submitted'`.
- Since the task description doesn't list a separate "Rejected" state (only
  Draft/Submitted/Approved/Closed/Cancel), **Reject returns the job to
  Draft** so the Recruitment User can fix and resubmit it. If you'd rather
  keep a distinct "Rejected" state visible in the statusbar instead of
  bouncing back to Draft, that's a small change to `action_reject` and the
  `approval_state` selection — let me know and I'll adjust it.
- Email notifications use two `mail.template` records
  (`email_template_job_approved`, `email_template_job_rejected`) that you can
  freely edit from **Settings > Technical > Email Templates**.
- Multi-company/multi-website: `is_published` is the single source of truth
  used across the website/careers pages, so unpublishing it once unpublishes
  it everywhere it's rendered.
