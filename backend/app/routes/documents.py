from pathlib import Path
from uuid import uuid4
import shutil

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.app.services.detection_engine import detect_sensitive_data
from backend.app.services.pdf_parser import extract_text_from_pdf
from backend.app.services.pdf_locator import locate_text_in_pdf
from backend.app.services.pdf_locator import locate_text_in_pdf
from backend.app.services.pdf_highlighter import create_highlighted_pdf



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

MAX_FILE_SIZE = 20 * 1024 * 1024

UPLOAD_ROOT = Path("tmp/privacylens")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


@router.post("")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Dosya adı bulunamadı.",
        )

    extension = Path(file.filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Sadece PDF, DOCX ve XLSX dosyaları desteklenmektedir.",
        )

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Desteklenmeyen dosya türü.",
        )

    document_id = str(uuid4())

    document_directory = UPLOAD_ROOT / document_id
    document_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = document_directory / f"source{extension}"

    total_size = 0
    chunk_size = 1024 * 1024

    try:
        with destination.open("wb") as output_file:
            while True:
                chunk = await file.read(chunk_size)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="Dosya boyutu maksimum 20 MB olabilir.",
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
def get_document_text(document_id: str):
    document_directory = UPLOAD_ROOT / document_id
    pdf_path = document_directory / "source.pdf"

    if not document_directory.exists():
        raise HTTPException(
            status_code=404,
            detail="Belge bulunamadı.",
        )

    if not pdf_path.exists():
        raise HTTPException(
            status_code=415,
            detail="Bu aşamada metin çıkarma yalnızca PDF dosyalarını destekliyor.",
        )

    try:
        result = extract_text_from_pdf(pdf_path)

    except Exception:
        raise HTTPException(
            status_code=422,
            detail="PDF dosyası okunamadı veya geçerli bir PDF değil.",
        )

    return {
        "id": document_id,
        "status": "parsed",
        **result,
    }


@router.get("/{document_id}/analyze")
def analyze_document(document_id: str):
    document_directory = UPLOAD_ROOT / document_id
    pdf_path = document_directory / "source.pdf"

    if not document_directory.exists():
        raise HTTPException(
            status_code=404,
            detail="Belge bulunamadı.",
        )

    if not pdf_path.exists():
        raise HTTPException(
            status_code=415,
            detail="Bu aşamada analiz yalnızca PDF dosyalarını destekliyor.",
        )

    try:
        parsed_document = extract_text_from_pdf(pdf_path)

    except Exception:
        raise HTTPException(
            status_code=422,
            detail="PDF dosyası analiz edilemedi.",
        )

    findings = []

    for page in parsed_document["pages"]:
        page_findings = detect_sensitive_data(
            text=page["text"],
            page_number=page["page_number"],
        )

        for finding in page_findings:
            bounding_boxes = locate_text_in_pdf(
                file_path=pdf_path,
                page_number=page["page_number"],
                value=finding["value"],
            )

            finding["bounding_boxes"] = bounding_boxes

        findings.extend(page_findings)

    return {
        "id": document_id,
        "status": "analyzed",
        "page_count": parsed_document["page_count"],
        "finding_count": len(findings),
        "findings": findings,
    }

@router.get("/{document_id}/highlight")
def highlight_document(document_id: str):
    document_directory = UPLOAD_ROOT / document_id
    pdf_path = document_directory / "source.pdf"
    highlighted_path = document_directory / "highlighted.pdf"

    if not document_directory.exists():
        raise HTTPException(
            status_code=404,
            detail="Belge bulunamadı.",
        )

    if not pdf_path.exists():
        raise HTTPException(
            status_code=415,
            detail="Highlight işlemi yalnızca PDF dosyalarını destekliyor.",
        )

    try:
        parsed_document = extract_text_from_pdf(pdf_path)

    except Exception:
        raise HTTPException(
            status_code=422,
            detail="PDF dosyası analiz edilemedi.",
        )

    findings = []

    for page in parsed_document["pages"]:
        page_findings = detect_sensitive_data(
            text=page["text"],
            page_number=page["page_number"],
        )

        for finding in page_findings:
            bounding_boxes = locate_text_in_pdf(
                file_path=pdf_path,
                page_number=page["page_number"],
                value=finding["value"],
            )

            finding["bounding_boxes"] = bounding_boxes

        findings.extend(page_findings)

    if not findings:
        raise HTTPException(
            status_code=404,
            detail="Highlight edilecek hassas veri bulunamadı.",
        )

    create_highlighted_pdf(
        source_path=pdf_path,
        output_path=highlighted_path,
        findings=findings,
    )

    return FileResponse(
        path=highlighted_path,
        media_type="application/pdf",
        filename=f"privacylens-highlighted-{document_id}.pdf",
    )