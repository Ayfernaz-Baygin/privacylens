from pathlib import Path
from uuid import uuid4
import shutil

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.services.detection_engine import detect_sensitive_data
from backend.app.services.document_processing import (
    DocumentParseError,
    UnsupportedDocumentFormatError,
    analyze_document_file,
    build_finding_id,
)
from backend.app.services.docx_parser import extract_text_from_docx
from backend.app.services.docx_redactor import create_redacted_docx
from backend.app.services.pdf_highlighter import create_highlighted_pdf
from backend.app.services.pdf_locator import locate_text_in_pdf
from backend.app.services.pdf_parser import extract_text_from_pdf
from backend.app.services.pdf_redactor import create_redacted_pdf
from backend.app.services.redaction_decision import (
    filter_auto_redact_findings,
    select_redaction_findings,
)
from backend.app.services.xlsx_parser import extract_text_from_xlsx


class RedactionSelectionRequest(BaseModel):
    selected_finding_ids: list[str] = Field(
        default_factory=list
    )


router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
)


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".xlsx",
}

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

DOCUMENT_FORMAT_LABELS = {
    "pdf": "PDF",
    "docx": "DOCX",
    "xlsx": "XLSX",
}

MAX_FILE_SIZE = 20 * 1024 * 1024

UPLOAD_ROOT = Path("tmp/privacylens")

UPLOAD_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Dosya adı bulunamadı.",
        )

    extension = Path(
        file.filename
    ).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                "Sadece PDF, DOCX ve XLSX "
                "dosyaları desteklenmektedir."
            ),
        )

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Desteklenmeyen dosya türü.",
        )

    document_id = str(uuid4())

    document_directory = (
        UPLOAD_ROOT / document_id
    )

    document_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        document_directory
        / f"source{extension}"
    )

    total_size = 0
    chunk_size = 1024 * 1024

    try:
        with destination.open(
            "wb"
        ) as output_file:
            while True:
                chunk = await file.read(
                    chunk_size
                )

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "Dosya boyutu maksimum "
                            "20 MB olabilir."
                        ),
                    )

                output_file.write(chunk)

    except Exception:
        shutil.rmtree(
            document_directory,
            ignore_errors=True,
        )
        raise

    finally:
        await file.close()

    return {
        "id": document_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": total_size,
        "status": "uploaded",
    }


@router.get("/{document_id}/text")
def get_document_text(
    document_id: str,
):
    document_directory = (
        UPLOAD_ROOT / document_id
    )

    pdf_path = (
        document_directory
        / "source.pdf"
    )

    docx_path = (
        document_directory
        / "source.docx"
    )

    xlsx_path = (
        document_directory
        / "source.xlsx"
    )

    if not document_directory.exists():
        raise HTTPException(
            status_code=404,
            detail="Belge bulunamadı.",
        )

    if pdf_path.exists():
        try:
            result = extract_text_from_pdf(
                pdf_path
            )

        except Exception:
            raise HTTPException(
                status_code=422,
                detail=(
                    "PDF dosyası okunamadı "
                    "veya geçerli bir PDF değil."
                ),
            )

    elif docx_path.exists():
        try:
            result = extract_text_from_docx(
                docx_path
            )

        except Exception:
            raise HTTPException(
                status_code=422,
                detail=(
                    "DOCX dosyası okunamadı "
                    "veya geçerli bir DOCX değil."
                ),
            )

    elif xlsx_path.exists():
        try:
            result = extract_text_from_xlsx(
                xlsx_path
            )

        except Exception:
            raise HTTPException(
                status_code=422,
                detail=(
                    "XLSX dosyası okunamadı "
                    "veya geçerli bir XLSX değil."
                ),
            )

    else:
        raise HTTPException(
            status_code=415,
            detail=(
                "Bu aşamada metin çıkarma "
                "yalnızca PDF, DOCX ve XLSX "
                "dosyalarını destekliyor."
            ),
        )

    return {
        "id": document_id,
        "status": "parsed",
        **result,
    }


