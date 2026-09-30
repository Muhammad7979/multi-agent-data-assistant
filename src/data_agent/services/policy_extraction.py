"""Validated, bounded extraction and token-aware chunking; never executes content."""
from io import BytesIO
import multiprocessing
from pathlib import PureWindowsPath
import re
import unicodedata


class PolicyInputError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


FORMATS = {".txt": {"text/plain"}, ".md": {"text/markdown", "text/plain"}, ".pdf": {"application/pdf"}}


def validate_document(filename, content, media_type, settings):
    if (not isinstance(filename, str) or not filename or len(filename) > 255
            or filename != filename.strip() or filename.endswith('.')
            or any(c in filename for c in '/\\:<>"|?*')
            or any(unicodedata.category(c).startswith('C') for c in filename)):
        raise PolicyInputError("UNSAFE_FILENAME")
    path = PureWindowsPath(filename)
    if path.stem.split('.')[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1,10)], *[f"LPT{i}" for i in range(1,10)]}:
        raise PolicyInputError("UNSAFE_FILENAME")
    extension = path.suffix.lower()
    if extension not in FORMATS:
        raise PolicyInputError("UNSUPPORTED_TYPE")
    if not isinstance(media_type, str) or media_type.split(';')[0].strip().lower() not in FORMATS[extension]:
        raise PolicyInputError("TYPE_MISMATCH")
    if not isinstance(content, bytes):
        raise PolicyInputError("INVALID_CONTENT")
    if not content:
        raise PolicyInputError("EMPTY_FILE")
    if len(content) > settings.max_file_bytes:
        raise PolicyInputError("FILE_TOO_LARGE")
    if extension == '.pdf' and not content.startswith(b'%PDF-'):
        raise PolicyInputError("TYPE_MISMATCH")
    return extension


def _pdf_worker(connection, content, settings):
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise PolicyInputError("ENCRYPTED_PDF")
        if len(reader.pages) > settings.max_pages:
            raise PolicyInputError("TOO_MANY_PAGES")
        segments, size = [], 0
        for number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ''
            size += len(text)
            if size > settings.max_text_chars:
                raise PolicyInputError("TEXT_TOO_LARGE")
            if text.strip():
                segments.append({"text": text, "page": number})
        connection.send((True, segments))
    except PolicyInputError as exc:
        connection.send((False, exc.code))
    except Exception:
        connection.send((False, "PARSING_FAILED"))
    finally:
        connection.close()


def extract_text(content, extension, settings):
    if extension == '.pdf':
        context = multiprocessing.get_context('spawn')
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(target=_pdf_worker, args=(sender, content, settings), daemon=True)
        try:
            process.start()
            sender.close()
            if not receiver.poll(settings.parser_timeout_seconds):
                raise PolicyInputError("PARSING_TIMEOUT")
            try:
                success, result = receiver.recv()
            except EOFError:
                raise PolicyInputError("PARSING_FAILED") from None
            if not success:
                raise PolicyInputError(result)
            return result
        finally:
            receiver.close()
            sender.close()
            if process.pid is not None:
                process.join(timeout=1)
                if process.is_alive():
                    process.terminate()
                    process.join()
                process.close()
    try:
        text = content.decode('utf-8-sig')
    except UnicodeError:
        raise PolicyInputError("INVALID_TEXT_ENCODING") from None
    if any(ord(c) < 32 and c not in '\n\r\t' for c in text):
        raise PolicyInputError("INVALID_TEXT_CONTENT")
    if len(text) > settings.max_text_chars:
        raise PolicyInputError("TEXT_TOO_LARGE")
    if extension != '.md':
        return [{"text": text}]
    segments, lines, section, fence = [], [], None, None
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        heading = re.match(r'^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$', line) if fence is None and not marker else None
        if heading:
            if ''.join(lines).strip():
                segments.append({"text": ''.join(lines), **({"section": section} if section else {})})
            lines, section = [], heading.group(1)
        lines.append(line)
    if ''.join(lines).strip():
        segments.append({"text": ''.join(lines), **({"section": section} if section else {})})
    return segments


def chunk_text(segments, settings):
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=settings.encoding_name, chunk_size=settings.chunk_tokens,
        chunk_overlap=settings.overlap_tokens, allowed_special=set(), disallowed_special=(),
        separators=['\n\n', '\n', '. ', ' ', ''])
    chunks = []
    for segment in segments:
        for text in splitter.split_text(segment['text']):
            if text.strip():
                chunks.append({"text": text, **{k: segment[k] for k in ('page', 'section') if k in segment}})
            if len(chunks) > settings.max_chunks:
                raise PolicyInputError("TOO_MANY_CHUNKS")
    if not chunks:
        raise PolicyInputError("NO_EXTRACTABLE_TEXT")
    return chunks
