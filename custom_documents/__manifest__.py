# -*- coding: utf-8 -*-
{
    'name': 'Documents (Community)',
    'version': '19.0.0.7.0',
    'category': 'Productivity/Documents',
    'summary': 'Document management, requests, drives and share links '
                '- Community Edition equivalent of Odoo Enterprise Documents',
    'description': """
Documents for Odoo Community
=============================
A custom re-implementation of the core functionality found in the
Odoo Enterprise "Documents" application, built to run on Community Edition:
""",
    'author': 'Custom Development',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'mail', 'portal', 'hr'],
    'external_dependencies': {
        # Only required to use the "Split PDF" Actions-menu entry; every
        # other feature works fine without it.
        'python': ['pypdf'],
    },
    'assets': {
        'web.assets_backend': [
            'custom_documents/static/src/js/documents_link_dialog.js',
            'custom_documents/static/src/js/documents_new_folder_dialog.js',
            'custom_documents/static/src/js/documents_rename_dialog.js',
            'custom_documents/static/src/js/documents_move_dialog.js',
            'custom_documents/static/src/js/documents_versions_dialog.js',
            'custom_documents/static/src/js/documents_split_pdf_dialog.js',
            'custom_documents/static/src/js/documents_new_menu.js',
            'custom_documents/static/src/js/documents_kanban_controller.js',
            'custom_documents/static/src/js/documents_kanban_renderer.js',
            'custom_documents/static/src/js/documents_kanban_view.js',
            'custom_documents/static/src/js/documents_list_controller.js',
            'custom_documents/static/src/js/documents_list_renderer.js',
            'custom_documents/static/src/js/documents_list_view.js',
            'custom_documents/static/src/js/documents_search_panel.js',
            'custom_documents/static/src/js/documents_file_viewer.js',
            'custom_documents/static/src/js/documents_share_dialog.js',
            'custom_documents/static/src/js/documents_file_viewer_hook.js',
            'custom_documents/static/src/xml/documents_dialogs.xml',
            'custom_documents/static/src/xml/documents_new_menu.xml',
            'custom_documents/static/src/xml/documents_kanban_view.xml',
            'custom_documents/static/src/xml/documents_kanban_renderer.xml',
            'custom_documents/static/src/xml/documents_list_view.xml',
            'custom_documents/static/src/xml/documents_list_renderer.xml',
            'custom_documents/static/src/xml/documents_search_panel.xml',
            'custom_documents/static/src/xml/documents_file_viewer.xml',
            'custom_documents/static/src/scss/documents_search_panel.scss',
            'custom_documents/static/src/scss/documents_list_renderer.scss',
            'custom_documents/static/src/scss/documents_file_viewer.scss',
        ],
    },
    'data': [
        'security/documents_security.xml',
        'security/ir.model.access.csv',
        'data/documents_data.xml',
        'data/mail_templates.xml',
        'data/documents_cron.xml',
        'views/documents_folder_views.xml',
        'views/documents_document_views.xml',
        'views/documents_tag_views.xml',
        'views/documents_share_views.xml',
        'views/documents_request_wizard_views.xml',
        'views/documents_config_settings_views.xml',
        'views/hr_employee_views.xml',
        'views/documents_menus.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
