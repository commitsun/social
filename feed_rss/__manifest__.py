# Copyright 2023 CommitSun (<http://www.commitsun.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Feed RSS",
    "version": "14.0.2.6.7",
    "author": "Commit [Sun], Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "application": True,
    "category": "Pms",
    "website": "https://github.com/OCA/social",
    "installable": True,
    "external_dependencies": {"python": ["feedparser"]},
    "depends": ["base", "mail"],
    "data": [
        "security/pms_security.xml",
        "security/ir.model.access.csv",
        "views/rss_post_views.xml",
        "views/rss_source_views.xml",
        "data/cron_jobs.xml",
    ],
}
