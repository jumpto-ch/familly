# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class FamillyBudgetLine(models.Model):
    _name = "familly.budget.line"
    _description = "Budget Line"
    _order = "sequence, id"

    budget_id = fields.Many2one('familly.budget', string='Budget', required=True, ondelete='cascade')
    account_id = fields.Many2one('account.account', string='Account')
    company_id = fields.Many2one(
        'res.company', string='company',
        default=lambda self: self.env.company
    )
    amount = fields.Float()
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Label')
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Company Currency",
        readonly=True,
        store=True
    )

    type = fields.Selection([
        ('income', 'Income'),
        ('expense', 'Expense')
    ], required=True)

    display_type = fields.Selection([
        ('line_section', 'Section'),
    ], default=False, help="Technical field for UI purposes (sections).")

    @api.constrains('display_type', 'account_id')
    def _check_account(self):
        for line in self:
            if not line.display_type and not line.account_id:
                raise ValidationError(_("A budget line must have an account."))

    @api.onchange('display_type')
    def _onchange_display_type(self):
        if self.display_type:
            self.account_id = False
            self.amount = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('display_type'):
                vals['account_id'] = False
                vals['amount'] = 0.0
        return super().create(vals_list)
