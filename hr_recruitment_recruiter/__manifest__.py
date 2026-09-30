{
    'name': 'Recruitment: Recruiter Role',
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Recruitment',
    'author': 'KKR - Tech Consulant',
    'summary': 'Recruiter group: manage applications, interviews and offers; read-only jobs',
    'depends': ['base', 'calendar', 'hr', 'hr_recruitment', 'ats_recruitment_customization', 'kavi_hr_job_custom'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        'views/menu_views.xml',
    ],
    'license': 'LGPL-3',
}
