import logging
import re

from odoo import models

_logger = logging.getLogger(__name__)

class AccountBankStatementLine(models.Model):
    _inherit = ("account.bank.statement.line",)

    def create(self, vals):
        # si vals n'est pas une liste transformer en liste
        vals = [vals] if not isinstance(vals, list) else vals
        new_vals = []
        for val in vals:
            if 'payment_ref' not in val.keys() or val['payment_ref'] == '/':

                if 'narration' in val.keys() and 'Additional Entry Information (AddtlNtryInf):' in val['narration']:
                    match = re.search(r'Additional Entry Information \(AddtlNtryInf\):([^\n]*)', val['narration'])
                    if match:
                        val['payment_ref'] = match.group(1).strip()

            if 'partner_name' in val.keys() and 'partner_id' not in val.keys():
                state_line_ref = (val.get('partner_name') or '').lower()
                for partner in self.env['res.partner'].search([]):
                    #_logger.debug("partner id: %s", partner.id)
                    statement_name = (partner.statement_name or partner.name or '').lower()

                    if statement_name and statement_name in state_line_ref:
                        val['partner_id'] = partner.id
                        break

            if 'partner_id' not in val.keys() and 'partner_name' not in val.keys():
                state_line_ref = (val.get('payment_ref') or '').lower()
                for partner in self.env['res.partner'].search([]):
                    #_logger.debug("partner id: %s", partner.id)
                    statement_name = (partner.statement_name or partner.name or '').lower()

                    if statement_name and statement_name in state_line_ref:
                        val['partner_id'] = partner.id
                        break

            new_vals.append(val)

        res = super().create(new_vals)
        return res
