"""Local ETL file catalog; independent of Policy/Chroma and business databases."""
from contextlib import closing
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit


def source_metadata(url):
    # Keep only hostname. Paths, query strings, fragments and userinfo can contain secrets.
    try:
        parsed = urlsplit(url)
        return parsed.hostname if parsed.scheme in ('http', 'https') else None
    except (ValueError, TypeError):
        return None


class ETLHistory:
    def __init__(self, output_root):
        self.root = Path(output_root).resolve()
        self.path = self.root.parent / 'metadata.sqlite3'

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=30)) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS etl_files (
                    id TEXT PRIMARY KEY, filename TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL, format TEXT NOT NULL,
                    created_at TEXT NOT NULL, size_bytes INTEGER NOT NULL,
                    source TEXT, source_url TEXT, description TEXT,
                    status TEXT NOT NULL CHECK(status='ready'),
                    storage_reference TEXT NOT NULL, row_count INTEGER,
                    run_id TEXT);
                CREATE INDEX IF NOT EXISTS etl_files_created ON etl_files(created_at DESC, id DESC);
            ''')

    def insert(self, record):
        self.initialize()
        fields = ('id','filename','display_name','format','created_at','size_bytes','source',
                  'source_url','description','status','storage_reference','row_count','run_id')
        with closing(sqlite3.connect(self.path, timeout=30)) as conn, conn:
            conn.execute('INSERT INTO etl_files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', [record[k] for k in fields])

    def _public(self, row):
        result = dict(row)
        reference = result.pop('storage_reference')
        # Treat stale, tampered, or externally moved files as unavailable, not ready.
        candidate = self.root / reference
        available = False
        try:
            available = (reference == Path(reference).name and candidate.resolve().parent == self.root
                         and not candidate.is_symlink() and candidate.is_file()
                         and candidate.stat().st_size == result['size_bytes'])
        except (OSError, ValueError):
            pass
        result['available'] = available
        if not available:
            result['status'] = 'failed'
        return result

    def get(self, identifier):
        row = self.lookup(identifier)
        return self._public(row) if row else None

    def lookup(self, identifier):
        """Internal record, including storage reference; never serialize directly."""
        if not self.path.exists():
            return None
        with closing(sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=30)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM etl_files WHERE id=?', (identifier,)).fetchone()
            return dict(row) if row else None

    def list(self, *, limit=50, offset=0):
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise ValueError('Invalid ETL history pagination')
        if not self.path.exists():
            return {'files': [], 'limit': limit, 'offset': offset, 'has_more': False}
        with closing(sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=30)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT * FROM etl_files ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?',
                                (limit + 1, offset)).fetchall()
            return {'files': [self._public(row) for row in rows[:limit]],
                    'limit': limit, 'offset': offset, 'has_more': len(rows) > limit}
