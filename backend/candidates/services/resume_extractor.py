import io
import os
import pypdf
import docx
from typing import Tuple


class ResumeExtractionError(Exception):
    """Base exception for resume text extraction errors."""
    pass


class UnsupportedFileError(ResumeExtractionError):
    """Raised when file extension or magic header is invalid."""
    pass


class CorruptedFileError(ResumeExtractionError):
    """Raised when file cannot be parsed or read."""
    pass


class EncryptedFileError(ResumeExtractionError):
    """Raised when document is password-protected or encrypted."""
    pass


class EmptyDocumentError(ResumeExtractionError):
    """Raised when document contains no extractable text (e.g., scanned image PDF without OCR)."""
    pass


class FileSizeLimitExceededError(ResumeExtractionError):
    """Raised when file exceeds the allowed upload limit."""
    pass


class ResumeExtractorService:
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
    MAX_TEXT_CHARACTERS = 100_000           # 100,000 characters limit

    @classmethod
    def extract_text(cls, file_obj, filename: str) -> str:
        """
        Extracts plain text from a PDF or DOCX file-like object.
        Validates magic bytes, corruptions, encryption, and minimum text content.
        """
        if not file_obj:
            raise UnsupportedFileError("No file provided for extraction.")

        # Determine extension
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ['.pdf', '.docx']:
            raise UnsupportedFileError(f"Unsupported file extension '{ext}'. Only .pdf and .docx are supported.")

        # Read content bytes into memory safely
        file_obj.seek(0)
        content_bytes = file_obj.read()
        if len(content_bytes) > cls.MAX_FILE_SIZE_BYTES:
            raise FileSizeLimitExceededError("File size exceeds the 10MB limit.")

        if len(content_bytes) == 0:
            raise CorruptedFileError("File is empty (0 bytes).")

        if ext == '.pdf':
            return cls._extract_from_pdf(content_bytes)
        elif ext == '.docx':
            return cls._extract_from_docx(content_bytes)

        raise UnsupportedFileError("Unsupported file type.")

    @classmethod
    def _extract_from_pdf(cls, content_bytes: bytes) -> str:
        # Magic bytes check for PDF
        if not content_bytes.startswith(b'%PDF-'):
            raise UnsupportedFileError("Invalid PDF format. File content does not match PDF signature.")

        try:
            stream = io.BytesIO(content_bytes)
            reader = pypdf.PdfReader(stream)

            if reader.is_encrypted:
                raise EncryptedFileError("PDF file is encrypted or password-protected.")

            text_chunks = []
            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_chunks.append(page_text.strip())

            full_text = "\n\n".join(text_chunks).strip()
            if not full_text:
                raise EmptyDocumentError(
                    "No usable text found in PDF. Scanned or image-only documents requiring OCR are not currently supported."
                )

            # Enforce max extracted characters
            if len(full_text) > cls.MAX_TEXT_CHARACTERS:
                full_text = full_text[:cls.MAX_TEXT_CHARACTERS]

            return full_text
        except EncryptedFileError:
            raise
        except EmptyDocumentError:
            raise
        except Exception as e:
            raise CorruptedFileError("Unable to parse PDF document. The file may be corrupt or invalid.")

    @classmethod
    def _extract_from_docx(cls, content_bytes: bytes) -> str:
        # Magic bytes check for ZIP (DOCX is a zipped XML package starting with PK\x03\x04)
        if not content_bytes.startswith(b'PK\x03\x04'):
            raise UnsupportedFileError("Invalid DOCX format. File content does not match DOCX package signature.")

        try:
            stream = io.BytesIO(content_bytes)
            doc = docx.Document(stream)

            text_parts = []
            for p in doc.paragraphs:
                clean_p = p.text.strip()
                if clean_p:
                    text_parts.append(clean_p)

            for table in doc.tables:
                for row in table.rows:
                    row_cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if row_cells:
                        text_parts.append(" | ".join(row_cells))

            full_text = "\n".join(text_parts).strip()
            if not full_text:
                raise EmptyDocumentError("The DOCX document contains no text content.")

            if len(full_text) > cls.MAX_TEXT_CHARACTERS:
                full_text = full_text[:cls.MAX_TEXT_CHARACTERS]

            return full_text
        except EmptyDocumentError:
            raise
        except Exception as e:
            raise CorruptedFileError("Unable to parse DOCX document. The file may be corrupt or invalid.")
