# -*- coding: utf-8 -*-
"""
announcement.py
---------------
Dojo Announcement / Event record.

Mirrors the "Events and Announcements" feature of Spark Kiosk:
- Announcements are displayed on the kiosk / portal screen between check-ins.
- Each announcement has a title, body text, optional image, and a visibility
  window (date_start / date_end).
- Type selector: general, event, belt_test, promotion, closure, special_class.
- Audience filter: all, members_only, instructors_only, specific_course.
- Priority flag for pinned / urgent notices.
"""

from odoo import api, fields, models


class DojoAnnouncement(models.Model):
    _name = 'disaster.announcement'
    _description = 'Dojo Announcement / Event'
    _order = 'priority desc, date_start desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Title',
        required=True,
        tracking=True,
    )
    announcement_type = fields.Selection(
        selection=[
            ('general',       'General Notice'),
            ('event',         'Upcoming Event'),
            ('belt_test',     'Belt Test'),
            ('promotion',     'Promotion / Celebration'),
            ('closure',       'Dojo Closure'),
            ('special_class', 'Special Class'),
        ],
        string='Type',
        default='general',
        required=True,
        tracking=True,
    )
    body = fields.Html(
        string='Message',
        help='Full announcement text displayed on the kiosk / portal.',
    )
    summary = fields.Text(
        string='Short Summary',
        help='One-line teaser shown in the kiosk carousel.',
    )
    image = fields.Image(
        string='Image / Banner',
        max_width=1920,
        max_height=1080,
    )
    image_thumbnail = fields.Image(
        string='Thumbnail',
        related='image',
        max_width=300,
        max_height=200,
        store=True,
    )

    # ---- Visibility window ----------------------------------------
    date_start = fields.Datetime(
        string='Show From',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
        help='Display this announcement from this date/time.',
    )
    date_end = fields.Datetime(
        string='Show Until',
        tracking=True,
        help='Stop displaying after this date/time. Leave empty to show indefinitely.',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
    )

    # ---- Audience -------------------------------------------------
    audience = fields.Selection(
        selection=[
            ('all',              'Everyone'),
            ('members_only',     'Members Only'),
            ('instructors_only', 'Instructors Only'),
        ],
        string='Audience',
        default='all',
        required=True,
        tracking=True,
    )

    # ---- Priority / pin -------------------------------------------
    priority = fields.Selection(
        selection=[
            ('0', 'Normal'),
            ('1', 'Important'),
            ('2', 'Urgent'),
        ],
        string='Priority',
        default='0',
        tracking=True,
    )
    is_pinned = fields.Boolean(
        string='Pinned',
        default=False,
        tracking=True,
        help='Pinned announcements always appear first.',
    )

    # ---- Creator --------------------------------------------------
    author_id = fields.Many2one(
        comodel_name='res.partner',
        string='Posted By',
        default=lambda self: self.env.user.partner_id,
        tracking=True,
    )

    # ---- Computed -------------------------------------------------
    is_active_now = fields.Boolean(
        string='Currently Visible',
        compute='_compute_is_active_now',
        search='_search_is_active_now',
    )

    @api.depends('active', 'date_start', 'date_end')
    def _compute_is_active_now(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.active:
                rec.is_active_now = False
            elif rec.date_start and rec.date_start > now:
                rec.is_active_now = False
            elif rec.date_end and rec.date_end < now:
                rec.is_active_now = False
            else:
                rec.is_active_now = True

    def _search_is_active_now(self, operator, value):
        now = fields.Datetime.now()
        domain = [
            ('active', '=', True),
            ('date_start', '<=', now),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', now),
        ]
        if (operator == '=' and value) or (operator == '!=' and not value):
            return domain
        # negated
        return ['!'] + domain if len(domain) > 1 else [('active', '=', False)]

    # ---- SQL constraints ------------------------------------------
    _sql_constraints = [
        ('name_not_empty', "CHECK(name != '')", 'Announcement title cannot be empty.'),
    ]
