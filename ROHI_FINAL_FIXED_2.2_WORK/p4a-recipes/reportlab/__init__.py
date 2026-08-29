"""
Local override for python-for-android's built-in `reportlab` recipe.

Why this exists
----------------
p4a's stock recipe (pythonforandroid/recipes/reportlab/__init__.py) downloads
source from:

    https://hg.reportlab.com/hg-public/reportlab/archive/<changeset>.tar.gz

That Mercurial host now returns HTTP 403 Forbidden to automated/CI requests,
so `buildozer android debug` fails during the "create" step before any of
our own code is even touched. This has happened before with reportlab's
source host (it moved off Bitbucket for the same reason years ago).

Fix
---
Any recipe folder placed under the directory named in buildozer.spec's
`p4a.local_recipes` takes priority over p4a's built-in recipe of the same
name, so we replace it here with one that:

  1. Downloads from PyPI instead (files.pythonhosted.org / pypi.io), which
     doesn't block CI traffic.
  2. Uses a plain PythonRecipe instead of CompiledComponentsPythonRecipe, so
     it does a straight `pip install` rather than forcing a build of
     reportlab's optional `_rl_accel` / `_renderPM` C accelerators (those
     are what forced pinning to Python 3.10 in buildozer.spec in the first
     place, since they use CPython APIs removed in 3.11+). The app only
     uses reportlab's high-level API (SimpleDocTemplate, Table, Paragraph,
     etc.), which works fine without the accelerators - just slightly
     slower PDF generation, which is irrelevant for attendance reports.

If you ever want the accelerated build back, you'd need to restore the
CompiledComponentsPythonRecipe behavior AND keep chasing whatever URL
reportlab's source currently lives at.
"""

from pythonforandroid.recipe import PythonRecipe


class ReportlabRecipe(PythonRecipe):
    name = 'reportlab'
    version = '4.2.5'
    url = 'https://pypi.io/packages/source/r/reportlab/reportlab-{version}.tar.gz'

    # pillow is already in requirements (used for image support in PDFs);
    # setuptools is needed to run reportlab's setup.py.
    depends = ['setuptools', 'pillow']

    call_hostpython_via_targetpython = False


recipe = ReportlabRecipe()
