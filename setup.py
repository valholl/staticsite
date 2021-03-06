#!/usr/bin/env python3

from distutils.core import setup
import sys

setup(
    name = "staticsite",
    requires=[ 'unidecode', 'markdown', 'toml', 'yaml', 'jinja2', 'dateutil', 'livereload' ],
    version = "0.3",
    description = "Static site generator",
    author = ["Enrico Zini"],
    author_email = ["enrico@enricozini.org"],
    url = "https://github.com/spanezz/staticsite",
    license = "http://www.gnu.org/licenses/gpl-3.0.html",
    packages = ["staticsite", "staticsite.slugify"],
    scripts = ['ssite']
)
