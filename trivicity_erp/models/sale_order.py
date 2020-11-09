# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.onchange('partner_shipping_id', 'partner_id', 'company_id')
    def onchange_partner_shipping_id(self):
        """
        Trigger the change of fiscal position when the shipping address is modified.
        """
        if self.partner_id and self.partner_id.property_account_position_id:
            self.fiscal_position_id = self.partner_id.property_account_position_id.id
        else:
            super(SaleOrder, self).onchange_partner_shipping_id()
        return {}

    @api.onchange('partner_id')
    def onchange_partner_analytic_id(self):
        if self.partner_id and self.partner_id.analytic_account_id:
            self.analytic_account_id = self.partner_id.analytic_account_id.id
