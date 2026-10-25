"""Integration checks for the prepared local reference, using the real hackathon ZIP."""
import csv
import hashlib
import io
import os
import sqlite3
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import PurePosixPath

from fastapi.testclient import TestClient

from backend.app.database import ROOT, connection, data_root, initialize
from backend.app.files import original_path
from backend.app.main import app
from backend.app.source_demo import prepare_sources_demo
from conftest import sign_in


BUNDLE = 'hakathon-20261024T164620Z-1-001.zip'
ENTRY = 'hakathon/busqueda de fuentes abiertas/limitantes legales/LIMITANTES LEGALES PARA FUENTES ABIERTAS.docx'
NAME = PurePosixPath(ENTRY).name
SHA256 = 'f13f12669877ee3c99b51ad0718770a925bd64fc17ade01cba02d4d9831e0107'


def original_document():
    with zipfile.ZipFile(ROOT / BUNDLE) as bundle:
        return bundle.read(ENTRY)


def csv_rows(response):
    assert response.status_code == 200
    return list(csv.DictReader(io.StringIO(response.text.lstrip('\ufeff'))))


def test_demo_uses_original_document_without_invented_web_metadata(client):
    before = datetime.now(timezone.utc)
    demo = prepare_sources_demo()
    after = datetime.now(timezone.utc)
    document = original_document()
    assert len(document) == 13486
    assert hashlib.sha256(document).hexdigest() == SHA256
    assert demo['title'] == 'LIMITANTES LEGALES PARA FUENTES ABIERTAS'
    assert demo['source_type'] == 'local_reference'
    assert demo['document_type'] == 'DOCX'
    assert demo['is_demo'] is True
    assert demo['url'] is None
    assert demo['observed_at'] is None
    assert demo['verification_status'] == 'integridad_comprobada'
    assert ENTRY in demo['provenance'] and BUNDLE in demo['provenance']
    incorporated = datetime.fromisoformat(demo['created_at'].replace('Z', '+00:00'))
    assert before <= incorporated <= after
    assert demo['description'] and demo['notes']
    assert not any(prefix in (demo['description'] + demo['notes']).lower() for prefix in ('http://', 'https://'))
    assert len(demo['evidence']) == 1
    evidence = demo['evidence'][0]
    assert evidence['name'] == NAME
    assert evidence['sha256'] == SHA256
    assert evidence['size'] == len(document)
    response = client.get('/api/files/' + evidence['id'])
    assert response.status_code == 200
    assert response.content == document
    detail = client.get('/api/sources/' + demo['id'])
    assert detail.status_code == 200
    assert detail.json()['id'] == demo['id']
    assert detail.json()['url'] is None and detail.json()['observed_at'] is None


def test_initialization_script_is_idempotent_and_preserves_registered_web_sources(client):
    web = {
        'title': 'Fuente web de regresión automatizada',
        'url': 'https://example.org/regresion',
        'description': 'Registro de prueba independiente de la referencia local.',
        'observed_at': '2026-10-24',
        'notes': 'No debe modificarse al preparar la demostración.',
    }
    response = client.post('/api/sources', json=web)
    assert response.status_code == 200
    web_id = response.json()['id']
    previous = next(s for s in client.get('/api/sources').json()['items'] if s['id'] == web_id)
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    script = ROOT / 'scripts' / 'cargar_demo_fuentes.py'
    first_run = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=env,
                               capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert first_run.returncode == 0, first_run.stderr
    first = next(s for s in client.get('/api/sources').json()['items'] if s['is_demo'])
    second_run = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=env,
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert second_run.returncode == 0, second_run.stderr
    same = prepare_sources_demo()
    items = client.get('/api/sources').json()['items']
    assert len(items) == 2
    assert len([s for s in items if s['is_demo']]) == 1
    assert same['id'] == first['id'] and same['created_at'] == first['created_at']
    assert same['evidence'][0]['id'] == first['evidence'][0]['id']
    assert next(s for s in items if s['id'] == web_id) == previous
    with connection() as db:
        assert db.execute('SELECT COUNT(*) FROM evidence WHERE source_id=?', (same['id'],)).fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM files WHERE sha256=?', (SHA256,)).fetchone()[0] == 1


def test_demo_survives_backend_restart_and_is_readable_by_both_roles(client, accounts):
    demo = prepare_sources_demo()
    file_id = demo['evidence'][0]['id']
    paths = ['/api/sources/' + demo['id'],
             '/api/sources/' + demo['id'] + '/document',
             '/api/sources/' + demo['id'] + '/integrity',
             '/api/sources/' + demo['id'] + '/export',
             '/api/files/' + file_id]
    for path in paths:
        assert client.get(path).status_code == 200
    initialize()
    # A new ASGI lifecycle and a fresh browser cookie jar exercise persisted SQLite state.
    with TestClient(app) as restarted:
        sign_in(restarted, accounts['analyst']['username'], accounts['analyst_password'])
        for path in paths:
            assert restarted.get(path).status_code == 200
        loaded = restarted.get('/api/sources/' + demo['id']).json()
        assert loaded['id'] == demo['id']
        assert loaded['created_at'] == demo['created_at']
        assert restarted.get('/api/files/' + file_id).content == original_document()


