# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import logging
from odoo import models, fields, api

_logger = logging.getLogger("Shopify")


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_shopify_customer = fields.Boolean(string="Is Shopify Customer?", default=False,
                                         help="Used for identified that the customer is imported from Shopify store.")

    @api.model
    def create_shopify_pos_customer(self, order_response, instance):
        """
        Creates customer from POS Order.
        @author: Maulik Barad on Date 27-Feb-2020.
        """
        shopify_partner_obj = self.env["shopify.res.partner.ept"]
        customer_data = order_response.get("customer")

        address = customer_data.get("default_address") or {}
        customer_id = customer_data.get("id")
        first_name = customer_data.get("first_name") or ''
        last_name = customer_data.get("last_name") or ''
        phone = customer_data.get("phone")
        email = customer_data.get("email")

        shopify_partner = shopify_partner_obj.search([("shopify_customer_id", "=", customer_id),
                                                      ("shopify_instance_id", "=", instance.id)],
                                                     limit=1)
        name = f"{first_name} {last_name}".strip()
        if name == "":
            if email:
                name = email
            elif phone:
                name = phone
        partner_vals = {
            "name": name,
            "phone": phone,
            "email": email,
        }

        if address.get("city"):
            state_name = address.get("province")

            country = self.get_country(address.get("country") or address.get("country_code"))
            state = (
                self.env["res.country.state"].search(
                    [
                        "|",
                        ("code", "=", address.get("province_code")),
                        ("name", "=", state_name),
                        ("country_id", "=", country.id),
                    ],
                    limit=1,
                )
                if country
                else self.env["res.country.state"].search(
                    [
                        "|",
                        ("code", "=", address.get("province_code")),
                        ("name", "=", state_name),
                    ],
                    limit=1,
                )
            )
            partner_vals |= {
                "street": address.get("address1"),
                "street2": address.get("address2"),
                "city": address.get("city"),
                "state_id": state.id or False,
                "country_id": country.id or False,
                "zip": address.get("zip"),
            }

        if shopify_partner:
            parent_id = shopify_partner.partner_id.id
            partner_vals.update(parent_id=parent_id)
            key_list = list(partner_vals.keys())
            res_partner = self._find_partner_ept(partner_vals, key_list, [])
            if not res_partner:
                del partner_vals["parent_id"]
                key_list = list(partner_vals.keys())
                res_partner = self._find_partner_ept(partner_vals, key_list, [])
            if not res_partner:
                partner_vals |= {
                    'is_company': False,
                    'type': 'invoice',
                    'customer_rank': 0,
                    'is_shopify_customer': True,
                }
                res_partner = self.create(partner_vals)
            return res_partner

        res_partner = self
        if email:
            res_partner = self.search([("email", "=", email)], limit=1)
        if not res_partner and phone:
            res_partner = self.search([("phone", "=", phone)], limit=1)
        if res_partner and res_partner.parent_id:
            res_partner = res_partner.parent_id

        if res_partner:
            partner_vals |= {
                "is_shopify_customer": True,
                "type": "invoice",
                "parent_id": res_partner.id,
            }
            res_partner = self.create(partner_vals)
        else:
            key_list = list(partner_vals.keys())
            res_partner = self._find_partner_ept(partner_vals, key_list, [])
            if res_partner:
                res_partner.write({"is_shopify_customer": True})
            else:
                partner_vals |= {"is_shopify_customer": True, "type": "contact"}
                res_partner = self.create(partner_vals)

        shopify_partner_obj.create({"shopify_instance_id": instance.id,
                                    "shopify_customer_id": customer_id,
                                    "partner_id": res_partner.id})
        return res_partner
