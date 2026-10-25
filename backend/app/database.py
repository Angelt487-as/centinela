import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def data_root() -> Path:
    path = Path(os.environ.get('CENTINELA_DATA_DIR', ROOT / 'data')).resolve()
    path.mkdir(parents=True, exist_ok=True)
    (path / 'originals').mkdir(exist_ok=True)
    return path


@contextmanager
def connection():
    db = sqlite3.connect(data_root() / 'centinela.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize():
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, sha256 TEXT NOT NULL,
            extension TEXT NOT NULL, size INTEGER NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS datasets (
            id TEXT PRIMARY KEY, file_id TEXT REFERENCES files(id),
            name TEXT NOT NULL, sha256 TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL,
            row_count INTEGER NOT NULL, metadata TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY, dataset_id TEXT NOT NULL REFERENCES datasets(id),
            subject TEXT, kind TEXT, number_a TEXT, number_b TEXT,
            timestamp TEXT NOT NULL, duration REAL, imei TEXT,
            latitude REAL, longitude REAL, azimuth REAL, raw TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS events_dataset_time ON events(dataset_id,timestamp);
        CREATE INDEX IF NOT EXISTS events_kind ON events(dataset_id,kind);
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL,
            description TEXT, observed_at TEXT NOT NULL, notes TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evidence (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
            file_id TEXT NOT NULL REFERENCES files(id)
        );
        CREATE TABLE IF NOT EXISTS dossiers (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, fields TEXT NOT NULL,
            file_id TEXT REFERENCES files(id), extracted_text TEXT NOT NULL,
            reviewed INTEGER NOT NULL DEFAULT 0, demo INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY, action TEXT NOT NULL, entity_id TEXT NOT NULL,
            created_at TEXT NOT NULL, details TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('administrador','analista')),
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
            created_at TEXT NOT NULL, last_login TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at INTEGER NOT NULL, last_seen_at INTEGER NOT NULL, expires_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
        CREATE TABLE IF NOT EXISTS login_challenges (
            token_hash TEXT PRIMARY KEY, expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS auth_limits (
            bucket TEXT PRIMARY KEY, attempts INTEGER NOT NULL, window_started INTEGER NOT NULL
        );
        ''')
        # Additive migration: preserve existing source IDs, evidence and web fields.
        # Legacy NOT NULL url/observed_at use '' for absence; the API exposes null.
        db.execute('BEGIN IMMEDIATE')
        source_columns = {row['name'] for row in db.execute('PRAGMA table_info(sources)')}
        additions = {
            'source_type': "TEXT NOT NULL DEFAULT 'web'",
            'document_type': "TEXT NOT NULL DEFAULT ''",
            'provenance': "TEXT NOT NULL DEFAULT ''",
            'verification_status': "TEXT NOT NULL DEFAULT 'pendiente'",
            'demo_key': 'TEXT',
            'original_file_id': 'TEXT REFERENCES files(id)',
        }
        for name, definition in additions.items():
            if name not in source_columns:
                db.execute(f'ALTER TABLE sources ADD COLUMN {name} {definition}')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS sources_demo_key ON sources(demo_key) WHERE demo_key IS NOT NULL')


def as_dict(row):
    return dict(row) if row else None


def audit(db, action, entity_id, now, details=None):
    db.execute('INSERT INTO audit(action,entity_id,created_at,details) VALUES(?,?,?,?)',
               (action, entity_id, now, json.dumps(details or {}, ensure_ascii=False)))
