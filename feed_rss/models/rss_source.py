# Copyright 2023
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import hashlib
from datetime import datetime

import feedparser

from odoo import _, fields, models


class RssSource(models.Model):
    _name = "rss.source"
    _description = "Rss source"
    _inherit = ["mail.thread", "mail.activity.mixin"]

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
            published_date = None
            if entry.published_parsed:
                published_date = datetime(*entry.published_parsed[:6])
            post_content = (
                f"{entry.get('title', '')}"
                f"{entry.get('link', '')}"
                f"{entry.get('summary', '')}"
            )
            content_hash = hashlib.md5(post_content.encode("utf-8")).hexdigest()
            rss_post_vals = {
                "post_id": entry.get("id", entry.get("link", None)),
                "title": entry.get("title", None),
                "link": entry.get("link", None),
                "description": entry.get("summary", None),
                "publish_date": published_date,
                "author": entry.get("author", None),
                "image_url": next(
                    (
                        link.href
                        for link in entry.get("links", [])
                        if link.get("rel") == "enclosure"
                    ),
                    None,
                ),
                "hash_md5": content_hash,
            }
            try:
                rss_post = self.env["rss.post"].search(
                    [("post_id", "=", rss_post_vals["post_id"])]
                )
                if rss_post and rss_post.hash_md5 != rss_post_vals["hash_md5"]:
                    rss_post.write(rss_post_vals)
                elif not rss_post:
                    self.env["rss.post"].create(rss_post_vals)
                self.message_post(
                    _(body="RSS feed imported successfully %s" % rss_post_vals["title"])
                )
            except Exception as e:
                self.message_post(
                    _(
                        body="Error importing RSS feed %s: %s"
                        % (rss_post_vals["title"], e)
                    )
                )

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
