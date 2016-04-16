# coding: utf-8
import os
import re
import pytz
import datetime
from collections import defaultdict
from .core import settings
import logging

log = logging.getLogger()

class Site:
    def __init__(self):
        # Site pages
        self.pages = {}

        # Description of tags
        self.tag_descriptions = {}

        # Site time zone
        self.timezone = pytz.timezone(settings.TIMEZONE)

        # Current datetime
        self.generation_time = pytz.utc.localize(datetime.datetime.utcnow()).astimezone(self.timezone)

        # Taxonomies found in the site
        self.taxonomies = []

        # Theme used to render pages
        self.theme = None

        # Map input file patterns to resource handlers
        from .markdown import MarkdownPages
        from .restructuredtext import ReSTPages
        from .j2 import J2Pages
        from .taxonomy import TaxonomyPages
        self.page_handlers = [
            MarkdownPages(self),
            ReSTPages(self),
            J2Pages(self),
            TaxonomyPages(self),
        ]

    def load_theme(self, theme_root):
        """
        Load a theme from the given directory.

        This needs to be called once (and only once) before analyze() is
        called.
        """
        if self.theme is not None:
            raise RuntimeError("cannot load theme from {} because it was already loaded from {}".format(theme_root, self.theme.root))

        from .theme import Theme
        self.theme = Theme(self, theme_root)

        theme_static = os.path.join(theme_root, "static")
        if os.path.isdir(theme_static):
            self.read_asset_tree(theme_static)

    def load_content(self, content_root):
        self.read_contents_tree(content_root)

    def add_page(self, page):
        self.pages[page.src_linkpath] = page

    def read_contents_tree(self, tree_root):
        """
        Read static assets and pages from a directory and all its subdirectories
        """
        from .asset import Asset

        log.info("Loading pages from %s", tree_root)

        for root, dnames, fnames in os.walk(tree_root):
            for f in fnames:
                if f.startswith("."): continue

                page_abspath = os.path.join(root, f)
                page_relpath = os.path.relpath(page_abspath, tree_root)

                for handler in self.page_handlers:
                    p = handler.try_load_page(tree_root, page_relpath)
                    if p is not None:
                        self.add_page(p)
                        break
                else:
                    if os.path.isfile(page_abspath):
                        log.debug("Loading static file %s", page_relpath)
                        p = Asset(self, tree_root, page_relpath)
                        self.add_page(p)

    def read_asset_tree(self, tree_root):
        """
        Read static assets from a directory and all its subdirectories
        """
        from .asset import Asset

        log.info("Loading assets from %s", tree_root)

        for root, dnames, fnames in os.walk(tree_root):
            for f in fnames:
                if f.startswith("."): continue

                page_abspath = os.path.join(root, f)
                if os.path.isfile(page_abspath):
                    page_relpath = os.path.relpath(page_abspath, tree_root)
                    log.debug("Loading static file %s", page_relpath)
                    p = Asset(self, tree_root, page_relpath)
                    self.add_page(p)

    def relocate(self, page, dest_relpath):
        log.info("Relocating %s to %s", page.relpath, dest_relpath)
        if dest_relpath in self.pages:
            log.warn("Cannot relocate %s to existing page %s", page.relpath, dest_relpath)
            return
        self.pages[dest_relpath] = page
        page.aliases.append(page.relpath)
        page.relpath = dest_relpath

    def analyze(self):
        self.taxonomies = []

        by_dir = defaultdict(list)
        by_pass = defaultdict(list)
        for page in self.pages.values():
            # Group pages by pass number
            by_pass[page.ANALYZE_PASS].append(page)
            # Collect taxonomies
            if page.TYPE == "taxonomy":
                self.taxonomies.append(page)
            # Harvest content for directory indices
            if page.FINDABLE and page.src_relpath:
                dir_relpath = os.path.dirname(page.src_relpath)
                by_dir[dir_relpath].append(page)
                while True:
                    if not dir_relpath: break
                    dir_relpath = os.path.dirname(dir_relpath)
                    # Do a lookup to make sure an entry exists for this
                    # directory level, even though without pages
                    by_dir[dir_relpath]


        # Build directory indices
        from .dir import DirPage
        for relpath, pages in by_dir.items():
            # We only build indices where there is not already a page
            if relpath in self.pages: continue
            page = DirPage(self, relpath, pages)
            self.pages[relpath] = page
            by_pass[page.ANALYZE_PASS].append(page)

        # Add directory indices to their parent directory indices
        for relpath, pages in by_dir.items():
            page = self.pages[relpath]
            if page.TYPE != "dir": continue
            page.attach_to_parent()

        # Read metadata
        for passnum, pages in sorted(by_pass.items(), key=lambda x:x[0]):
            for page in pages:
                page.read_metadata()


    def slugify(self, text):
        from .slugify import slugify
        return slugify(text)
