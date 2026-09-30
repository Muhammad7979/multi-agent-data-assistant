"""Application-owned document lifecycle metadata, separate from Chroma internals."""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import sqlite3
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat()


class PolicyDocuments:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def connection(self):
        with closing(sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=5)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys=ON')
            with conn:
                yield conn

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, active_generation_id TEXT,
                    status TEXT NOT NULL CHECK(status IN ('pending','processing','ready','failed')),
                    error_code TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS document_generations (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
                    filename TEXT NOT NULL, media_type TEXT NOT NULL,
                    content_hash TEXT NOT NULL, size_bytes INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending','processing','ready','failed')),
                    error_code TEXT, chunk_count INTEGER NOT NULL DEFAULT 0,
                    cleanup_pending INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS generations_document ON document_generations(document_id);
            ''')

    def begin(self, document_id, filename, media_type, digest, size):
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            stamp = now()
            if document_id is None:
                document_id = str(uuid4())
                conn.execute('INSERT INTO documents VALUES (?,NULL,\'pending\',NULL,?,?)',
                             (document_id, stamp, stamp))
            else:
                row = conn.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
                if row is None:
                    raise KeyError('Document not found')
                if row['status'] in ('pending', 'processing'):
                    raise ValueError('Document is already processing')
                conn.execute("UPDATE documents SET status='pending',error_code=NULL,updated_at=? WHERE id=?",
                             (stamp, document_id))
            generation = str(uuid4())
            conn.execute('''INSERT INTO document_generations
                (id,document_id,filename,media_type,content_hash,size_bytes,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,'pending',?,?)''',
                (generation, document_id, filename, media_type, digest, size, stamp, stamp))
            return document_id, generation

    def processing(self, document_id, generation):
        with self.connection() as conn:
            conn.execute("UPDATE documents SET status='processing',updated_at=? WHERE id=?", (now(), document_id))
            conn.execute("UPDATE document_generations SET status='processing',updated_at=? WHERE id=?", (now(), generation))

    def activate(self, document_id, generation, count):
        with self.connection() as conn:
            conn.execute("UPDATE document_generations SET status='ready',chunk_count=?,updated_at=? WHERE id=? AND document_id=?",
                         (count, now(), generation, document_id))
            conn.execute('UPDATE documents SET active_generation_id=?,updated_at=? WHERE id=?', (generation, now(), document_id))
            conn.execute('UPDATE document_generations SET cleanup_pending=1 WHERE document_id=? AND id<>?', (document_id, generation))

    def finish(self, document_id):
        with self.connection() as conn:
            conn.execute("UPDATE documents SET status='ready',error_code=NULL,updated_at=? WHERE id=?", (now(), document_id))

    def fail(self, document_id, generation, code):
        with self.connection() as conn:
            active = conn.execute('SELECT active_generation_id FROM documents WHERE id=?', (document_id,)).fetchone()[0]
            if active != generation:
                conn.execute("UPDATE document_generations SET status='failed',error_code=?,cleanup_pending=1,updated_at=? WHERE id=?",
                             (code, now(), generation))
            conn.execute("UPDATE documents SET status='failed',error_code=?,updated_at=? WHERE id=?", (code, now(), document_id))

    def get(self, document_id):
        with self.connection() as conn:
            row = conn.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
            if row is None:
                return None
            result = dict(row)
            result['generations'] = [dict(g) for g in conn.execute(
                'SELECT * FROM document_generations WHERE document_id=? ORDER BY created_at,id', (document_id,))]
            return result

    def cleanup_done(self, generation):
        with self.connection() as conn:
            conn.execute('UPDATE document_generations SET cleanup_pending=0 WHERE id=?', (generation,))

    def list_ids(self, limit=50, offset=0):
        with self.connection() as conn:
            return [row[0] for row in conn.execute(
                'SELECT id FROM documents ORDER BY created_at DESC,id LIMIT ? OFFSET ?', (limit, offset))]

    def deactivate_for_delete(self, document_id):
        with self.connection() as conn:
            conn.execute("UPDATE documents SET active_generation_id=NULL,status='failed',error_code='DELETE_PENDING',updated_at=? WHERE id=?",
                         (now(), document_id))
            conn.execute('UPDATE document_generations SET cleanup_pending=1 WHERE document_id=?', (document_id,))

    def delete(self, document_id):
        with self.connection() as conn:
            conn.execute('DELETE FROM document_generations WHERE document_id=?', (document_id,))
            conn.execute('DELETE FROM documents WHERE id=?', (document_id,))

    def active_generation_ids(self):
        with self.connection() as conn:
            return [row[0] for row in conn.execute('''SELECT g.id FROM documents d
                JOIN document_generations g ON d.active_generation_id=g.id WHERE g.status='ready' ''')]
