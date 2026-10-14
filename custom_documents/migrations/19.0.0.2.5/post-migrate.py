# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


BODY_HTML = r'''
<div style="margin:0; padding:0; font-family:Arial,Helvetica,sans-serif; font-size:14px; color:#212529; background-color:#ffffff;">
    <div style="max-width:900px; margin:0 auto; padding:38px 32px;">
        <t t-set="recipient_name" t-value="object.request_user_id.name if object.request_user_id else (object.request_partner_id.name if object.request_partner_id else '')"/>
        <t t-if="recipient_name">
            <p style="margin:0 0 24px 0; line-height:1.6;">Hello <t t-out="recipient_name"/>,</p>
        </t>
        <p style="margin:0 0 24px 0; line-height:1.6;">
            <strong><t t-out="object.requested_by_id.name"/></strong>
            <t t-if="object.requested_by_id.email">
                (<t t-out="object.requested_by_id.email"/>)
            </t>
            asks you to provide the following document:
        </p>
        <div style="border-top:1px solid #e5e7eb; border-bottom:1px solid #e5e7eb; padding:26px 0; margin:0 0 24px 0; text-align:center;">
            <p style="margin:0 0 22px 0; font-size:20px; line-height:1.4; font-weight:700; text-align:center;">
                <t t-out="object.name"/>
            </p>
            <t t-if="object.request_note">
                <p style="margin:0; font-style:italic;"><t t-out="object.request_note"/></p>
            </t>
            <t t-if="object.request_share_url">
                <p style="margin:24px 0 0 0;">
                    <a t-att-href="object.request_share_url" style="display:inline-block; padding:14px 28px; background-color:#875a7b; color:#ffffff; text-decoration:none; border-radius:5px; font-weight:600;">
                        Upload the requested document
                    </a>
                </p>
            </t>
        </div>
        <t t-if="object.request_deadline">
            <p style="margin:0 0 16px 0;">Please provide us with the missing document before <t t-out="object.request_deadline"/>.</p>
        </t>
        <p style="margin:0 0 8px 0;">--</p>
        <p style="margin:0 0 30px 0;"><t t-out="object.requested_by_id.name"/></p>
        <div style="border-top:1px solid #e5e7eb; margin-top:28px; padding-top:18px;">
            <p style="margin:0 0 18px 0; line-height:1.6;"><t t-out="object.company_id.name"/></p>
            <p style="margin:0; text-align:center; color:#6b7280; line-height:1.6;">Powered by Odoo Documents</p>
        </div>
    </div>
</div>
'''


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    template = env.ref('custom_documents.mail_template_document_request', raise_if_not_found=False)
    if not template:
        return
    template.sudo().write({
        'name': 'Documents: Document Request',
        'subject': 'Document Request : {{ object.name }}',
        'body_html': BODY_HTML,
        'auto_delete': True,
    })
    imd = env['ir.model.data'].search([
        ('module', '=', 'custom_documents'),
        ('name', '=', 'mail_template_document_request'),
    ], limit=1)
    if imd and imd.noupdate:
        imd.sudo().write({'noupdate': False})
