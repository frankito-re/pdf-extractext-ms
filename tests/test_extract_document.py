import hashlib

import pytest

from application.exceptions import DuplicateDocumentError
from application.extract_document import ExtractResult, extract_document
from application.pdf_extractor import ExtractorTimeoutError

PDF_BYTES = b"%PDF-1.4 contenido"
CHECKSUM = hashlib.sha256(PDF_BYTES).hexdigest()


class FakeExtractor:
    def __init__(self, text: str = "texto extraido", error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls = 0

    async def extract(self, pdf_bytes: bytes) -> str:
        self.calls += 1
        if self.error:
            raise self.error
        return self.text


class FakeChecksumRepo:
    def __init__(self, existing: set[str] | None = None) -> None:
        self.existing = existing or set()
        self.saved: list[tuple[str, str]] = []

    async def exists(self, checksum: str) -> bool:
        return checksum in self.existing

    async def save(self, text: str, checksum: str) -> None:
        self.saved.append((text, checksum))


@pytest.mark.asyncio
async def test_extracts_and_persists_a_new_document():
    repo = FakeChecksumRepo()

    result = await extract_document(PDF_BYTES, repo, FakeExtractor("hola"))

    assert result == ExtractResult(text="hola", checksum=CHECKSUM)
    assert repo.saved == [("hola", CHECKSUM)]


@pytest.mark.asyncio
async def test_duplicate_is_rejected_before_calling_the_extractor():
    extractor = FakeExtractor()
    repo = FakeChecksumRepo(existing={CHECKSUM})

    with pytest.raises(DuplicateDocumentError) as exc_info:
        await extract_document(PDF_BYTES, repo, extractor)

    assert exc_info.value.checksum == CHECKSUM
    assert extractor.calls == 0
    assert repo.saved == []


@pytest.mark.asyncio
async def test_extractor_failure_propagates_and_nothing_is_saved():
    repo = FakeChecksumRepo()

    with pytest.raises(ExtractorTimeoutError):
        await extract_document(PDF_BYTES, repo, FakeExtractor(error=ExtractorTimeoutError()))

    assert repo.saved == []
