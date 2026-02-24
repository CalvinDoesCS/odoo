# -*- coding: utf-8 -*-
{
    'name': 'Dojo Contracts & Billing',
    'version': '19.0.2.0.0',
    'summary': 'Member contracts, hold/pause, delinquency, wallet/credits and dunning',
    'description': """
Dojo Contracts & Billing
========================
Extends disaster_member_belts contracts with:
- Hold / Pause state (hold_reason, hold_until)
- Past-due tracking (past_due_since)
- Billing day configuration
- Member Wallet (balance, store credits)
- Wallet transaction ledger (earn / spend / adjust / refund)
    """,
    'author': 'Custom Dev',
    'category': 'Membership',
    'license': 'LGPL-3',
    'application': True,
    'depends': ['disaster_member_belts'],
    'data': [
        'security/ir.model.access.csv',
        'views/dojo_wallet_views.xml',
        'views/member_contract_ext_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'auto_install': False,
}
