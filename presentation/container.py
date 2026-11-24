from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request

from application.checksum import ChecksumRepository
from application.document_service import DocumentRepository
from application.pdf_extractor import PDFExtractor
from data.config import ExtractorSettings
from data.connection import get_database_connection
from data.extractor_client import HttpPDFExtractor
from data.models import ExtractedDocument
from data.repositories import MongoChecksumRepository
from data.repository import BeanieDocumentRepository


# Composition root: único módulo que conoce los adaptadores concretos (Mongo/Beanie,
# httpx) y los liga a los puertos de application/. main.py solo declara rutas contra
# esos puertos (SOLID: DIP). Cambiar de base o de extractor se resuelve acá.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Debe completarse antes de que la app empiece a servir: los modelos de Beanie
    # no se pueden usar en queries hasta que init_beanie() corra contra una conexión activa.
    await get_database_connection([ExtractedDocument])
    settings = ExtractorSettings()
    # Un único cliente HTTP por proceso: reutiliza conexiones hacia el extractor.
    async with httpx.AsyncClient(
        base_url=settings.url, timeout=settings.timeout_seconds
    ) as client:
        app.state.pdf_extractor = HttpPDFExtractor(client)
        yield


def get_document_repo() -> DocumentRepository:
    return BeanieDocumentRepository()


def get_checksum_repo() -> ChecksumRepository:
    return MongoChecksumRepository()


def get_pdf_extractor(request: Request) -> PDFExtractor:
    return request.app.state.pdf_extractor
