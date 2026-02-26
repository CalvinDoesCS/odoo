from odoo import fields, models


class DojoMember(models.Model):
    _inherit = "dojo.member"

    emergency_contact_ids = fields.One2many(
        "dojo.emergency.contact", "member_id", string="Emergency Contacts"
    )
