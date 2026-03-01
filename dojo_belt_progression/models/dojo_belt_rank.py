from odoo import fields, models


class DojoBeltRank(models.Model):
    _name = "dojo.belt.rank"
    _description = "Dojo Belt Rank"
    _order = "sequence, name"

    name = fields.Char(required=True, string="Rank Name")
    sequence = fields.Integer(default=10, help="Lower = beginner, Higher = advanced")
    color = fields.Char(
        string="Belt Colour",
        help="CSS colour name or hex (e.g. 'white', '#FFD700')",
        default="#ffffff",
    )
    description = fields.Text()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )

    # Reverse links
    member_rank_ids = fields.One2many(
        "dojo.member.rank", "rank_id", string="Awarded To"
    )
