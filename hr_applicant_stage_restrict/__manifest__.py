# -*- coding: utf-8 -*-
{
    'name': 'Restrict Stage to Recruiter',
    'version': '19.0.2.0.0',
    'category': 'Human Resources/Recruitment',
    'summary': "Only the assigned Recruiter can change an applicant's pipeline stage",
    'description': """
HR Recruitment - Restrict Pipeline Stage Change
================================================
By default, any Interviewer assigned to a job applicant can drag / change
the Kanban pipeline stage (e.g. Initial Qualification -> First Interview ->
Second Interview -> Contract Proposal -> Contract Signed).

Configuration
=============
Nothing to configure. The restriction is based on the existing "Recruiter"
(user_id) field of hr.applicant and the standard Recruitment Manager
security group (hr_recruitment.group_hr_recruitment_manager).
""",
    'author': 'Custom Development',
    'license': 'LGPL-3',
    'depends': ['base','hr_recruitment'],
    'data': [
        'views/hr_applicant_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
