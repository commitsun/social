# Copyright 2023
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from time import strftime

from odoo import fields, models, api
import feedparser

class RssSource(models.Model):
    _name = "rss.source"
    _description = "Rss source"

    id = fields.Char(
        string="ID",
        help="Source ID",
        required=True,
    )
    title = fields.Char(
        string="Title",
        help="Source title",
        required=True,
        translate=True,
    )

    source_url = fields.Char(
        string="Source URL",
        help="Source url"
    )
    rss_post_ids = fields.One2many(
        comodel_name="rss.post",
        inverse_name="rss_source_id",
        string="Posts",
        help="Posts",
    )

    def import_rss_feed(self):
        self.ensure_one()
        feed = feedparser.parse(self.source_url)

        for entry in feed.entries:
            pub_date_struct = entry.get('published_parsed')
            pub_date_str = strftime("%Y-%m-%d %H:%M:%S", pub_date_struct)
            if entry.get('id'):
                post = self.env["rss.post"].search([('post_id', '=', entry.get('id'))])
            if not post:
                rss_post_vals = {
                    'post_id': entry.get('id', ''),
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'description': entry.get('description', ''),
                    'publish_date': fields.Datetime.from_string(pub_date_str),
                    'author': entry.get('author', ''),
                    'rss_source_id': self.id,
                }
                self.env["rss.post"].create(rss_post_vals)


    def open_rss_posts(self):
        self.ensure_one()

        result = {
            'name': self.title,
            'view_mode': 'tree,form',
            'res_model': 'rss.post',
            'type': 'ir.actions.act_window',
            'domain': [('rss_source_id', '=', self.id)],
        }
        return result

