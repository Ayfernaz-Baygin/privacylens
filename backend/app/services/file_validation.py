import zipfile
from io import BytesIO

PDF_SIGNATURE = b"%PDF-"

DOCX_REQUIRED_ENTRIES = {
    "[Content_Types].xml",
    "word/document.xml",
}

XLSX_REQUIRED_ENTRIES = {
    "[Content_Types].xml",
    "xl/workbook.xml",
}


def is_valid_pdf(content: bytes) -> bool:
    return content.startswith(PDF_SIGNATURE)


def _zip_contains_all(
    content: bytes,
    required_entries: set[str],
) -> bool:
    """True only if content is a real ZIP archive containing every one
    of required_entries.

    A PK\\x03\\x04 magic-byte check alone would accept any ZIP file
    renamed to .docx/.xlsx; this actually opens the archive and checks
    for the specific parts every real DOCX/XLSX package must have.
    Any failure while parsing an untrusted, possibly-corrupt archive
    (bad zip, truncated, unsupported compression, ...) means "not a
    valid file" rather than propagating as an unhandled exception.
    """
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
    except Exception:
        return False

    return required_entries.issubset(names)


def is_valid_docx(content: bytes) -> bool:
    return _zip_contains_all(content, DOCX_REQUIRED_ENTRIES)


def is_valid_xlsx(content: bytes) -> bool:
    return _zip_contains_all(content, XLSX_REQUIRED_ENTRIES)


# --- ZIP bomb / decompression-abuse guard ------------------------------
#
# DOCX/XLSX are ZIP archives. Beyond checking that the required parts are
# present (is_valid_docx/is_valid_xlsx above), an attacker-crafted archive
# can still declare wildly inflated uncompressed sizes, hide encrypted
# entries, or use traversal-shaped entry names. This guard inspects only
# ZipInfo *metadata* (infolist()) -- it never decompresses an entry -- so
# checking it costs nothing proportional to what a malicious archive
# claims its inflated size to be.
#
# Limits are picked for a local/demo service: generous enough that any
# real DOCX/XLSX (including ones with embedded images or many sheets)
# passes comfortably, but far below what a deliberate zip bomb needs.
MAX_TOTAL_UNCOMPRESSED_SIZE = 200 * 1024 * 1024  # 200 MB inflated, total
MAX_ENTRY_UNCOMPRESSED_SIZE = 50 * 1024 * 1024   # 50 MB inflated, single entry
MAX_COMPRESSION_RATIO = 100                       # inflated size : stored size
MAX_ZIP_ENTRIES = 2000                            # real docx/xlsx: tens-to-low-hundreds

ENCRYPTED_ENTRY_FLAG_BIT = 0x1


def _has_unsafe_entry_name(name: str) -> bool:
    """Defense-in-depth: nothing extracts these entries to disk today,
    but reject traversal-shaped names anyway so that never becomes a
    silent assumption.
    """
    if not name:
        return True

    normalized = name.replace("\\", "/")

    if normalized.startswith("/"):
        return True

    if len(normalized) >= 2 and normalized[1] == ":":
        return True

    if ".." in normalized.split("/"):
        return True

    return False


def validate_safe_office_zip(content: bytes) -> bool:
    """True only if the archive's ZipInfo metadata stays within the
    decompression-abuse limits above.

    Runs before python-docx/openpyxl ever open the file. Complements
    is_valid_docx/is_valid_xlsx: this checks archive-level safety, not
    whether the expected DOCX/XLSX parts are present.
    """
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            infos = archive.infolist()
    except Exception:
        return False

    if len(infos) > MAX_ZIP_ENTRIES:
        return False

    total_uncompressed = 0

    for info in infos:
        if _has_unsafe_entry_name(info.filename):
            return False

        if info.flag_bits & ENCRYPTED_ENTRY_FLAG_BIT:
            return False

        file_size = info.file_size
        compress_size = info.compress_size

        if file_size > MAX_ENTRY_UNCOMPRESSED_SIZE:
            return False

        if compress_size == 0:
            if file_size > 0:
                # Anomalous: nonzero inflated size can't come from zero
                # stored bytes. Fail safe rather than special-case it.
                return False
        elif file_size / compress_size > MAX_COMPRESSION_RATIO:
            return False

        total_uncompressed += file_size

        if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_SIZE:
            return False

    return True


VALIDATORS_BY_EXTENSION = {
    ".pdf": is_valid_pdf,
    ".docx": is_valid_docx,
    ".xlsx": is_valid_xlsx,
}


def validate_file_content(extension: str, content: bytes) -> bool:
    """True only if content's real bytes match what `extension` claims.

    This is the security-relevant check: extension and declared
    Content-Type are both attacker-controlled, so the upload route uses
    this (not those) as the actual accept/reject decision.
    """
    validator = VALIDATORS_BY_EXTENSION.get(extension)

    if validator is None:
        return False

    return validator(content)
