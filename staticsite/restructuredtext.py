# coding: utf-8

from .core import Archetype, Page, RenderedString
import re
import os
import io
import pytz
import datetime
import dateutil.parser
from docutils.core import publish_doctree, publish_programmatically
from docutils.nodes import docinfo
import docutils.nodes
import docutils.io
from docutils.transforms import Transform
from docutils.writers.html5_polyglot import Writer as HTMLWriter

import logging

log = logging.getLogger()


class LinkResolver(Transform):
    default_priority = 600

    def apply(self):
        # TODO: actually implement the link resolver
        for node in self.document.traverse():
            if isinstance(node, docutils.nodes.target):
                print(node)
            if isinstance(node, docutils.nodes.image):
                print(node)


class MyWriter(HTMLWriter):
    def get_transforms(self):
        transforms = super(MyWriter, self).get_transforms()
        transforms.append(LinkResolver)
        return transforms


def parse_rest(fd, t_names):
    """
    Parse a rest document.

    Return a tuple of 3 elements:
        * a dict with the first docinfo entries
        * the doctree with the docinfo removed
        * the parts published by the html5 writer
    """
    rst_lines = fd.readlines()

    # extract docinfo
    doctree = publish_doctree(''.join(rst_lines))
    info = doctree.children[doctree.first_child_matching_class(docinfo)]
    docinfo_data = {}
    for child in info.children:
        if child.tagname == 'field':
            if 'path' in child.attributes.get('classes'):
                docinfo_data['path'] = child.children[1].astext().strip()
            for t in t_names:
                if t in child.attributes.get('classes'):
                    tags = []
                    try:
                        tag_list = child.children[1][0]
                        for tag in tag_list.children:
                            tags.append(tag.astext())
                    except:
                        log.exception("failed to parse front matter")
                    docinfo_data[t] = tags
        else:
            docinfo_data[child.tagname] = child.astext()
    doctree.remove(info)

    parts = publish_parts_from_doctree(doctree)

    return docinfo_data, doctree, parts


def publish_parts_from_doctree(doctree):
    writer = MyWriter()
    output, pub = publish_programmatically(
        source=doctree, source_path=None,
        source_class=docutils.io.DocTreeInput,
        destination=None, destination_path=None,
        destination_class=docutils.io.StringOutput,
        reader=None, reader_name='doctree',
        parser=None, parser_name='null',
        writer=writer, writer_name=None,
        settings=None, settings_spec=None,
        settings_overrides=None,
        config_section=None,
        enable_exit_status=False
        )
    parts = pub.writer.parts

    return parts

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
        return publish_parts_from_doctree(content)['body']

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
        root, ext = os.path.splitext(os.path.basename(relpath))
        if not root == name:
            return None
        return ReSTArchetype(self, archetypes, relpath)


class ReSTArchetype(Archetype):
    def __init__(self, rstenv, archetypes, relpath):
        super().__init__(rstenv.site, relpath)
        self.rstenv = rstenv
        self.archetypes = archetypes

    def render(self, **kw):
        """
        Process the archetype returning its parsed front matter in a dict, and
        its contents in a string
        """
        # Render the archetype with jinja2
        abspath = os.path.join(self.archetypes.root, self.relpath)
        with open(abspath, "rt") as fd:
            template = self.site.theme.jinja2.from_string(fd.read())

        rendered = template.render(**kw)

        # Reparse the archetype to load the metadata
        with io.StringIO(rendered) as fd:
            try:
                meta, rst_body, rst_parts = parse_rest(fd, [])
            except:
                log.exception("archetype %s: failed to parse front matter", self.relpath)

        style = 'rest'

        return style, meta, rendered.split('\n')


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
        return self.doctree

    def read_metadata(self):
        src = self.src_abspath
        if self.meta.get("date", None) is None:
            self.meta["date"] = pytz.utc.localize(datetime.datetime.utcfromtimestamp(os.path.getmtime(src)))

        t_names = [t.name for t in self.site.taxonomies]
        with open(src, "rt") as fd:
            try:
                meta, self.doctree, self.rst_parts = parse_rest(fd, t_names)
                self.meta.update(**meta)
            except:
                log.exception("%s: failed to parse front matter", self.src_relpath)

        date = self.meta.get("date", None)
        if date is not None and not isinstance(date, datetime.datetime):
            self.meta["date"] = dateutil.parser.parse(date)

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

