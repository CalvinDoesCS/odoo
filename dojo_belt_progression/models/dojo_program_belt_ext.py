from odoo import fields, models


class DojoProgramBeltExt(models.Model):
    _inherit = "dojo.program"

    belt_rank_ids = fields.Many2many(
        "dojo.belt.rank",
        "dojo_program_belt_rank_rel",
        "program_id",
        "rank_id",
        string="Belt Path",
        help="Ordered belt ranks for this program's progression.",
    )
