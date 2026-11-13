# -*- coding: utf-8 -*-
{
    "name": "Multi-Level Purchase Approval",
    "version": "19.0.0.0.17",
    "category": "Purchases",
    'sequence': 225,
    "summary": """
    This module adds multi-level approval workflow for purchase orders
        with configurable approval groups, levels, and amount thresholds.
    """,
    'website': "https://www.zalinotech.com",
    'author': 'Zalino Tech (Private) Limited',
    'company': 'Zalino Tech',
    'maintainer': 'Zalino Tech',
    "description": """

This module extends Odoo's native purchase management capabilities by introducing a sophisticated multi-level approval system. Organizations can define custom approval workflows with configurable thresholds, recommendation levels, and hierarchical approval processes to ensure proper financial controls and compliance.

Features
--------

✅ **Approval Group Management**
   - Create and configure approval groups with custom hierarchies
   - Define multiple approval levels within each group

✅ **Amount-Based Thresholds**
   - Set minimum and maximum amount limits for each approval level
   - Automatic routing based on purchase order value

✅ **Multi-Level Workflow**
   - Sequential approval process through configured levels
   - Support for both recommendation and approval stages
   - Configurable user assignments per approval level

✅ **Approval History Tracking**
   - Complete audit trail of all approval actions
   - User comments and timestamps for each approval step
   - Visual indicators for different action types (approved, rejected, returned)

✅ **Seamless Integration**
   - Fully integrated with standard Odoo purchase workflow
   - Maintains all native purchase order functionality
   - Responsive UI with intuitive approval buttons

    """,
    "depends": ['purchase'],
    "data": [
        'security/ir.model.access.csv',
        # 'security/ir_rule.xml',
        'data/data.xml',

        'wizard/approval_wizard.xml',
        'wizard/returned_wizard.xml',

        'views/approval_group_views.xml',
        'views/approval_level_views.xml',

        'views/purchase_order_views.xml',
    ],
    'demo': [],
    'images': ['static/description/banner.png'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
