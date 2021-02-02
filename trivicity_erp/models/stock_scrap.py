# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class StockScrap(models.Model):
    _inherit = "stock.scrap"

    def action_validate_scrap_wo(self):
        if self.workorder_id:
            order = self.workorder_id.action_open_manufacturing_order()
            if self.production_id.state == 'done':
                self.action_validate()
                return order
            else:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'mrp.production',
                    'views': [[self.env.ref('mrp.mrp_production_form_view').id, 'form']],
                    'res_id': self.production_id.id,
                    'target': 'main',
                }
        return True
