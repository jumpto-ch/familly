from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta

class FamillyBudget(models.Model):
    _name = "familly.budget"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Budget Familial"

    name = fields.Char(required=True)
    version = fields.Char(default="1.0")

    date_start = fields.Date(required=True)
    date_end = fields.Date()

    frequency = fields.Selection([
        ('week', 'Weekly'),
        ('month', 'Monthly'),
        ('year', 'Yearly')
    ], required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
    ], default='draft')
    active = fields.Boolean('Active', default=True)
    next_execution_date = fields.Date(
        string="Next Execution Date",
        help="Date on which the next budget entry should be generated.",
    )

    income_line_ids = fields.One2many('familly.budget.line', 'budget_id', copy=True,
                                       domain=[('type', '=', 'income')], context={'default_type': 'income'})
    expense_line_ids = fields.One2many('familly.budget.line', 'budget_id', copy=True,
                                      domain=[('type', '=', 'expense')], context={'default_type': 'expense'})

    total_incomes = fields.Monetary(compute="_compute_totals")
    total_expenses = fields.Monetary(compute="_compute_totals")
    balanced = fields.Boolean(compute="_compute_totals")

    currency_id = fields.Many2one('res.currency', string='Currency',
                                  related="company_id.currency_id")
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company
    )

    @api.depends('income_line_ids.amount', 'expense_line_ids.amount')
    def _compute_totals(self):
        for rec in self:
            rec.total_incomes = sum(rec.income_line_ids.mapped('amount'))
            rec.total_expenses = sum(rec.expense_line_ids.mapped('amount'))
            rec.balanced = rec.total_incomes == rec.total_expenses

    def _group_lines_by_section(self, lines):
        """Group ordered budget lines by section.

        Returns a list of dicts: {'name': <section title or False>,
        'lines': <recordset of real lines>, 'subtotal': <sum of amounts>}.
        Lines appearing before the first section are grouped under a
        section with no name.
        """
        self.ensure_one()
        groups = []
        current = {'name': False, 'lines': self.env['familly.budget.line'], 'subtotal': 0.0}
        for line in lines.sorted(key=lambda l: (l.sequence, l.id)):
            if line.display_type == 'line_section':
                if current['lines'] or current['name']:
                    groups.append(current)
                current = {'name': line.name, 'lines': self.env['familly.budget.line'], 'subtotal': 0.0}
            else:
                current['lines'] |= line
                current['subtotal'] += line.amount
        if current['lines'] or current['name']:
            groups.append(current)
        return groups

    def action_confirm(self):
        for budget in self:
            if not budget.balanced:
                raise ValidationError(_("Budget not balanced! Revenue must equal expenses."))

            # Un seul budget actif par société
            other_active = self.search(
                [
                    ("id", "!=", budget.id),
                    ("state", "=", "active"),
                    ("company_id", "=", budget.company_id.id),
                ],
                limit=1,
            )
            if other_active:
                raise ValidationError(
                        _("There is already an active budget for this company: '%s'. "
                          "You must archive it before activating a new one.")% other_active.name
                )

            # Initialiser la prochaine date d'exécution
            base_date = budget.date_start or fields.Date.today()
            budget.next_execution_date = budget._compute_first_period_date(base_date)

            budget.state = "active"

    def action_set_draft(self):
        self.write({"state": "draft"})

    def _compute_first_period_date(self, ref_date):
        """Return ref_date if it is the first day of the current period, otherwise return the next period start."""
        self.ensure_one()

        # ----------------------------
        # WEEK → Monday = first day
        # ----------------------------
        if self.frequency == "week":
            monday = ref_date - relativedelta(days=ref_date.weekday())  # Monday of same week
            if ref_date == monday:
                return ref_date  # already first day
            return monday + relativedelta(weeks=1)  # next Monday

        # ----------------------------
        # MONTH → 1st day of month
        # ----------------------------
        if self.frequency == "month":
            first_day = ref_date.replace(day=1)
            if ref_date == first_day:
                return ref_date  # already first day
            # Next 1st day of month
            next_month = ref_date + relativedelta(months=1)
            return next_month.replace(day=1)

        # ----------------------------
        # YEAR → 1st January
        # ----------------------------
        if self.frequency == "year":
            first_day = ref_date.replace(month=1, day=1)
            if ref_date == first_day:
                return ref_date  # already first day
            # Next 1st January
            next_year = ref_date + relativedelta(years=1)
            return next_year.replace(month=1, day=1)

        return ref_date

    def _get_next_period_date(self, current_date):
        self.ensure_one()

        if self.frequency == "week":
            next_date = current_date + relativedelta(weeks=1)
        elif self.frequency == "month":
            next_date = current_date + relativedelta(months=1)
        elif self.frequency == "year":
            next_date = current_date + relativedelta(years=1)
        else:
            return current_date

        return self._compute_first_period_date(next_date)

    @api.model
    def _cron_generate_budget_moves(self):
        today = fields.Date.today()
        budgets = self.search(
            [
                ("state", "=", "active"),
                ("company_id", "=", self.env.company.id),
            ]
        )
        for budget in budgets:
            if not budget.next_execution_date:
                continue

            # Respect de la période du budget
            if budget.date_start and today < budget.date_start:
                continue
            if budget.date_end and today > budget.date_end:
                continue

            # Si plusieurs périodes sont "en retard", on boucle
            while budget.next_execution_date and budget.next_execution_date <= today:
                budget._generate_budget_move(budget.next_execution_date)
                budget.next_execution_date = budget._get_next_period_date(
                    budget.next_execution_date
                )

    def _generate_budget_move(self, move_date):
        """Créer une opération diverse dans le journal Budget pour la date donnée."""
        self.ensure_one()
        today = fields.Date.today()

        journal = self.env.ref('family_budget.journal_budget')

        move_vals = {
            "ref": _("Budget %s - %s") % (self.name, move_date),
            "date": move_date,
            "journal_id": journal.id,
            "company_id": self.company_id.id,
            "move_type": "entry",
            "line_ids": [],
        }

        line_commands = []
        total_debit = 0.0
        total_credit = 0.0

        for line in self.income_line_ids:
            if not line.account_id:
                continue

            amount = line.amount
            if amount <= 0.0:
                continue

            line_commands.append(
                (
                    0,
                    0,
                    {
                        "name": line.name or self.name,
                        "account_id": line.account_id.id,
                        "credit": amount,
                        "debit": 0.0,
                    },
                )
            )
            total_credit += amount
        for line in self.expense_line_ids:
            if not line.account_id:
                continue

            amount = line.amount
            if amount <= 0.0:
                continue

            # Charges : débit du compte de charge
            line_commands.append(
                (
                    0,
                    0,
                    {
                        "name": line.name or self.name,
                        "account_id": line.account_id.id,
                        "debit": amount,
                        "credit": 0.0,
                    },
                )
            )
            total_debit += amount

        if not line_commands:
            return  # rien à générer

        move_vals["line_ids"] = line_commands
        move = self.env["account.move"].create(move_vals)
        move.action_post()

