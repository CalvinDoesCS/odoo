from odoo import fields, models


class DojoClassTemplate(models.Model):
    _inherit = 'dojo.class.template'

    # Reverse side of the plan ↔ template M2M — read-only informational field.
    allowed_plan_ids = fields.Many2many(
        'dojo.subscription.plan',
        'dojo_sub_plan_template_rel',
        'template_id',
        'plan_id',
        string='Subscription Plans',
        readonly=True,
        help='Course-Based plans that include this class. Managed on each plan.',
    )
