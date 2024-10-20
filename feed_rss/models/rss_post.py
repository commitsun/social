# Copyright 2023
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class RssPost(models.Model):
    _name = "rss.post"
    _description = "Post item"

    post_id = fields.Char(
        string="ID",
        help="Post ID",
        required=True,
    )

    title = fields.Char(
        string="Title",
        help="Post title",
        required=True,
        translate=True,
    )

    link = fields.Char(string="Link", help="Post link")

    description = fields.Text(
        string="Description",
        help="Post description",
        translate=True,
    )
    publish_date = fields.Datetime(string="Date", help="Post date")
    author = fields.Char(string="Author", help="Post author")
    image_url = fields.Char(string="Image URL", help="Post image URL")
    rss_source_id = fields.Many2one(
        comodel_name="rss.source",
        string="Source",
        help="Source",
    )
    hash_md5 = fields.Char(
        string="MD5",
        help="MD5 hash",
    )
