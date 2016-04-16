# coding: utf-8

from .core import Archetype, Page, RenderedString, settings
import re
import os
import io
import pytz
import datetime
import dateutil.parser

import logging

log = logging.getLogger()


def parse_rest_with_front_matter(fd):
    return ([], [])

def parse_front_matter(lines):
    return "rest", {}


class ReSTPages:
    def __init__(self, site):
        self.site = site
        # Cached templates
        self._page_template = None
        self._redirect_template = None

    @property
    def page_template(self):
        if not self._page_template:
            self._page_template = self.site.theme.jinja2.get_template("page.html")
        return self._page_template

    @property
    def redirect_template(self):
        if not self._redirect_template:
            self._redirect_template = self.site.theme.jinja2.get_template("redirect.html")
        return self._redirect_template

    def render(self, page):
        # TODO: implement this
        return page.get_content()

    def try_load_page(self, root_abspath, relpath):
        if not (relpath.endswith(".rst") or relpath.endswith(".rest")):
            return None
        return ReSTPage(self, root_abspath, relpath)

    def try_load_archetype(self, archetypes, relpath, name):
        if not (relpath.endswith(".rst") or relpath.endswith(".rest")):
            return None
        if not (relpath.endswith(name + '.rst') or
                relpath.endswith(name + ".rest")):
            return None
        return ReSTArchetype(self, archetypes, relpath)


class ReSTArchetype(Archetype):
    def __init__(self, rstenv, archetypes, relpath):
        super().__init__(rstenv.site, relpath)
        self.rstenv = rstenv
        self.archetypes = archetypes

    def render(self, **kw):
        raise NotImplementedError


class ReSTPage(Page):
    TYPE = "restructuredtext"

    FINDABLE = True

    def __init__(self, resenv, root_abspath, relpath):
        dirname, basename = os.path.split(relpath)
        if basename in ['index.rst', 'index.rest']:
            linkpath = dirname
        else:
            linkpath = os.path.splitext(relpath)[0]
        super().__init__(
            site=resenv.site,
            root_abspath=root_abspath,
            src_relpath=relpath,
            src_linkpath=linkpath,
            dst_relpath=os.path.join(linkpath, "index.html"),
            dst_link=os.path.join(settings.SITE_ROOT, linkpath))

        # Shared restructuredtext environment
        self.resenv = resenv

        # Sequence of lines found in the front matter
        self.front_matter = []

        # Sequence of lines found in the body
        self.body = []

        # reStructuredText content of the page rendered into html
        self.rest_html = None

    def get_content(self):
        return "\n".join(self.body)

    def read_metadata(self):
        src = self.src_abspath
        if self.meta.get("date", None) is None:
            self.meta["date"] = pytz.utc.localize(datetime.datetime.utcfromtimestamp(os.path.getmtime(src)))

        with open(src, "rt") as fd:
            self.front_matter, self.body = parse_rest_with_front_matter(fd)

        try:
            style, meta = parse_front_matter(self.front_matter)
            self.meta.update(**meta)
        except:
            log.exception("%s: failed to parse front matter", self.src_relpath)

        # Remove leading empty lines
        while self.body and not self.body[0]:
            self.body.pop(0)

        date = self.meta.get("date", None)
        if date is not None and not isinstance(date, datetime.datetime):
            self.meta["date"] = dateutil.parser.parse(date)

    def check(self, checker):
        self.resenv.render(self)

    @property
    def content(self):
        if self.rest_html is None:
            self.rest_html = self.resenv.render(self)
        return self.rest_html

    def render(self):
        res = {}

        html = self.resenv.page_template.render(
            page=self,
            content=self.content,
            **self.meta,
        )
        res[self.dst_relpath] = RenderedString(html)

        for relpath in self.meta.get("aliases", ()):
            html = self.mdenv.redirect_template.render(
                page=self,
            )
            res[os.path.join(relpath, "index.html")] = RenderedString(html)

        return res

    def target_relpaths(self):
        res = [self.dst_relpath]
        for relpath in self.meta.get("aliases", ()):
            res.append(os.path.join(relpath, "index.html"))
        return res

