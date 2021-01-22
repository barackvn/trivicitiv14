# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import pytz
import logging
from odoo import models, fields, api, _
from datetime import datetime, timedelta

utc = pytz.utc

_logger = logging.getLogger("Shopify")


class ShopifyOrderDataQueueEpt(models.Model):
    _inherit = "shopify.order.data.queue.ept"

    def import_order_cron_action(self, ctx={}):
        instance_id = ctx.get('shopify_instance_id')
        instance = self.env['shopify.instance.ept'].browse(instance_id)
        from_date = instance.last_date_order_import
        to_date = datetime.now()
        if not from_date:
            from_date = to_date - timedelta(3)

        self.shopify_create_order_data_queues(instance, from_date, to_date, created_by="scheduled_action",
                                              order_type="shipped")
        self.shopify_create_order_data_queues(instance, from_date, to_date, created_by="scheduled_action",
                                              order_type="unshipped")
        self.env['shopify.order.data.queue.line.ept'].auto_import_order_queue_data()
        return
