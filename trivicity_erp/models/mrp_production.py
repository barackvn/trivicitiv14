# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class MrpProduction(models.Model):
    """ Manufacturing Orders """
    _inherit = 'mrp.production'

    box_package_id = fields.Many2one(
        'box.package', 'Box Packaging', copy=False)