def test_demo_document_hash_and_ledger_require_authentication(client):
    demo = prepare_sources_demo()
    paths = ['/api/sources', '/api/sources/export', '/api/sources/' + demo['id'],
             '/api/sources/' + demo['id'] + '/document',
             '/api/sources/' + demo['id'] + '/integrity',
             '/api/sources/' + demo['id'] + '/export',
             '/api/files/' + demo['evidence'][0]['id']]
    with TestClient(app) as anonymous:
        for path in paths:
            response = anonymous.get(path)
            assert response.status_code == 401, path
            assert SHA256 not in response.text and NAME not in response.text
    csrf = client.headers.pop('X-CSRF-Token')
    try:
        assert client.post('/api/sources', json={}).status_code == 403
    finally:
        client.headers['X-CSRF-Token'] = csrf


def test_document_preview_and_integrity_come_from_preserved_bytes(client):
    demo = prepare_sources_demo()
    preview = client.get('/api/sources/' + demo['id'] + '/document')
    assert preview.status_code == 200
    data = preview.json()
    assert data['name'] == NAME and data['sha256'] == SHA256
    assert data['file_id'] == demo['evidence'][0]['id']
    assert 'LIMITANTES LEGALES PARA FUENTES ABIERTAS' in data['text']
    assert 'Fijación Digital Forense' in data['text']
    assert 'text' in data['notice'].lower()
    before = datetime.now(timezone.utc)
    integrity = client.get('/api/sources/' + demo['id'] + '/integrity')
    after = datetime.now(timezone.utc)
    assert integrity.status_code == 200
    verified = integrity.json()
    assert verified['stored_sha256'] == verified['computed_sha256'] == SHA256
    assert verified['matches'] is True and verified['archive_matches'] is True
    checked = datetime.fromisoformat(verified['checked_at'].replace('Z', '+00:00'))
    assert before <= checked <= after


def test_integrity_detects_tampering_without_repairing_or_claiming_a_match(client):
    demo = prepare_sources_demo()
    file_id = demo['evidence'][0]['id']
    with connection() as db:
        stored = db.execute('SELECT * FROM files WHERE id=?', (file_id,)).fetchone()
        path = original_path(stored)
    # This copy belongs to the per-test data directory, never to the original ZIP.
    assert path.is_relative_to(data_root())
    tampered = path.read_bytes() + b'\nQA-TAMPER'
    path.write_bytes(tampered)
    result = client.get('/api/sources/' + demo['id'] + '/integrity')
    assert result.status_code == 200
    integrity = result.json()
    assert integrity['matches'] is False
    assert integrity['stored_sha256'] == SHA256
    assert integrity['computed_sha256'] == hashlib.sha256(tampered).hexdigest()
    assert integrity['computed_sha256'] != SHA256
    assert path.read_bytes() == tampered
    assert hashlib.sha256(original_document()).hexdigest() == SHA256


def test_demo_export_has_no_public_url_or_consultation_date(client):
    demo = prepare_sources_demo()
    rows = csv_rows(client.get('/api/sources/' + demo['id'] + '/export'))
    assert len(rows) == 1
    row = rows[0]
    assert row['titulo'] == demo['title']
    assert row['url'] == '' and row['fecha_observacion'] == ''
    assert row['archivo_evidencia'] == NAME and row['sha256'] == SHA256
    assert ENTRY in str(row)
    assert any(value in str(row) for value in ('local_reference', 'Referencia local', 'referencia local'))
    global_rows = csv_rows(client.get('/api/sources/export'))
    assert any(r['sha256'] == SHA256 and r['url'] == '' for r in global_rows)


def test_legacy_sources_migrate_without_losing_existing_metadata(tmp_path, monkeypatch):
    directory = tmp_path / 'legacy'
    directory.mkdir()
    monkeypatch.setenv('CENTINELA_DATA_DIR', str(directory))
    original = ('legacy', 'Fuente previa', 'https://example.org/previa', 'Descripción previa',
                '2026-10-23', 'Notas previas', '2026-10-23T12:00:00+00:00')
    with sqlite3.connect(directory / 'centinela.sqlite3') as db:
        db.execute('''CREATE TABLE sources(id TEXT PRIMARY KEY,title TEXT NOT NULL,url TEXT NOT NULL,
                    description TEXT,observed_at TEXT NOT NULL,notes TEXT,created_at TEXT NOT NULL)''')
        db.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?)', original)
    initialize()
    first = prepare_sources_demo()
    initialize()
    second = prepare_sources_demo()
    with connection() as db:
        preserved = db.execute('SELECT id,title,url,description,observed_at,notes,created_at FROM sources WHERE id=?', ('legacy',)).fetchone()
        assert tuple(preserved) == original
        assert db.execute('SELECT COUNT(*) FROM sources').fetchone()[0] == 2
    assert first['id'] == second['id']