@router.get("/{document_id}/analyze")
def analyze_document(
    document_id: str,
):
    document_directory = (
        UPLOAD_ROOT / document_id
    )

    pdf_path = (
        document_directory
        / "source.pdf"
    )

    docx_path = (
        document_directory
        / "source.docx"
    )

    xlsx_path = (
        document_directory
        / "source.xlsx"
    )

    if not document_directory.exists():
        raise HTTPException(
            status_code=404,
            detail="Belge bulunamadı.",
        )

    try:
        analysis = analyze_document_file(
            pdf_path=pdf_path,
            docx_path=docx_path,
            xlsx_path=xlsx_path,
        )

    except UnsupportedDocumentFormatError:
        raise HTTPException(
            status_code=415,
            detail=(
                "Bu aşamada analiz yalnızca "
                "PDF, DOCX ve XLSX "
                "dosyalarını destekliyor."
            ),
        )

    except DocumentParseError as error:
        format_label = DOCUMENT_FORMAT_LABELS[
            error.document_format
        ]

        raise HTTPException(
            status_code=422,
            detail=(
                f"{format_label} dosyası "
                "analiz edilemedi."
            ),
        )

    return {
        "id": document_id,
        "status": "analyzed",
        "page_count": analysis[
            "page_count"
        ],
        "finding_count": len(
            analysis["findings"]
        ),
        "findings": analysis["findings"],
    }


@router.get("/{document_id}/highlight")
def highlight_document(
    document_id: str,
):
    document_directory = (
        UPLOAD_ROOT / document_id
    )

    pdf_path = (
        document_directory
        / "source.pdf"
    )

    highlighted_path = (
        document_directory
        / "highlighted.pdf"
    )

    if not document_directory.exists():
        raise HTTPException(
            status_code=404,
            detail="Belge bulunamadı.",
        )

    if not pdf_path.exists():
        raise HTTPException(
            status_code=415,
            detail=(
                "Highlight işlemi yalnızca "
                "PDF dosyalarını destekliyor."
            ),
        )

    try:
        parsed_document = (
            extract_text_from_pdf(
                pdf_path
            )
        )

    except Exception:
        raise HTTPException(
            status_code=422,
            detail=(
                "PDF dosyası "
                "analiz edilemedi."
            ),
        )

    findings = []

    for page in parsed_document["pages"]:
        page_findings = detect_sensitive_data(
            text=page["text"],
            page_number=page["page_number"],
            include_ner=True,
        )

        for finding in page_findings:
            bounding_boxes = locate_text_in_pdf(
                file_path=pdf_path,
                page_number=page["page_number"],
                value=finding["value"],
            )

            finding["bounding_boxes"] = (
                bounding_boxes
            )

            finding["finding_id"] = (
                build_finding_id(
                    finding
                )
            )

        findings.extend(
            page_findings
        )

    if not findings:
        raise HTTPException(
            status_code=404,
            detail=(
                "Highlight edilecek "
                "hassas veri bulunamadı."
            ),
        )

    create_highlighted_pdf(
        source_path=pdf_path,
        output_path=highlighted_path,
        findings=findings,
    )

    return FileResponse(
        path=highlighted_path,
        media_type="application/pdf",
        filename=(
            "privacylens-highlighted-"
            f"{document_id}.pdf"
        ),
    )


