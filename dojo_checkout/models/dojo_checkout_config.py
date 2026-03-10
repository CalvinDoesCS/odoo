from odoo import fields, models


class DojoCheckoutConfig(models.Model):
    """Per-plan checkout page configuration.

    Controls the appearance of the public plan detail page and which upsells
    are offered. One record per subscription plan (unique constraint).
    """

    _name = "dojo.checkout.config"
    _description = "Checkout Page Configuration"
    _rec_name = "plan_id"

    plan_id = fields.Many2one(
        "dojo.subscription.plan",
        required=True,
        index=True,
        ondelete="cascade",
    )
    featured = fields.Boolean(
        default=False,
        help="Highlight this plan in the gallery with a 'Featured' badge.",
    )
    cta_label = fields.Char(
        string="Button Label",
        default="Join Now",
        help="Text for the call-to-action button on the plan card.",
    )
    banner_text = fields.Char(
        string="Banner Text",
        help="Short promo text displayed above the plan card (e.g. 'Best Value!').",
    )
    hero_image_1920 = fields.Image(
        string="Hero Image",
        max_width=1920,
        max_height=1920,
        help="Large banner image shown on the plan detail page.",
    )
    thank_you_html = fields.Html(
        string="Thank You Message",
        help="HTML shown on the confirmation page after a successful checkout.",
        sanitize=True,
    )
    upsell_ids = fields.Many2many(
        "dojo.checkout.upsell",
        "dojo_checkout_config_upsell_rel",
        "config_id",
        "upsell_id",
        string="Upsell Items",
        help="Add-on items offered during checkout for this plan.",
    )

    _dojo_checkout_config_plan_unique = models.Constraint(
        "unique(plan_id)",
        "A checkout config already exists for this plan.",
    )
