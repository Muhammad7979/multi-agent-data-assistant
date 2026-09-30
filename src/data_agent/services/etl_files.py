"""Unique, completed ETL output publication. No IO during import/construction."""
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.parse import urlsplit
from uuid import uuid4

from data_agent.config import etl_output_path
from data_agent.services.etl_history import ETLHistory, source_metadata

FORMATS = frozenset(('csv', 'json', 'parquet'))


def filename_stem(suggestion, source):
    def normalize(value):
        if not isinstance(value, str):
            return ''
        value = unicodedata.normalize('NFKD', value[:512]).encode('ascii', 'ignore').decode().lower()
        value = re.sub(r'\.(csv|json|parquet)$', '', value.strip())
        return re.sub(r'[^a-z0-9]+', '_', value).strip('_')[:64].rstrip('_')
    # A purported path is not a descriptive name; discard rather than interpret it.
    stem = normalize(suggestion) if isinstance(suggestion, str) and not any(c in suggestion for c in ('/', '\\', ':', '..')) else ''
    if not stem:
        try:
            parsed = urlsplit(source)
            stem = normalize(parsed.path.rstrip('/').rsplit('/', 1)[-1]) or normalize(parsed.hostname)
        except (TypeError, ValueError):
            stem = ''
    stem = stem or 'dataset'
    if stem in {'con', 'prn', 'aux', 'nul', *[f'com{i}' for i in range(1, 10)], *[f'lpt{i}' for i in range(1, 10)]}:
        stem = 'dataset_' + stem
    return stem


@dataclass(frozen=True)
class StoredETLFile:
    id: str
    path: Path
    created_at: str
    format: str
    size_bytes: int
    row_count: int | None


class ETLFileStore:
    def __init__(self, *, data_root):
        self.root = etl_output_path(Path(data_root))
        self.history = ETLHistory(self.root)

    def write(self, *, source, format, writer, suggested_name=None, row_count=None):
        if format not in FORMATS:
            raise ValueError('Unsupported ETL format')
        if row_count is not None and (type(row_count) is not int or row_count < 0):
            raise ValueError('Invalid row count')
        self.root.mkdir(parents=True, exist_ok=True)
        stage = self.root / '.staging'
        stage.mkdir(exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='etl_', suffix='.' + format, dir=stage)
        os.close(descriptor)
        temporary = Path(temporary)
        try:
            writer(temporary)
            with temporary.open('r+b') as handle:
                os.fsync(handle.fileno())
            created = datetime.now(timezone.utc)
            stamp = created.strftime('%Y%m%d_%H%M%S_%fZ')
            stem = filename_stem(suggested_name, source)
            for _ in range(10):
                identifier = uuid4().hex[:16]
                target = self.root / f'{stem}_{stamp}_{identifier}.{format}'
                try:
                    # Atomic, same-filesystem publication; unlike replace(), never overwrites.
                    os.link(temporary, target)
                except FileExistsError:
                    continue
                try:
                    size_bytes = target.stat().st_size
                    self.history.insert(dict(id=identifier, filename=target.name,
                        display_name=stem.replace('_', ' '), format=format, created_at=created.isoformat(),
                        size_bytes=size_bytes, source=source_metadata(source), source_url=None,
                        description=None, status='ready', storage_reference=target.name,
                        row_count=row_count, run_id=None))
                except Exception:
                    try:
                        target.unlink()
                    except OSError:
                        raise RuntimeError('ETL metadata publication failed; unregistered output requires cleanup') from None
                    raise RuntimeError('ETL metadata publication failed; output rolled back') from None
                return StoredETLFile(identifier, target, created.isoformat(), format, size_bytes, row_count)
            raise FileExistsError('Could not allocate a unique ETL filename')
        finally:
            temporary.unlink(missing_ok=True)
