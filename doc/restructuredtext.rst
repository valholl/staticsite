========================
 reStructuredText files
========================

reStructuredText file have a ``.rst`` or ``.rest`` extension.

Linking to other pages
----------------------

To be implemented.

Page metadata
-------------

As in Sphinx_, a field list near the top of the file is parsed as front
matter and removed from the generated files.

.. _Sphinx: http://www.sphinx-doc.org/en/stable/markup/misc.html#file-wide-metadata

This is a list of all metadata elements that are currently in use:

* ``date``: a python datetime object, timezone aware. If the date is in
  the future when ``ssite`` runs, the page will be consider a draft and
  will be ignored. Use ``ssite --draft`` to also consider draft pages.

* ``tags``: list of tags for the page.

* All `bibliographic fields`_ known to docutils.

.. _`bibliographic fields`: http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html#bibliographic-fields

`Back to README <../README.md>`_
