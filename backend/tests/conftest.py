import os
import tempfile

# Importing backend.app.routes.documents runs
# `UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)` at module scope, once,
# the first time anything imports it in this process -- which happens
# during test collection, before any fixture gets a chance to run. If
# PRIVACYLENS_UPLOAD_ROOT isn't already pointed elsewhere by then, that
# one-time side effect creates the real repository tmp/privacylens
# directory. Redirecting it here, before the imports below, keeps that
# side effect inside a throwaway directory instead.
#
# Kept as a module-level reference so the directory isn't cleaned up
# until the process exits (TemporaryDirectory self-cleans via
# weakref.finalize once nothing references it).
_collection_time_upload_root = tempfile.TemporaryDirectory(
    prefix="privacylens-test-collect-"
)
os.environ["PRIVACYLENS_UPLOAD_ROOT"] = (
    _collection_time_upload_root.name
)

import pytest  # noqa: E402

from backend.app import main as main_module  # noqa: E402
from backend.app.routes import documents as documents_module  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_upload_root(tmp_path, monkeypatch):
    """Every test gets its own document-storage directory under
    pytest's tmp_path, and the real repository tmp/privacylens is
    never touched.

    documents.py and main.py each hold their own module-level
    UPLOAD_ROOT binding -- main.py did `from .routes.documents import
    UPLOAD_ROOT`, which copies the reference at import time.
    Monkeypatching documents.UPLOAD_ROOT alone would not be visible to
    main.py's periodic cleanup loop, since that loop reads its own
    module's global at call time. Both are patched to the same Path so
    routes and the periodic cleanup task agree on where documents live.

    document_cleanup.py takes upload_root as a plain parameter
    everywhere, so there's no global there to patch.
    """
    test_root = tmp_path / "privacylens-test-storage"

    monkeypatch.setattr(
        documents_module, "UPLOAD_ROOT", test_root
    )
    monkeypatch.setattr(
        main_module, "UPLOAD_ROOT", test_root
    )

    yield test_root
