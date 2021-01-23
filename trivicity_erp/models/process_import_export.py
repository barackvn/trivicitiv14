# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import base64
import csv
import logging
import time

from datetime import datetime, timedelta
from io import StringIO, BytesIO

from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import split_every

from odoo import models, fields, api, _
from odoo.addons.shopify_ept import shopify
from odoo.addons.shopify_ept.shopify.pyactiveresource.connection import ClientError

_logger = logging.getLogger("Shopify")


class ShopifyProcessImportExport(models.TransientModel):
    _inherit = 'shopify.process.import.export'

    def import_customer_cron_action(self, ctx={}):
        instance_id = ctx.get('shopify_instance_id')
        instance = self.env['shopify.instance.ept'].browse(instance_id)
        customer_queues_ids = []

        instance.connect_in_shopify()
        if not instance.shopify_last_date_customer_import:
            customer_ids = shopify.Customer().find(limit=250)
        else:
            customer_ids = shopify.Customer().find(
                updated_at_min=instance.shopify_last_date_customer_import, limit=250)
        if customer_ids:
            customer_queues_ids = self.create_customer_data_queues_cron(customer_ids, instance)
            if len(customer_ids) == 250:
                customer_queues_ids += self.shopify_list_all_customer_cron(customer_ids, instance)

            instance.shopify_last_date_customer_import = datetime.now()
        if not customer_ids:
            _logger.info("Customers not found while the import customers from Shopify")
        else:
            if not ctx.get('is_auto_run_queue'):
                self.env['shopify.customer.data.queue.line.ept'].sync_shopify_customer_into_odoo()
        return

    def create_customer_data_queues_cron(self, customer_data, instance):
        """
        It creates customer data queue from data of Customer.
        @author: Maulik Barad on Date 09-Sep-2020.
        @param customer_data: Data of Customer.
        """
        customer_queue_list = []
        customer_data_queue_obj = self.env["shopify.customer.data.queue.ept"]
        customer_data_queue_line_obj = self.env["shopify.customer.data.queue.line.ept"]
        bus_bus_obj = self.env["bus.bus"]

        if len(customer_data) > 0:
            for customer_id_chunk in split_every(125, customer_data):
                customer_queue = customer_data_queue_obj.shopify_create_customer_queue(instance,
                                                                                       "import_process")
                customer_data_queue_line_obj.shopify_create_multi_queue(customer_queue, customer_id_chunk)

                message = "Customer Queue created {}".format(customer_queue.name)
                bus_bus_obj.sendone((self._cr.dbname, "res.partner", self.env.user.partner_id.id),
                                    {"type": "simple_notification", "title": "Shopify Notification",
                                     "message": message, "sticky": False, "warning": True})
                _logger.info(message)

                customer_queue_list.append(customer_queue.id)
            self._cr.commit()
        return customer_queue_list

    def shopify_list_all_customer_cron(self, result, instance):
        """
        This method used to call the page wise data import for customers from Shopify to Odoo.
        @param : self,result
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 14/10/2019.
        :Task ID: 157065
        Modify by Haresh Mori on date 26/12/2019, Taken Changes for the pagination and API version.
        """
        catch = ""
        customer_queue_list = []
        while result:
            page_info = ""
            link = shopify.ShopifyResource.connection.response.headers.get('Link')
            if not link or not isinstance(link, str):
                return customer_queue_list
            for page_link in link.split(','):
                if page_link.find('next') > 0:
                    page_info = page_link.split(';')[0].strip('<>').split('page_info=')[1]
                    try:
                        result = shopify.Customer().find(page_info=page_info, limit=250)
                    except ClientError as error:
                        if hasattr(error, "response"):
                            if error.response.code == 429 and error.response.msg == "Too Many Requests":
                                time.sleep(5)
                                result = shopify.Customer().find(page_info=page_info, limit=250)
                    except Exception as error:
                        raise UserError(error)
                    if result:
                        customer_queue_list += self.create_customer_data_queues_cron(result, instance)
            if catch == page_info:
                break
        return customer_queue_list
