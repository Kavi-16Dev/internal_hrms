from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _load_menus_blacklist(self):
        """hr_recruitment hides the unfiltered 'By Job Positions' menu from
        anyone who is an Interviewer but not an Officer. A Recruiter is exactly
        that (the group implies Interviewer), so treat them like an Officer for
        this one menu: show the unfiltered menu, hide the interviewer one."""
        res = super()._load_menus_blacklist()
        user = self.env.user
        if (
            user.has_group('hr_recruitment_recruiter.group_hr_recruiter')
            and not user.has_group('hr_recruitment.group_hr_recruitment_user')
        ):
            all_jobs = self.env.ref('hr_recruitment.menu_hr_job_position', raise_if_not_found=False)
            own_jobs = self.env.ref('hr_recruitment.menu_hr_job_position_interviewer', raise_if_not_found=False)
            if all_jobs and all_jobs.id in res:
                res.remove(all_jobs.id)
            if own_jobs and own_jobs.id not in res:
                res.append(own_jobs.id)
        return res
