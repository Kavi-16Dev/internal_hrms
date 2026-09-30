# -*- coding: utf-8 -*-
{
    "name": "HR Recruitment - Interviewer Status Customization",
    "version": "19.0.3.0.0",
    "summary": "Add a fifth recruitment kanban status and synchronize Interviewer Status labels with stage tooltips.",
    "category": "Human Resources/Recruitment",
    "depends": ["hr_recruitment"],
    "data": [
        "security/hr_recruitment_custom_security.xml",
        "security/ir.model.access.csv",
        "views/hr_recruitment_stage_views.xml",
        "views/hr_applicant_views.xml",
        "data/ir_cron_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hr_recruitment_custom/static/src/js/interviewer_status_selection.js",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
