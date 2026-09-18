{
    "name": "Familly Budget",
    "version": "17.0.1.0.0",
    "category": "Accounting",
    "summary": "Manage family budgets with incomes, expenses and automatic journal entries",
    "description": """
Familly Budget

This module allows you to:
- Create and manage budgets
- Define income and expense accounts with planned amounts
- Validate that the budget is balanced
- Automatically generate journal entries based on a schedule

States:
Draft -> Active 

Features:
- Only one active budget allowed at a time
- Automatic posting into a specific "Budget" journal
- Periodicity: Weekly, Monthly, Yearly
""",
    "author": "JumpTo",
    "website": "https://github.com/jumpto-ch/familly",
    "license": "LGPL-3",
    "depends": [
        "base",
        "account",
        "account_reconcile_oca",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/journal.xml",
        "data/budget_cron.xml",
        "report/budget_report.xml",
        "views/budget_view.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False
}