@router.get("/{document_id}/redact")
def redact_document(
    document_id: str,
):
    document_directory = (
        UPLOAD_ROOT / document_id
    )

    pdf_path = (
        document_directory
        / "source.pdf"
    )

    redacted_path = (
        document_directory
        / "redacted.pdf"
    )

    if not document_directory.exists():
        raise HTTPException(
            status_code=404,
            detail="Belge bulunamadı.",
        )

    if not pdf_path.exists():
        raise HTTPException(
            status_code=415,
            detail=(
                "Redaction işlemi yalnızca "
                "PDF dosyalarını destekliyor."
            ),
        )

    try:
        parsed_document = (
            extract_text_from_pdf(
                pdf_path
            )
        )

    except Exception:
        raise HTTPException(
            status_code=422,
            detail=(
                "PDF dosyası "
                "analiz edilemedi."
            ),
        )

    findings = []

    for page in parsed_document["pages"]:
        page_findings = detect_sensitive_data(
            text=page["text"],
            page_number=page["page_number"],
            include_ner=True,
        )

        for finding in page_findings:
            bounding_boxes = locate_text_in_pdf(
                file_path=pdf_path,
                page_number=page["page_number"],
                value=finding["value"],
            )

            finding["bounding_boxes"] = (
                bounding_boxes
            )

            finding["finding_id"] = (
                build_finding_id(
                    finding
                )
            )

        findings.extend(
            page_findings
        )

    auto_redact_findings = (
        filter_auto_redact_findings(
            findings
        )
    )

    if not auto_redact_findings:
        raise HTTPException(
            status_code=404,
            detail=(
                "Otomatik maskelenecek "
                "hassas veri bulunamadı."
            ),
        )

    create_redacted_pdf(
        source_path=pdf_path,
        output_path=redacted_path,
        findings=auto_redact_findings,
    )

    return FileResponse(
        path=redacted_path,
        media_type="application/pdf",
        filename=(
            "privacylens-redacted-"
            f"{document_id}.pdf"
        ),
    )


@router.post(
    "/{document_id}/redact-selected"
)
def redact_selected_document(
    document_id: str,
    request: RedactionSelectionRequest,
):
    document_directory = (
        UPLOAD_ROOT / document_id
    )

    pdf_path = (
        document_directory
        / "source.pdf"
    )

    docx_path = (
        document_directory
        / "source.docx"
    )

    xlsx_path = (
        document_directory
        / "source.xlsx"
    )

    if not document_directory.exists():
        raise HTTPException(
            status_code=404,
            detail="Belge bulunamadı.",
        )

    try:
        analysis = analyze_document_file(
            pdf_path=pdf_path,
            docx_path=docx_path,
            xlsx_path=xlsx_path,
        )

    except UnsupportedDocumentFormatError:
        raise HTTPException(
            status_code=415,
            detail=(
                "Redaction işlemi yalnızca "
                "PDF ve DOCX dosyalarını "
                "destekliyor."
            ),
        )

    except DocumentParseError as error:
        format_label = DOCUMENT_FORMAT_LABELS[
            error.document_format
        ]

        raise HTTPException(
            status_code=422,
            detail=(
                f"{format_label} dosyası "
                "analiz edilemedi."
            ),
        )

    document_format = analysis[
        "document_format"
    ]

    if document_format == "xlsx":
        raise HTTPException(
            status_code=415,
            detail=(
                "Redaction işlemi XLSX "
                "dosyaları için henüz "
                "desteklenmiyor."
            ),
        )

    is_docx = document_format == "docx"

    selected_findings = (
        select_redaction_findings(
            findings=analysis["findings"],
            selected_finding_ids=(
                request.selected_finding_ids
            ),
        )
    )

    if not selected_findings:
        raise HTTPException(
            status_code=404,
            detail=(
                "Maskelenecek veri "
                "bulunamadı."
            ),
        )

    if is_docx:
        redacted_path = (
            document_directory
            / "redacted-selected.docx"
        )

        create_redacted_docx(
            source_path=docx_path,
            output_path=redacted_path,
            findings=selected_findings,
        )

        return FileResponse(
            path=redacted_path,
            media_type=(
                "application/vnd.openxmlformats"
                "-officedocument.wordprocessingml"
                ".document"
            ),
            filename=(
                "privacylens-redacted-"
                f"{document_id}.docx"
            ),
        )

    redacted_path = (
        document_directory
        / "redacted-selected.pdf"
    )

    create_redacted_pdf(
        source_path=pdf_path,
        output_path=redacted_path,
        findings=selected_findings,
    )

    return FileResponse(
        path=redacted_path,
        media_type="application/pdf",
        filename=(
            "privacylens-redacted-"
            f"{document_id}.pdf"
        ),
    )