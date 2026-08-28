import logging
import shutil
import time
from pathlib import Path
from uuid import UUID

logger = logging.getLogger(__name__)

# Abandoned documents (uploaded but never redacted/deleted) are removed
# after this many seconds. 1 hour is a reasonable default for a local
# demo service: long enough to finish a normal review session, short
# enough that nothing lingers on disk for long.
DOCUMENT_RETENTION_SECONDS = 3600

# How often the background sweep checks for stale document directories.
CLEANUP_INTERVAL_SECONDS = 300


def _is_document_directory_name(name: str) -> bool:
    """document_id directories are always canonical UUID4 strings (see
    validate_document_id / uuid4() at upload time). Anything else under
    UPLOAD_ROOT wasn't created by this service, so cleanup leaves it
    alone rather than guessing.
    """
    try:
        parsed = UUID(name)
    except (ValueError, AttributeError, TypeError):
        return False

    return parsed.version == 4 and str(parsed) == name


def delete_document_directory(
    upload_root: Path,
    document_id: str,
) -> None:
    """Recursively deletes upload_root/document_id, if present.

    Confined to a direct child of upload_root: resolves both paths and
    refuses to act unless the target is exactly one level under the
    root, so this can never be tricked into deleting outside it.
    """
    document_directory = upload_root / document_id

    try:
        resolved_root = upload_root.resolve()
        resolved_target = document_directory.resolve()
    except OSError:
        return

    if resolved_target.parent != resolved_root:
        return

    if not resolved_target.is_dir():
        return

    shutil.rmtree(resolved_target, ignore_errors=True)


def _newest_mtime(directory: Path, now: float) -> float:
    """The document's age is the age of its *most recently touched*
    file or the directory itself, whichever is newest -- so generating
    a new file inside it (e.g. a fresh redacted output) resets the
    retention clock for the whole document, not just that one file.
    """
    newest = directory.stat().st_mtime

    for path in directory.rglob("*"):
        try:
            newest = max(newest, path.stat().st_mtime)
        except OSError:
            continue

    return now - newest


def cleanup_stale_documents(
    upload_root: Path,
    retention_seconds: float = DOCUMENT_RETENTION_SECONDS,
) -> int:
    """Deletes every document directory under upload_root whose newest
    contained mtime is older than retention_seconds.

    Fail-safe by design: an unexpected (non-UUID4) directory name is
    skipped rather than deleted, and a failure while removing one
    document directory is logged and skipped so it never stops the
    rest of the sweep (or crashes the caller).
    """
    if not upload_root.exists():
        return 0

    now = time.time()
    deleted_count = 0

    for entry in upload_root.iterdir():
        if not entry.is_dir():
            continue

        if not _is_document_directory_name(entry.name):
            continue

        try:
            age_seconds = _newest_mtime(entry, now)

            if age_seconds < retention_seconds:
                continue

            shutil.rmtree(entry)
            deleted_count += 1

            logger.info(
                "cleanup_stale_documents: removed stale document "
                "document_id=%s age_seconds=%.0f",
                entry.name,
                age_seconds,
            )
        except Exception:
            logger.exception(
                "cleanup_stale_documents: failed to remove "
                "document_id=%s",
                entry.name,
            )
            continue

    return deleted_count
