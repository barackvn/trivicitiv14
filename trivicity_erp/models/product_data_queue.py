# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import logging

from odoo import models, fields, api, _

_logger = logging.getLogger("Shopify")


class ShopifyProductDataQueue(models.Model):
    _inherit = "shopify.product.data.queue.ept"

    def import_product_cron_action(self, ctx={}):
        instance_id = ctx.get('shopify_instance_id')
        instance = self.env['shopify.instance.ept'].browse(instance_id)

        self.shopify_create_product_data_queue(instance)
        if not ctx.get('is_auto_run_queue'):
            self.env['shopify.product.data.queue.line.ept'].auto_import_product_queue_line_data()
        return
