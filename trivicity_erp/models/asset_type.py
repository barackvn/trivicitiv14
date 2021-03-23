# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AssetType(models.Model):
    _name = 'asset.type'
    _description='Asset Type'
    _rec_name = 'type'

    
    type = fields.Char(string='Type')
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, default=lambda self: self.env.company)
    fixed_asset_acc_id = fields.Many2one('account.account',string='Fixed Asset Account', domain="[('company_id', '=', company_id), ('is_off_balance', '=', False)]")
    depreciation_acc_id = fields.Many2one('account.account', string='Depreciation Account', domain="[('internal_type', '=', 'other'), ('deprecated', '=', False), ('company_id', '=', company_id), ('is_off_balance', '=', False)]")
    expense_acc_id = fields.Many2one('account.account', string='Expense Account', domain="[('internal_type', '=', 'other'), ('deprecated', '=', False), ('company_id', '=', company_id), ('is_off_balance', '=', False)]")


class AccountAsset(models.Model):
    _inherit = 'account.asset'

    asset_type_id = fields.Many2one('asset.type', string='Asset Type')

    @api.onchange('asset_type_id')
    def onchange_asset_type_id(self):
        if self.asset_type_id: 
            self.account_asset_id = self.asset_type_id.fixed_asset_acc_id.id
            self.account_depreciation_id = self.asset_type_id.depreciation_acc_id.id
            self.account_depreciation_expense_id = self.asset_type_id.expense_acc_id.id


