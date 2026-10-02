
from odoo import fields, models, api, _
import re

class AccountStatementImportCamtParser(models.AbstractModel):
    _inherit = "account.statement.import.camt.parser"

    def parse_statement(self,  ns, node):
        result = super().parse_statement(ns, node)

        # Use custom statement_name to find partners in narration
        def _find_matching_partner(search_string):
            search = (search_string or '').lower()
            for p in self.env['res.partner'].search([]):
                criteria = (p.statement_name or p.name or '').lower()
                if criteria and criteria in search:
                    return p
            return None

        # Change the partner_id of specific bank and partner combinations
        # to find one more specific partner based on the narration
        bank_filter = ['BCJUCH22XXX']
        # Each entry is a list of name parts where ALL MUST be present in the partner name
        # each name part can have multiple possible solutions, only ONE needs to match
        # ex: Eicher Stéphane / Stephane Eicher will match
        # ( list_of_partners/any: (list_of_conditions/all: (list_of_possible_solutions_in_name/any: Stephan, Steph ) )
        partner_list_filter = [
            (
                ('Stéphane', 'Stephane', 'Steph'),
                ('Eicher')
            ),
            (
                ('Alyssia'),
                ('Eicher', 'Broquet')
            )]
        bank_node = node.xpath("./ns:Acct/ns:Svcr/ns:FinInstnId/ns:BICFI", namespaces={"ns": ns})
        # Pattern could be RmtInf/Ustrd - AddtlTxInf - AddtlNtryInf - Refs/InstrId
        new_fields_pattern = ["AddtlNtryInf"]

        for transaction in result['transactions']:
            if 'partner_name' in transaction.keys() and 'partner_id' not in transaction.keys():
                # reset variables
                filtered_partner = None
                partner_in_filter = False

                # FILTER bank_filter
                bank_in_filter = bank_node and bank_node[0].text in bank_filter

                # search partner in partner_name
                partner = _find_matching_partner(transaction['partner_name'])
                # no partner found
                # we flag it to find a more specific one in narration later
                no_partner_found = transaction['partner_name'] == 'NOTPROVIDED' or not partner

                if partner:
                    partner_name = partner.statement_name if partner.statement_name else partner.name
                    # FILTER partner_list_filter
                    # partner_list_filter contain the list of partner which need to be more specific
                    # we flag it to find a more specific one in narration later
                    partner_in_filter = (
                        any(all(any(solution in partner_name for solution in condition)
                                for condition in partner_filter) for partner_filter in partner_list_filter))
                    if not partner_in_filter:
                        # a partner is found but is not in filter, use it
                        transaction['partner_id'] = partner.id

                # if we found the target bank and a more specific partner is needed
                if bank_in_filter and (no_partner_found or partner_in_filter):
                    # try to find specific field in narration
                    # FILTER new_fields_pattern
                    for new_field_pattern in new_fields_pattern:
                        match = re.search(rf'\({new_field_pattern}\):([^\n]*)',
                                          transaction['narration'])

                        # if field exist in narration, try to find matching partner
                        research_string = match.group(1).strip() if match else ''
                        filtered_partner = _find_matching_partner(research_string)
                        # if more specific partner found, stop searching
                        if filtered_partner:
                            transaction['partner_id'] = filtered_partner.id
                            break
                    # partner in filter but no more specific partner found, remove partner
                    if not filtered_partner:
                        transaction['partner_id'] = False

        return result
