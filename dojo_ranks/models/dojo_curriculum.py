# -*- coding: utf-8 -*-
"""
dojo_curriculum.py
------------------
Curriculum content library + rank-to-content mapping.

Models
------
  dojo.curriculum.tag      – tag cloud for content items
  dojo.curriculum.content  – a single learning resource (video, doc, link, image)
  dojo.rank.curriculum     – ordered many2many-with-extra-fields between
                             belt rank and content item
"""

from odoo import fields, models


class DojoCurriculumTag(models.Model):
    _name = 'dojo.curriculum.tag'
    _description = 'Curriculum Content Tag'
    _order = 'name'

    name = fields.Char(required=True)
    color = fields.Integer(string='Color Index', default=0)

    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Tag name must be unique.'),
    ]


class DojoCurriculumContent(models.Model):
    _name = 'dojo.curriculum.content'
    _description = 'Curriculum Content Item'
    _order = 'sequence, name'

    name = fields.Char(string='Title', required=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        'res.company', string='Dojo',
        default=lambda self: self.env.company,
    )
    content_type = fields.Selection([
        ('video',    'Video'),
        ('doc',      'Document / PDF'),
        ('link',     'External Link'),
        ('image',    'Image'),
    ], string='Type', required=True, default='doc')

    attachment_id = fields.Many2one(
        'ir.attachment', string='Attached File', ondelete='set null',
    )
    url = fields.Char(string='URL / Embed Link')
    description = fields.Text(string='Description')
    visibility = fields.Selection([
        ('member',  'Members'),
        ('staff',   'Staff Only'),
        ('private', 'Private'),
    ], string='Visibility', default='member', required=True)

    tag_ids = fields.Many2many(
        'dojo.curriculum.tag', string='Tags',
        relation='dojo_content_tag_rel', column1='content_id', column2='tag_id',
    )
    active = fields.Boolean(default=True)

    rank_curriculum_ids = fields.One2many(
        'dojo.rank.curriculum', 'content_id', string='Used in Ranks',
    )


class DojoRankCurriculum(models.Model):
    _name = 'dojo.rank.curriculum'
    _description = 'Rank Curriculum Line'
    _order = 'belt_rank_id, sequence'

    belt_rank_id = fields.Many2one(
        'disaster.belt.rank.config', string='Belt Rank',
        required=True, ondelete='cascade', index=True,
    )
    content_id = fields.Many2one(
        'dojo.curriculum.content', string='Content',
        required=True, ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    required_for_promotion = fields.Boolean(
        string='Required for Promotion', default=False,
    )
