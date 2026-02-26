from odoo import fields, models


class DojoHousehold(models.Model):
    _name = "dojo.household"
    _description = "Dojo Household"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    primary_guardian_partner_id = fields.Many2one(
        "res.partner", string="Primary Guardian", tracking=True
    )
    member_ids = fields.One2many("dojo.member", "household_id", string="Members")
    guardian_link_ids = fields.One2many(
        "dojo.guardian.link", "household_id", string="Guardian Links"
    )
    note = fields.Text()
