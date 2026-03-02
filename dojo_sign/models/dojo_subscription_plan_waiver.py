from odoo import fields, models


class DojoSubscriptionPlan(models.Model):
    """Extends dojo.subscription.plan with an optional Odoo Sign waiver template."""

    _inherit = "dojo.subscription.plan"

    sign_template_id = fields.Many2one(
        "sign.template",
        string="Waiver Template",
        ondelete="set null",
        help=(
            "Odoo Sign template to send to new members when they enrol in this plan. "
            "Leave blank if no waiver is required.  When set, the member must sign the "
            "waiver before portal access is granted."
        ),
    )
