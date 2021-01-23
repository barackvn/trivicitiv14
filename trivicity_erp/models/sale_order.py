# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging
import json
from datetime import datetime
from dateutil import parser
from odoo.addons.shopify_ept import shopify

_logger = logging.getLogger("Shopify")


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

    def prepare_shopify_customer_and_addresses(self, order_response, pos_order, instance, order_data_line, log_book):
        """
        Searches for existing customer in Odoo and creates in odoo, if not found.
        if not found shipping or invoice address
        @author: Maulik Barad on Date 11-Sep-2020.
        """
        partner, delivery_address, invoice_address = super(SaleOrder, self).prepare_shopify_customer_and_addresses(order_response, pos_order, instance, order_data_line, log_book)
        if partner and not (delivery_address or invoice_address):
            message = "Customer's Shipping or invoice details are not available in %s Order." % (
                order_response.get("order_number"))
            self.create_shopify_log_line(message, order_data_line, log_book, order_response.get("name"))
            _logger.info(message)
            return partner, False, False
        return partner, delivery_address, invoice_address

    def import_shopify_orders(self, order_data_lines, log_book, is_queue_line=True):
        """
        This method used to create a sale orders in Odoo.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 11/11/2019.
        Task Id : 157350
        @change: By Maulik Barad on Date 21-Sep-2020.
        """
        order_risk_obj = self.env["shopify.order.risk"]

        order_ids = []
        commit_count = 0
        instance = log_book.shopify_instance_id

        instance.connect_in_shopify()

        for order_data_line in order_data_lines:
            commit_count += 1
            if commit_count == 5:
                self._cr.commit()
                commit_count = 0
            if is_queue_line:
                order_data = order_data_line.order_data
                order_response = json.loads(order_data)
            else:
                if not isinstance(order_data_line, dict):
                    order_response = order_data_line.to_dict()
                else:
                    order_response = order_data_line
                order_data_line = False

            order_number = order_response.get("order_number")
            _logger.info("Started processing Shopify order(%s) and order id is(%s)"
                         % (order_number, order_response.get("id")))
            sale_order = self.search([("shopify_order_id", "=", order_response.get("id")),
                                      ("shopify_instance_id", "=", instance.id),
                                      ("shopify_order_number", "=", order_number)])
            if not sale_order:
                sale_order = self.search([("shopify_instance_id", "=", instance.id),
                                          ("client_order_ref", "=", order_response.get("name"))])

            if sale_order:
                if order_data_line:
                    order_data_line.write({"state": "done", "processed_at": datetime.now(),
                                           "sale_order_id": sale_order.id})
                    self._cr.commit()
                _logger.info("Done the Process of order Because Shopify Order(%s) is exist in Odoo and "
                             "Odoo order is(%s)" % (order_number, sale_order.name))
                continue

            pos_order = True if order_response.get("source_name", "") == "pos" else False
            partner, delivery_address, invoice_address = self.prepare_shopify_customer_and_addresses(
                order_response, pos_order, instance, order_data_line, log_book)
            if not partner or not delivery_address or not invoice_address:
                continue

            lines = order_response.get("line_items")
            if self.check_mismatch_details(lines, instance, order_number, order_data_line, log_book):
                _logger.info("Mismatch details found in this Shopify Order(%s) and id (%s)" % (
                    order_number, order_response.get("id")))
                if order_data_line:
                    order_data_line.write({"state": "failed", "processed_at": datetime.now()})
                continue

            sale_order = self.shopify_create_order(instance, partner, delivery_address, invoice_address,
                                                   order_data_line, order_response, log_book)
            if not sale_order:
                message = "Configuration missing in Odoo while importing Shopify Order(%s) and id (%s)" % (
                    order_number, order_response.get("id"))
                _logger.info(message)
                self.create_shopify_log_line(message, order_data_line, log_book, order_response.get("name"))
                continue
            order_ids.append(sale_order.id)

            location_vals = self.set_shopify_location_and_warehouse(order_response, instance, pos_order)
            sale_order.write(location_vals)

            risk_result = shopify.OrderRisk().find(order_id=order_response.get("id"))
            if risk_result:
                order_risk_obj.shopify_create_risk_in_order(risk_result, sale_order)
                risk = sale_order.risk_ids.filtered(lambda x: x.recommendation != "accept")
                if risk:
                    sale_order.is_risky_order = True

            _logger.info("Creating order lines for Odoo order(%s) and Shopify order is (%s)." % (
                sale_order.name, order_number))
            sale_order.create_shopify_order_lines(lines, order_response, instance)

            _logger.info("Created order lines for Odoo order(%s) and Shopify order is (%s)"
                         % (sale_order.name, order_number))

            sale_order.create_shopify_shipping_lines(order_response, instance)
            _logger.info("Created Shipping lines for order (%s)." % sale_order.name)

            _logger.info("Starting auto workflow process for Odoo order(%s) and Shopify order is (%s)"
                         % (sale_order.name, order_number))

            if not sale_order.is_risky_order:
                if sale_order.shopify_order_status == "fulfilled":
                    sale_order.auto_workflow_process_id.shipped_order_workflow_ept(sale_order)
                else:
                    sale_order.process_orders_and_invoices_ept()

            _logger.info("Done auto workflow process for Odoo order(%s) and Shopify order is (%s)"
                         % (sale_order.name, order_number))

            if order_data_line:
                order_data_line.write({"state": "done", "processed_at": datetime.now(),
                                       "sale_order_id": sale_order.id})
            _logger.info("Processed the Odoo Order %s process and Shopify Order (%s)"
                         % (sale_order.name, order_number))

        return order_ids
