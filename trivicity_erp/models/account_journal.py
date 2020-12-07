# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def get_journal_dashboard_datas(self):
        domain_checks_to_print = [
            ('journal_id', '=', self.id),
            ('payment_method_id.code', '=', 'check_printing'),
            ('state', '=', 'posted'),
            ('check_number', '=', False)
        ]
        res = super(AccountJournal, self).get_journal_dashboard_datas() or {}
        res['num_checks_to_print'] = self.env['account.payment'].search_count(domain_checks_to_print)
        return res
