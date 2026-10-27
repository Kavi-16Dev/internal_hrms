# -*- coding: utf-8 -*-
import io
import json
import zipfile

from werkzeug.exceptions import BadRequest, NotFound

from odoo import http, _
from odoo.http import content_disposition, request


class DocumentsDownloadController(http.Controller):

    @staticmethod
    def _parse_ids(value):
        try:
            ids = json.loads(value or '[]')
            return [int(item) for item in ids]
        except (TypeError, ValueError):
            raise BadRequest()

    @http.route('/documents/download', type='http', auth='user',
                methods=['POST'])
    def download_selection(self, document_ids='[]', folder_ids='[]', **kwargs):
        """Download the current selection of the Documents screen.

        One file is sent as is.  Several files and/or folders are sent as a
        zip in which each selected folder keeps its sub-folder structure.
        Only what the current user can read is included."""
        document_ids = self._parse_ids(document_ids)
        folder_ids = self._parse_ids(folder_ids)
        Document = request.env['documents.document']
        entries = Document._get_download_entries(document_ids, folder_ids)
        if not entries:
            raise NotFound(_('There is nothing to download in this selection.'))

        if len(entries) == 1 and not folder_ids:
            path, document = entries[0]
            return request.env['ir.binary']._get_stream_from(
                document.attachment_id.sudo()
            ).get_response(as_attachment=True)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path, document in entries:
                archive.writestr(path, document.attachment_id.sudo().raw or b'')

        zip_name = 'Documents.zip'
        if len(folder_ids) == 1 and not document_ids:
            folder = request.env['documents.folder'].browse(folder_ids[0]).exists()
            if folder:
                zip_name = f'{folder.name}.zip'
        return request.make_response(buffer.getvalue(), headers=[
            ('Content-Type', 'application/zip'),
            ('Content-Disposition', content_disposition(zip_name)),
        ])
