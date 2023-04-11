# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class MrpWorkCenter(models.Model):
    """ Manufacturing Work Centers """
    _inherit = 'mrp.workcenter'

    user_ids = fields.Many2many('res.users', string='Allowed Users', default=lambda self: self.env.user.ids)


class MrpWorkOrder(models.Model):
    """ Manufacturing Work Orders """
    _inherit = 'mrp.workorder'

    show_button = fields.Boolean(string='Show Button', compute='compute_show_button')

    @api.depends('workcenter_id')
    def compute_show_button(self):
        for rec in self:
            rec.show_button = self.env.uid in rec.workcenter_id.user_ids.ids

    def read(self, fields=None, load='_classic_read'):
        return super(MrpWorkOrder, self.sudo()).read(fields, load)

    def action_manufacturing_order_with_scrap(self):
        self.ensure_one()
        return {
            'name': _('Scrap'),
            'view_mode': 'form',
            'res_model': 'stock.scrap',
            'view_id': self.env.ref('trivicity_erp.stock_scrap_form_triviciti').id,
            'type': 'ir.actions.act_window',
            'context': {'default_company_id': self.production_id.company_id.id,
                        'default_workorder_id': self.id,
                        'default_production_id': self.production_id.id,
                        'product_ids': self.production_id.product_id.ids},
            'target': 'new',
        }