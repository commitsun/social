# Copyright 2023
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import hashlib
import html
import re
from datetime import datetime

import feedparser

from odoo import _, fields, models

# Patrones para extraer la imagen, el titular y la introducción del HTML del
# cuerpo del item (content:encoded o description). Necesario para feeds que no
# exponen un <enclosure> para la imagen ni un <title> descriptivo (p. ej.
# Mintlify, que pone la portada y el titular dentro del HTML del contenido).
IMG_SRC_RE = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.IGNORECASE)
HEADING_RE = re.compile(r"<h[12][^>]*>(.*?)</h[12]>", re.IGNORECASE | re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]+>")
PARAGRAPH_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)

# Algunos feeds (p. ej. Mintlify) ponen la fecha real del artículo en el <title>
# y entregan un <pubDate> poco fiable (fecha de build, igual para varios items),
# lo que rompe la ordenación. Estos meses permiten leer la fecha del <title>.
MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
DATE_RE = re.compile(
    r"(\d{1,2})\s+(?:de\s+)?([a-záéíóúñ]+)\s+(?:de\s+)?(\d{4})", re.IGNORECASE
)


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

    def _clean_text(self, raw, limit):
        text = re.sub(r"\s+", " ", HTML_TAG_RE.sub(" ", raw)).strip()
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)  # sin espacio antes de puntuación
        if len(text) > limit:
            text = text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:—-") + "…"
        return text

    def _extract_description(self, entry, limit=300):
        """Introducción breve para la tarjeta del dashboard: el primer párrafo de
        texto real del cuerpo, como reclamo para entrar al detalle. Decodifica
        entidades (algunos feeds escapan HTML, p. ej. botones JSX de Mintlify) y
        descarta imágenes y enlaces sueltos. Evita volcar el artículo completo o
        dejar HTML visible."""
        body = html.unescape(self._entry_body_html(entry))
        body = re.sub(
            r"<figure[^>]*>.*?</figure>", " ", body, flags=re.IGNORECASE | re.DOTALL
        )
        body = re.sub(r"<img[^>]*>", " ", body, flags=re.IGNORECASE)
        for raw in PARAGRAPH_RE.findall(body):
            text = self._clean_text(raw, limit)
            if len(text) >= 40:  # primer párrafo con texto sustancial = la intro
                return text
        return self._clean_text(body, limit) or None

    def _extract_publish_date(self, entry):
        """Fecha de publicación: preferimos la fecha escrita en el <title> (algunos
        feeds, p. ej. Mintlify, ponen ahí la fecha real del artículo y un <pubDate>
        que es la fecha de build, lo que rompe el orden). Si no, el <pubDate>."""
        match = DATE_RE.search(entry.get("title") or "")
        if match:
            day, month_name, year = match.groups()
            month = MONTHS.get(month_name.lower())
            if month:
                try:
                    return datetime(int(year), month, int(day))
                except ValueError:
                    pass
        if entry.get("published_parsed"):
            return datetime(*entry.published_parsed[:6])
        return None

    def import_rss_feed(self):
        self.ensure_one()
        feed = feedparser.parse(self.source_url)
        for entry in feed.entries:
            published_date = self._extract_publish_date(entry)
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
