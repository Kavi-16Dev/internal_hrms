# -*- coding: utf-8 -*-
import base64

from werkzeug.exceptions import NotFound

from odoo import http, _
from odoo.http import request


class DocumentsShareController(http.Controller):

    def _get_share(self, token):
        share = request.env['documents.share'].sudo().search(
            [('access_token', '=', token)], limit=1)
        if not share:
            raise NotFound()
        return share

    @http.route(['/document/share/<string:token>'], type='http',
                auth='public', sitemap=False)
    def share_view(self, token, **kwargs):
        share = self._get_share(token)
        valid = share._check_valid()
        documents = share._get_shared_documents().sudo() if valid else request.env['documents.document'].sudo()

        # A copied link for one file must open THAT file.  Do not send the
        # browser to /odoo/documents/<id>: that is a backend client route and
        # may restore another application (for example Discuss).  For a
        # single available attachment we stream it inline from the secure
        # token route.  Multi-document shares and requested/upload shares
        # continue to use the portal page.
        if valid and len(documents) == 1:
            document = documents[:1]
            if document.attachment_id and document.state != 'requested':
                return request.env['ir.binary'].sudo()._get_stream_from(
                    document.attachment_id
                ).get_response(as_attachment=False)

        return request.render('custom_documents.portal_share_page', {
            'share': share,
            'valid': valid,
            'documents': documents,
        })


    @http.route(['/document/share/<string:token>/file'], type='http',
                auth='public', sitemap=False)
    def share_file(self, token, **kwargs):
        """Stream the one document behind a valid share token inline.

        This route is useful for browsers/iframes and makes the security
        boundary explicit: the attachment is reachable only through a valid
        token that belongs to a share containing exactly one document.
        """
        share = self._get_share(token)
        if not share._check_valid():
            raise NotFound()
        documents = share._get_shared_documents().sudo()
        if len(documents) != 1:
            raise NotFound()
        document = documents[:1]
        if document.state == 'requested' or not document.attachment_id:
            raise NotFound()
        return request.env['ir.binary'].sudo()._get_stream_from(
            document.attachment_id
        ).get_response(as_attachment=False)

    @http.route(['/document/share/<string:token>/download/<int:document_id>'],
                type='http', auth='public', sitemap=False)
    def share_download(self, token, document_id, **kwargs):
        share = self._get_share(token)
        if not share._check_valid() or share.access_mode not in ('download', 'upload'):
            raise NotFound()
        documents = share._get_shared_documents().sudo().filtered(lambda d: d.id == document_id)
        if not documents or not documents.attachment_id:
            raise NotFound()
        attachment = documents.attachment_id
        return request.env['ir.binary']._get_stream_from(attachment).get_response(
            as_attachment=True)

    @http.route(['/document/share/<string:token>/upload'], type='http',
                auth='public', methods=['POST'], csrf=True)
    def share_upload(self, token, upload_file=None, **kwargs):
        share = self._get_share(token)
        if not share._check_valid() or share.access_mode != 'upload':
            raise NotFound()
        if upload_file:
            datas = base64.b64encode(upload_file.read())
            # If the share targets a single requested placeholder document,
            # fulfill it. Otherwise create a fresh document in the folder.
            requested_doc = share.document_ids.filtered(lambda d: d.state == 'requested')[:1]
            if requested_doc:
                requested_doc._create_attachment_from_datas(datas, upload_file.filename)
                requested_doc.action_upload_fulfill()
            else:
                folder = share.folder_id or (share.document_ids[:1].folder_id)
                document = request.env['documents.document'].sudo().create({
                    'name': upload_file.filename,
                    'folder_id': folder.id,
                    'owner_id': share.owner_id.id,
                })
                document._create_attachment_from_datas(datas, upload_file.filename)
                share.document_ids = [(4, document.id)]
        return request.redirect(f'/document/share/{token}')
