# coding: utf-8

from .core import Archetype, Page, RenderedString
import re
import os
import io
import pytz
import datetime
import dateutil.parser
from docutils.core import publish_parts, publish_doctree
from docutils.nodes import docinfo, title

import logging

log = logging.getLogger()


def parse_rest(fd):
    """
    Parse a rest document.

    Return a tuple of 3 elements:
        * a dict with the first docinfo entries
        * the rst text without the first docinfo
        * the html5 parts rendered from this text
    """
    rst_lines = fd.readlines()

    # extract docinfo
    doctree = publish_doctree(''.join(rst_lines))
    info = doctree.children[doctree.first_child_matching_class(docinfo)]
    docinfo_data = {}
    for child in info.children:
        docinfo_data[child.tagname] = child.astext()
    doctree.remove(info)

    # remove docinfo and empty lines
    while (rst_lines[0] == '' or rst_lines[0][0] in [':', ' ', '\t']):
        rst_lines.pop(0)

    # render html5 parts
    rst_text = ''.join(rst_lines)
    parts = publish_parts(rst_text, writer_name="html5")

    return docinfo_data, rst_text, parts


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

    def render(self, page, content=None):
        if content is None:
            content = page.get_content()
        return publish_parts(content, writer_name="html5")['body']

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
            dst_link=os.path.join(resenv.site.settings.SITE_ROOT, linkpath))

        # Shared restructuredtext environment
        self.resenv = resenv

        # Sequence of lines found in the front matter
        self.front_matter = []

        # Sequence of lines found in the body
        self.body = []

        # reStructuredText content of the page rendered into html
        self.rest_html = None

    def get_content(self):
        return self.rst_body

    def read_metadata(self):
        src = self.src_abspath
        if self.meta.get("date", None) is None:
            self.meta["date"] = pytz.utc.localize(datetime.datetime.utcfromtimestamp(os.path.getmtime(src)))

        with open(src, "rt") as fd:
            try:
                meta, self.rst_body, self.rst_parts = parse_rest(fd)
                self.meta.update(**meta)
            except:
                log.exception("%s: failed to parse front matter", self.src_relpath)

        date = self.meta.get("date", None)
        if date is not None and not isinstance(date, datetime.datetime):
            self.meta["date"] = dateutil.parser.parse(date)

        if not self.meta.get("title", ""):
            self.meta['title'] = self.rst_parts['title']


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
            html = self.resenv.redirect_template.render(
                page=self,
            )
            res[os.path.join(relpath, "index.html")] = RenderedString(html)

        return res

    def target_relpaths(self):
        res = [self.dst_relpath]
        for relpath in self.meta.get("aliases", ()):
            res.append(os.path.join(relpath, "index.html"))
        return res

