# Copyright 2023
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import hashlib
import re
from datetime import datetime

import feedparser

from odoo import _, fields, models

# Patrones para extraer la imagen y el titular del HTML del cuerpo del item
# (content:encoded o description). Necesario para feeds que no exponen un
# <enclosure> para la imagen ni un <title> descriptivo (p. ej. Mintlify, que
# pone la portada y el titular dentro del HTML del contenido).
IMG_SRC_RE = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.IGNORECASE)
HEADING_RE = re.compile(r"<h[12][^>]*>(.*?)</h[12]>", re.IGNORECASE | re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]+>")


class RssSource(models.Model):
    _name = "rss.source"
    _description = "Rss source"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    id = fields.Char(
        help="Source ID",
        required=True,
    )
    title = fields.Char(
        help="Source title",
        required=True,
        translate=True,
    )
    source_url = fields.Char(
        help="Url of the RSS feed",
        required=True,
    )
    rss_post_ids = fields.One2many(
        comodel_name="rss.post",
        inverse_name="rss_source_id",
        string="Posts",
        help="Posts",
    )

    @staticmethod
    def _entry_body_html(entry):
        """HTML del cuerpo del item (content:encoded si existe, si no description)."""
        contents = entry.get("content")
        if contents:
            return contents[0].get("value") or ""
        return entry.get("summary") or ""

    def _extract_image_url(self, entry):
        """Imagen del item: <enclosure> -> media:* -> primera <img> del cuerpo."""
        enclosure = next(
            (
                link.href
                for link in entry.get("links", [])
                if link.get("rel") == "enclosure"
            ),
            None,
        )
        if enclosure:
            return enclosure
        for media_key in ("media_content", "media_thumbnail"):
            media = entry.get(media_key)
            if media and media[0].get("url"):
                return media[0]["url"]
        match = IMG_SRC_RE.search(self._entry_body_html(entry))
        return match.group(1) if match else None

    def _extract_title(self, entry):
        """Titular del item. Algunos feeds (Mintlify) ponen la fecha en <title> y
        el titular real en un encabezado del cuerpo; en ese caso usamos el primer
        <h1>/<h2>. Si no hay encabezado, caemos al <title> del item."""
        match = HEADING_RE.search(self._entry_body_html(entry))
        if match:
            heading = HTML_TAG_RE.sub("", match.group(1)).strip()
            if heading:
                return heading
        return entry.get("title", None)

    def _extract_description(self, entry, limit=400):
        """Resumen corto para la tarjeta del dashboard. Quita los encabezados (el
        titular ya va en 'title') y las imágenes (van en 'image_url'), pasa a
        texto y recorta. Evita volcar el artículo completo con la imagen embebida
        cuando el feed entrega el contenido entero en el cuerpo (p. ej. Mintlify)."""
        text = self._entry_body_html(entry)
        text = re.sub(
            r"<h[1-6][^>]*>.*?</h[1-6]>", " ", text, flags=re.IGNORECASE | re.DOTALL
        )
        text = re.sub(
            r"<figure[^>]*>.*?</figure>", " ", text, flags=re.IGNORECASE | re.DOTALL
        )
        text = re.sub(r"<img[^>]*>", " ", text, flags=re.IGNORECASE)
        text = HTML_TAG_RE.sub(" ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > limit:
            text = text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:—-") + " […]"
        return text or None

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
                "title": self._extract_title(entry),
                "link": entry.get("link", None),
                "description": self._extract_description(entry),
                "publish_date": published_date,
                "author": entry.get("author", None),
                "image_url": self._extract_image_url(entry),
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
                    body=_("RSS feed imported successfully %s")
                    % rss_post_vals["title"]
                )
            except Exception as e:
                self.message_post(
                    body=_("Error importing RSS feed %(title)s: %(error)s")
                    % {
                        "title": rss_post_vals["title"],
                        "error": e,
                    }
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
