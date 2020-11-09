# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    analytic_account_id = fields.Many2one('account.analytic.account',string='Analytic Account')  

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if not self.property_account_position_id and self.category_id.mapped('fiscal_position_id'):
            self.property_account_position_id = self.category_id.mapped('fiscal_position_id').ids[0]
        if not self.analytic_account_id and self.category_id.mapped('analytic_account_id'):
            self.analytic_account_id = self.category_id.mapped('analytic_account_id').ids[0]
    


    
