from dataclasses import dataclass

from application.checksum import (
    ChecksumRepository,
    calculate_checksum,
    ensure_unique_checksum,
    save_document_if_unique,
)
from application.pdf_extractor import PDFExtractor


@dataclass
class ExtractResult:
    text: str
    checksum: str


# Caso de uso de /extract: orquesta checksum -> unicidad -> extracción -> persistencia
# a través de puertos (ChecksumRepository, PDFExtractor), sin conocer HTTP, Mongo ni
# el microservicio concreto (SOLID: DIP). Vive en application/ y no en el endpoint para
# poder testearse con fakes, sin FastAPI. Propaga DuplicateDocumentError y las
# Extractor*Error; traducirlas a códigos HTTP es responsabilidad de presentation.
async def extract_document(
    pdf_bytes: bytes,
    repository: ChecksumRepository,
    extractor: PDFExtractor,
) -> ExtractResult:
    # El checksum se calcula sobre el upload crudo, antes de extraer: la deduplicación
    # debe basarse en el archivo original, ya que la extracción no está garantizada idempotente.
    checksum = calculate_checksum(pdf_bytes)
    # El duplicado se descarta antes de llamar al extractor: evita gastar CPU
    # del microservicio en archivos que igual se van a rechazar.
    await ensure_unique_checksum(checksum, repository)
    text = await extractor.extract(pdf_bytes)
    await save_document_if_unique(text, checksum, repository)
    return ExtractResult(text=text, checksum=checksum)
