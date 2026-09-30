"""Read-only, bounded previews and verified file access by catalog ID."""
import csv
import io
import json
import os
import re
import sqlite3
import stat

from data_agent.config import default_data_root, etl_output_path
from data_agent.services.etl_history import ETLHistory

PREVIEW_BYTES = 256 * 1024
PREVIEW_ROWS = 50
PREVIEW_COLUMNS = 100
PREVIEW_TEXT = 20_000
CELL_CHARACTERS = 1000
MEDIA_TYPES = {'csv': 'text/csv', 'json': 'application/json', 'parquet': 'application/vnd.apache.parquet'}


class ETLFileError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


class ETLBrowser:
    def __init__(self, *, history=None):
        self._history = history

    @property
    def history(self):
        # Resolve configuration after the host loads its environment. No startup IO.
        return self._history or ETLHistory(etl_output_path(default_data_root()))

    def _record(self, identifier):
        if not re.fullmatch(r'[0-9a-f]{16}', identifier):
            raise ETLFileError(400, 'INVALID_FILE_ID', 'Invalid ETL file identifier.')
        try:
            row = self.history.lookup(identifier)
        except (sqlite3.Error, OSError):
            raise ETLFileError(503, 'ETL_STORAGE_UNAVAILABLE', 'ETL file history is unavailable.') from None
        if row is None:
            raise ETLFileError(404, 'FILE_NOT_FOUND', 'This ETL file is not registered.')
        reference = row['storage_reference']
        if (not isinstance(reference, str) or not re.fullmatch(r'[a-z0-9_]+_\d{8}_\d{6}_\d{6}Z_[0-9a-f]{16}\.(csv|json|parquet)', reference)
                or reference != row['filename'] or not reference.endswith(f"_{identifier}.{row['format']}")):
            raise ETLFileError(409, 'INVALID_FILE_REFERENCE', 'The registered file reference is invalid.')
        return row

    @staticmethod
    def _metadata(row, available):
        # Explicit allowlist: source URLs and internal storage references are excluded.
        keys = ('id', 'filename', 'display_name', 'format', 'created_at', 'size_bytes', 'row_count')
        return {**{key: row[key] for key in keys}, 'status': 'ready' if available else 'failed', 'available': available}

    def open(self, identifier):
        row = self._record(identifier)
        if row['status'] != 'ready':
            raise ETLFileError(409, 'FILE_UNAVAILABLE', 'This ETL file is not ready.')
        path = self.history.root / row['storage_reference']
        handle = None
        try:
            if path.is_symlink() or path.resolve().parent != self.history.root:
                raise ETLFileError(409, 'INVALID_FILE_REFERENCE', 'The registered file reference is invalid.')
            before = path.lstat()
            if not stat.S_ISREG(before.st_mode):
                raise ETLFileError(409, 'FILE_UNAVAILABLE', 'This ETL file is unavailable.')
            handle = path.open('rb')
            opened = os.fstat(handle.fileno())
            if not os.path.samestat(before, opened) or opened.st_size != row['size_bytes']:
                raise ETLFileError(409, 'FILE_CHANGED', 'The stored file no longer matches its metadata.')
            return row, handle
        except FileNotFoundError:
            if handle: handle.close()
            raise ETLFileError(404, 'FILE_MISSING', 'The registered ETL file is missing.') from None
        except ETLFileError:
            if handle: handle.close()
            raise
        except OSError:
            if handle: handle.close()
            raise ETLFileError(503, 'ETL_STORAGE_UNAVAILABLE', 'The ETL file could not be opened.') from None

    def details(self, identifier):
        row, handle = self.open(identifier)
        handle.close()
        return self._metadata(row, True)

    @staticmethod
    def content_type(row, handle):
        if row['format'] != 'json':
            return MEDIA_TYPES.get(row['format'], 'application/octet-stream')
        try:
            raw = handle.read(PREVIEW_BYTES + 1)
            text = raw[:PREVIEW_BYTES].decode('utf-8-sig')
            if len(raw) <= PREVIEW_BYTES:
                try:
                    json.loads(text)
                    return 'application/json'
                except ValueError:
                    lines = [line for line in text.splitlines() if line.strip()]
                    if lines:
                        for line in lines: json.loads(line)
                        return 'application/x-ndjson'
            elif text.lstrip().startswith('['):
                return 'application/json'
            elif '\n' in text:
                first, remainder = text.split('\n', 1)
                json.loads(first)
                if remainder.strip(): return 'application/x-ndjson'
        except (ValueError, UnicodeError, RecursionError):
            pass
        finally:
            handle.seek(0)
        # Do not label unrecognizable/corrupted JSON as a verified JSON document.
        return 'application/octet-stream'

    def list(self, limit=50, offset=0):
        try:
            page = self.history.list(limit=limit, offset=offset)
        except (sqlite3.Error, OSError):
            raise ETLFileError(503, 'ETL_STORAGE_UNAVAILABLE', 'ETL file history is unavailable.') from None
        # Do not expose even a stale unsafe filename if its catalog relationship is invalid.
        records = []
        for item in page['files']:
            try:
                row = self._record(item['id'])
            except ETLFileError as exc:
                if exc.code in ('INVALID_FILE_REFERENCE', 'INVALID_FILE_ID', 'FILE_NOT_FOUND'):
                    continue
                raise
            records.append(self._metadata(row, item['available']))
        return {'files': records, 'page': {'limit': limit, 'offset': offset, 'has_more': page['has_more']}}

    def preview(self, identifier):
        row, handle = self.open(identifier)
        with handle:
            if row['format'] not in ('csv', 'json'):
                raise ETLFileError(415, 'PREVIEW_UNSUPPORTED', 'Preview is unavailable for this format. Download the original file.')
            raw = handle.read(PREVIEW_BYTES + 1)
        truncated = len(raw) > PREVIEW_BYTES
        try:
            # Incremental decoding tolerates only an unfinished final codepoint in a bounded prefix.
            import codecs
            text = codecs.getincrementaldecoder('utf-8-sig')().decode(raw[:PREVIEW_BYTES], final=not truncated)
        except UnicodeError:
            raise ETLFileError(422, 'FILE_CORRUPT', 'The file does not contain valid UTF-8 text.') from None
        if row['format'] == 'csv':
            return self._csv(text, truncated)
        return self._json(text, truncated)

    @staticmethod
    def _csv(text, truncated):
        columns, rows = [], []
        clipped = truncated
        try:
            reader = csv.reader(io.StringIO(text), strict=True)
            header = next(reader, [])
            columns = [value[:CELL_CHARACTERS] for value in header[:PREVIEW_COLUMNS]]
            clipped |= len(header) > PREVIEW_COLUMNS or any(len(value) > CELL_CHARACTERS for value in header)
            for row in reader:
                if not row: continue
                # A bounded prefix's final row may not be complete; never present it as complete.
                if truncated and reader.line_num >= len(text.splitlines()):
                    clipped = True
                    break
                if len(row) != len(header):
                    raise ValueError('Inconsistent CSV columns')
                if len(rows) == PREVIEW_ROWS:
                    clipped = True
                    break
                clipped |= any(len(value) > CELL_CHARACTERS for value in row)
                rows.append([value[:CELL_CHARACTERS] for value in row[:PREVIEW_COLUMNS]])
        except csv.Error as exc:
            if 'field larger than field limit' in str(exc):
                raise ETLFileError(413, 'PREVIEW_LIMIT', 'A CSV field exceeds the preview limit. Download the original file.') from None
            if not truncated:
                raise ETLFileError(422, 'FILE_CORRUPT', 'The CSV content is malformed.') from None
            clipped = True
        except ValueError:
            raise ETLFileError(422, 'FILE_CORRUPT', 'The CSV content is malformed.') from None
        return {'format': 'csv', 'columns': columns, 'rows': rows, 'text': None,
                'truncated': bool(clipped), 'validation': 'preview_only'}

    @staticmethod
    def _json(text, truncated):
        if not text.strip():
            return {'format': 'json', 'columns': [], 'rows': [], 'text': '', 'truncated': truncated, 'validation': 'preview_only'}
        if truncated:
            # A prefix of a large JSON object/array cannot be validated as a complete document.
            return {'format': 'json', 'columns': [], 'rows': [], 'text': text[:PREVIEW_TEXT],
                    'truncated': True, 'validation': 'unvalidated_prefix'}
        try:
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                value = [json.loads(line) for line in text.splitlines() if line.strip()]
            # Input is capped at 256 KiB; output is separately bounded in depth, breadth and text.
            clipped = False
            budget = 500
            def bounded(item, depth=0):
                nonlocal clipped, budget
                budget -= 1
                if depth >= 5 or budget <= 0:
                    clipped = True
                    return '[Preview limit]'
                if isinstance(item, dict):
                    clipped |= len(item) > 50
                    return {str(k)[:CELL_CHARACTERS]: bounded(v, depth+1) for k,v in list(item.items())[:50] if budget > 0}
                if isinstance(item, list):
                    clipped |= len(item) > 50
                    return [bounded(v, depth+1) for v in item[:50] if budget > 0]
                if isinstance(item, str) and len(item) > CELL_CHARACTERS:
                    clipped = True
                    return item[:CELL_CHARACTERS] + '…'
                return item
            rendered = json.dumps(bounded(value), ensure_ascii=False, indent=2)
            # JSON escapes can decode into unpaired surrogates that HTTP UTF-8
            # cannot encode. Return the normal corrupt-content error instead.
            rendered.encode('utf-8')
            return {'format': 'json', 'columns': [], 'rows': [], 'text': rendered[:PREVIEW_TEXT],
                    'truncated': clipped or len(rendered) > PREVIEW_TEXT, 'validation': 'preview_only'}
        except (ValueError, RecursionError):
            raise ETLFileError(422, 'FILE_CORRUPT', 'The JSON content is malformed or too deeply nested.') from None
