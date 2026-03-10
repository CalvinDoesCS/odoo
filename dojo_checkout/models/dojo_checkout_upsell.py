from odoo import fields, models


class DojoCheckoutUpsell(models.Model):
    """Optional add-on items shown during the checkout flow.

    Each upsell is linked to specific subscription plans via ``plan_ids``.
    When selected, it adds a line to the member's first invoice and creates
    a staff activity so the physical item can be processed.
    """

    _name = "dojo.checkout.upsell"
    _description = "Checkout Upsell Item"
    _order = "sequence, name"

    name = fields.Char(required=True)
    description = fields.Text(help="Brief description shown to members at checkout.")
    price = fields.Monetary(
        currency_field="currency_id",
        string="Price",
        required=True,
        default=0.0,
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )
    type = fields.Selection(
        [
            ("uniform", "Uniform / Gi"),
            ("merch", "Merchandise"),
            ("donation", "Donation"),
            ("other", "Other"),
        ],
        string="Type",
        default="other",
        required=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        help="Linked product used to generate the invoice line. If not set, a plain text line is used.",
    )
    image_1920 = fields.Image(max_width=1920, max_height=1920)
    image_128 = fields.Image(related="image_1920", max_width=128, max_height=128, store=True)
    plan_ids = fields.Many2many(
        "dojo.subscription.plan",
        "dojo_checkout_upsell_plan_rel",
        "upsell_id",
        "plan_id",
        string="Shown on Plans",
        help="Which subscription plan checkout pages display this upsell. Leave empty to show on all.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
