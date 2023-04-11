# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models, tools, SUPERUSER_ID, _
_logger = logging.getLogger(__name__)
FTYPES = ['docx', 'pptx', 'xlsx', 'opendoc']
class IrAttachment(models.Model):
    _inherit = 'ir.attachment'
    @api.model
    def _index(self, bin_data, mimetype):
        if self.res_model in [
            'report.excel',
        ]:
            return
        for ftype in FTYPES:
            if buf := getattr(self, f'_index_{ftype}')(bin_data):
                return buf
        return super(IrAttachment, self)._index(bin_data, mimetype)
