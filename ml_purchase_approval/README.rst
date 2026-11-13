.. image:: https://img.shields.io/badge/licence-LGPL--3-blue.svg
   :target: https://www.gnu.org/licenses/lgpl-3.0.en.html
   :alt: License: LGPL-3
.. image:: https://img.shields.io/badge/version-1.0-green.svg
   :alt: Version
.. image:: https://img.shields.io/badge/Odoo%20Version-19.0-brightgreen.svg
   :alt: Odoo 19 Compatible

Multi-Level Purchase Approval
=============================

A comprehensive approval workflow management system for Odoo v19 that enables configurable multi-level purchase order approvals with amount-based thresholds and hierarchical approval chains.

Overview
--------

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

Installation
------------

1. Install the module through Odoo Apps
2. Navigate to **Purchases → Configuration → Approval Groups**
3. Create your approval groups and configure approval levels
4. Assign users to each approval level with appropriate thresholds
5. Select the desired approval group when creating purchase orders

Configuration Guide
-------------------

**Step 1: Create Approval Groups**
   - Go to *Purchases → Configuration → Approval Groups*
   - Create groups for different departments or purchase types

**Step 2: Configure Approval Levels**
   - Define hierarchical levels within each group
   - Set amount thresholds for each level
   - Specify whether the level is for recommendation or approval
   - Assign authorized users to each level

**Step 3: Assign to Purchase Orders**
   - Select the appropriate approval group when creating POs
   - The system automatically routes through approval levels based on amount

**Step 4: Approval Process**
   - Users receive notifications for pending approvals
   - Approvers can add comments during the approval process
   - Complete audit trail maintained for compliance

Usage
-----

1. **Create Purchase Order**: Select an approval group during PO creation
2. **Request Approval**: Use the "Request Approval" button to initiate workflow
3. **Multi-Level Review**: Orders progress through configured approval levels
4. **Final Approval**: Complete the chain to confirm the purchase order
5. **Audit Trail**: View complete history in the Approval tab

Support
-------

For technical support, bug reports, or feature requests:
- **Email**: support@zalinotech.com
- **Website**: https://zalinotech.com
- **Issue Tracker**: GitHub Repository Issues

Company
-------

**Developed & Maintained by:**
`Zalino Tech Private Limited <https://zalinotech.com>`__

**Lead Development Team:**
- **Project Lead**: Zahid Anwar
- **Quality Assurance**: Zalino Tech QA Team
- **Technical Support**: Zalino Tech Support Team

License
-------

This module is licensed under the **Lesser General Public License v3.0 (LGPL-3)**.
For complete license details, visit: https://www.gnu.org/licenses/lgpl-3.0.en.html

Credits
-------

- **Lead Developer (v19):** Zahid Anwar
- **Lead Developer (v18):** Zahid Anwar
- **Contact:** info@zalinotech.com

Bug Reporting
-------------

Found an issue? Please report it through our GitHub Issue Tracker. Before submitting:
- Check existing issues to avoid duplicates
- Provide detailed reproduction steps
- Include Odoo version and module version
- Attach relevant screenshots or error logs

Maintainer
----------

.. image:: https://zalinotech.com/wp-content/uploads/2024/09/ZalinoLogo.png
   :alt: Zalino Tech Private Limited
   :target: https://zalinotech.com
   :width: 200
   :height: 60

**Zalino Tech Private Limited** specializes in Odoo customization, implementation, and support services. We provide enterprise-grade solutions tailored to your business needs.

- **Website**: https://zalinotech.com
- **Email**: info@zalinotech.com
- **Address**: Islamabad, Pakistan

Changelog
---------

**Version 1.0** (2025-09-23)
- Initial release for Odoo v19
- Multi-level approval workflow implementation
- Amount-based threshold configuration
- Approval history and audit trail
- Seamless integration with purchase module