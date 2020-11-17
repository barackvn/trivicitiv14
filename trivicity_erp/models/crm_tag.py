# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ResPartnerCategory(models.Model):
    _inherit = "res.partner.category"

    analytic_account_id = fields.Many2one('account.analytic.account',string='Analytic Account')
    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position')

