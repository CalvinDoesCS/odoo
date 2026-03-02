{
    'name': 'Dojo Sign & Waivers',
    'version': '19.0.1.0.0',
    'summary': 'Waiver collection via Odoo Sign + Documents storage for dojo members',
    'description': """
        Bridge module that integrates dojo_members with Odoo Sign (Enterprise) and
        optionally the Documents module.

        Features:
        - ``sign_template_id`` field on ``dojo.subscription.plan``: assign a Sign
          template per program.  When a new member is enrolled through the
          onboarding wizard, a Sign request is sent automatically and portal
          access is held until the waiver is signed.
        - ``waiver_request_id`` / ``has_signed_waiver`` fields on ``dojo.member``.
        - Daily cron that grants portal access to members whose waiver state
          transitions to ``signed``.
        - Signed documents are stored in a ``Waivers`` folder in the Documents app
          (requires the ``documents`` module).
        - Waiver status tab on the member form.
        - Waiver template field on the subscription plan form.
    """,
    'author': 'Dojo',
    'category': 'Dojo',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    # auto_install means Odoo will install this automatically when ALL listed
    # depends are installed.  Because 'sign' is Enterprise-only, this module
    # stays dormant on Community editions.
    'auto_install': True,
    'depends': [
        'dojo_onboarding',
        'sign',
    ],
    'data': [
        'data/ir_cron.xml',
        'views/dojo_member_waiver_views.xml',
        'views/dojo_subscription_plan_waiver_views.xml',
    ],
}
