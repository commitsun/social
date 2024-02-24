# Copyright 2023
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import re
from time import strftime

import feedparser

from odoo import fields, models


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

    source_url = fields.Char(string="Source URL", help="Source url")
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
            pub_date_struct = entry.get("published_parsed")
            pub_date_str = strftime("%Y-%m-%d %H:%M:%S", pub_date_struct)
            if entry.get("id"):
                post = self.env["rss.post"].search([("post_id", "=", entry.get("id"))])
            if not post:
                rss_post_vals = {
                    "post_id": entry.get("id", ""),
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "description": entry.get("description", ""),
                    "publish_date": fields.Datetime.from_string(pub_date_str),
                    "author": entry.get("author", ""),
                    "image_url": self.get_image_url(entry),
                    "rss_source_id": self.id,
                }
                self.env["rss.post"].create(rss_post_vals)

    def get_clean_description(self, entry):
        img_pattern = r"<img[^>]+>"
        clean_description = re.sub(img_pattern, "", entry.get("description"))
        return clean_description

    def get_image_url(self, entry):
        img_pattern = r"<img[^>]+>"
        if entry.get("image") and entry.get("image").get("href"):
            return entry.get("image").get("href")
        elif entry.get("media_content") and entry.get("media_content")[0].get("url"):
            return entry.get("media_content")[0].get("url")
        else:
            img_tag = re.search(img_pattern, entry.get("description"))
            if img_tag:
                img_url = re.search(r'src="([^"]+)"', img_tag.group(0))
                return img_url.group(1)
        return False

    def open_rss_posts(self):
        self.ensure_one()

        result = {
            "name": self.title,
            "view_mode": "tree,form",
            "res_model": "rss.post",
            "type": "ir.actions.act_window",
            "domain": [("rss_source_id", "=", self.id)],
        }
        return result
