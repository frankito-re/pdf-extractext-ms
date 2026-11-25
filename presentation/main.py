from typing import Annotated, Optional

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, model_validator

from application.checksum import ChecksumRepository
from application.document_service import DocumentDTO, DocumentRepository, get_document, get_all_documents, update_document, delete_document
from application.exceptions import DuplicateDocumentError
from application.extract_document import extract_document
from application.pdf_extractor import (
    ExtractorRejectedError,
    ExtractorTimeoutError,
    ExtractorUnavailableError,
    PDFExtractor,
)
from presentation.container import (
    get_checksum_repo,
    get_document_repo,
    get_pdf_extractor,
    lifespan,
)


# Solo los campos actualizables que pide la consigna (text/checksum), sin exponer
# campos especulativos que ningún caso de uso necesita todavía (YAGNI).
class UpdateDocumentRequest(BaseModel):
    text: Optional[str] = None
    checksum: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateDocumentRequest":
        if self.text is None and self.checksum is None:
            raise ValueError("At least one of 'text' or 'checksum' must be provided")
        return self


app = FastAPI(
    title="PDF Extractext API",
    description="API for PDF text extraction using Clean Architecture",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(ExtractorRejectedError)
async def extractor_rejected_handler(_request: Request, exc: ExtractorRejectedError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(ExtractorUnavailableError)
async def extractor_unavailable_handler(_request: Request, exc: ExtractorUnavailableError):
    headers = {"Retry-After": exc.retry_after} if exc.retry_after else None
    return JSONResponse(
        status_code=503, content={"detail": "PDF extractor is unavailable"}, headers=headers
    )


@app.exception_handler(ExtractorTimeoutError)
async def extractor_timeout_handler(_request: Request, _exc: ExtractorTimeoutError):
    return JSONResponse(status_code=504, content={"detail": "PDF extractor timed out"})


# Evita repetir la construcción del dict de respuesta en los 4 endpoints de
# documentos (DRY).
def _doc_to_response(doc: DocumentDTO) -> dict:
    return {"id": doc.id, "text": doc.text, "checksum": doc.checksum}


@app.get("/")
async def root(request: Request):
    """Redirect to the Swagger UI, honoring the proxy's root path."""
    prefix = request.scope.get("root_path", "").rstrip("/")
    return RedirectResponse(url=f"{prefix}/docs")

@app.get("/health")
async def health_check():
    """Report that the API is up and reachable."""
    return {"status": "ok", "message": "pong"}


@app.post("/extract")
async def extract_text(
    repository: Annotated[ChecksumRepository, Depends(get_checksum_repo)],
    extractor: Annotated[PDFExtractor, Depends(get_pdf_extractor)],
    file: UploadFile = File(...),
):
    """Extract text from an uploaded PDF (via the extractor microservice) and persist it if its checksum is not already stored.

    Returns 409 if a document with the same SHA-256 checksum already exists.
    """
    pdf_bytes = await file.read()
    try:
        result = await extract_document(pdf_bytes, repository, extractor)
    except DuplicateDocumentError as exc:
        raise HTTPException(status_code=409, detail=f"Duplicate document: {exc.checksum}")
    return {"text": result.text, "checksum": result.checksum}


@app.get("/documents")
async def list_documents(repo: Annotated[DocumentRepository, Depends(get_document_repo)]):
    """List all persisted documents."""
    docs = await get_all_documents(repo)
    return [_doc_to_response(d) for d in docs]


@app.get("/documents/{id}")
async def read_document(id: str, repo: Annotated[DocumentRepository, Depends(get_document_repo)]):
    """Retrieve a single document by id. Returns 404 if it doesn't exist."""
    doc = await get_document(id, repo)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_to_response(doc)


@app.patch("/documents/{id}")
async def update_document_endpoint(
    id: str,
    body: UpdateDocumentRequest,
    repo: Annotated[DocumentRepository, Depends(get_document_repo)],
):
    """Update a document's text and/or checksum. Returns 404 if it doesn't exist."""
    doc = await update_document(id, body.text, body.checksum, repo)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_to_response(doc)


@app.delete("/documents/{id}", status_code=204)
async def delete_document_endpoint(
    id: str,
    repo: Annotated[DocumentRepository, Depends(get_document_repo)],
):
    """Delete a document by id. Returns 404 if it doesn't exist."""
    deleted = await delete_document(id, repo)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return None
