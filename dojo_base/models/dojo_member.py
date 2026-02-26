from odoo import api, fields, models


class DojoMember(models.Model):
    _name = "dojo.member"
    _description = "Dojo Member"
    _inherits = {"res.partner": "partner_id"}
    _inherit = ["mail.thread", "mail.activity.mixin"]

    partner_id = fields.Many2one("res.partner", required=True, ondelete="cascade")
    active = fields.Boolean(default=True)
    household_id = fields.Many2one("dojo.household", tracking=True, index=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    role = fields.Selection(
        [
            ("student", "Student"),
            ("parent", "Parent"),
            ("both", "Student & Parent"),
        ],
        default="student",
        required=True,
        tracking=True,
    )
    date_of_birth = fields.Date()
    emergency_note = fields.Text()
    guardian_for_link_ids = fields.One2many(
        "dojo.guardian.link", "guardian_member_id", string="Guardian Of"
    )
    dependent_link_ids = fields.One2many(
        "dojo.guardian.link", "student_member_id", string="Dependents"
    )
    user_ids = fields.One2many("res.users", "partner_id", string="Linked Users")
    has_portal_login = fields.Boolean(compute="_compute_has_portal_login")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("partner_id"):
                partner_vals = {}
                for field_name in ("name", "email", "phone", "mobile", "company_id"):
                    if field_name in vals:
                        partner_vals[field_name] = vals.pop(field_name)
                if not partner_vals.get("name"):
                    partner_vals["name"] = "New Member"
                partner = self.env["res.partner"].create(partner_vals)
                vals["partner_id"] = partner.id
        return super().create(vals_list)

    def _compute_has_portal_login(self):
        portal_group = self.env.ref("base.group_portal")
        for member in self:
            member.has_portal_login = any(
                portal_group in user.group_ids for user in member.user_ids
            )
