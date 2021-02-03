# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging
import json
from datetime import datetime
from dateutil import parser


class StockPicking(models.Model):
    _inherit = "stock.picking"

    