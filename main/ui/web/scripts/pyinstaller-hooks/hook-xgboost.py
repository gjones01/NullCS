"""PyInstaller hook for xgboost.

PyInstaller ships no hook for xgboost, and the plain ``--collect-submodules xgboost``
flag cannot be used for this project. Recursing into ``xgboost.testing`` executes
``pytest.importorskip("hypothesis")``; pytest's ``Skipped`` derives from
``BaseException``, so it slips past the ``except Exception`` guard in
``PyInstaller.utils.hooks._collect_submodules`` and aborts the whole build with::

    RuntimeError: Child process call to _collect_submodules() failed with:
      Skipped: could not import 'hypothesis': No module named 'hypothesis'

Filtering those names out is safe because ``collect_submodules`` applies the filter
before it recurses, so the offending module is never imported. Everything else in
xgboost is still collected, and the test-only helpers (plus pytest/hypothesis) stay
out of the packaged binary.
"""

from PyInstaller.utils.hooks import collect_submodules

# Never import these while scanning: they pull in pytest and hypothesis.
_EXCLUDED_PREFIXES = ("xgboost.testing", "xgboost.tests")


def _keep(name: str) -> bool:
    return not name.startswith(_EXCLUDED_PREFIXES)


hiddenimports = collect_submodules("xgboost", filter=_keep)