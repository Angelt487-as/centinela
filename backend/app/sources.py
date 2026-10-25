"""Source documents and their integrity, distinct from assertions about public content."""
import hashlib
import hmac

from fastapi import HTTPException

from .database import connection
from .documents import extract_document
from .files import MAX_BYTES, now, original_path


def source_dict(db, row):
    item = dict(row)
    item['is_demo'] = bool(item.pop('demo_key', None))
    item['url'] = item['url'] or None
    item['observed_at'] = item['observed_at'] or None
    item['evidence'] = [dict(r) for r in db.execute('''
        SELECT f.id,f.name,f.sha256,f.size,f.created_at FROM evidence e
        JOIN files f ON f.id=e.file_id WHERE e.source_id=? ORDER BY f.created_at,f.id
    ''', (row['id'],))]
    primary = next((r for r in item['evidence'] if r['id'] == item.get('original_file_id')), None)
    item['original_name'] = primary['name'] if primary else None
    return item


def get_source(source_id):
    with connection() as db:
        row = db.execute('SELECT * FROM sources WHERE id=?', (source_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'La fuente no existe.')
        return source_dict(db, row)


def source_document(source_id):
    """Return only the server-associated document. Never resolve client-supplied paths."""
    with connection() as db:
        source = db.execute('SELECT * FROM sources WHERE id=?', (source_id,)).fetchone()
        if not source:
            raise HTTPException(404, 'La fuente no existe.')
        if source['original_file_id']:
            file = db.execute('SELECT * FROM files WHERE id=?', (source['original_file_id'],)).fetchone()
        else:
            file = db.execute('''SELECT f.* FROM files f JOIN evidence e ON f.id=e.file_id
                                 WHERE e.source_id=? ORDER BY f.created_at,f.id LIMIT 1''', (source_id,)).fetchone()
        if not file:
            raise HTTPException(404, 'Este registro todavía no tiene un documento asociado.')
        source, file = dict(source), dict(file)
    try:
        with original_path(file).open('rb') as stream:
            content = stream.read(MAX_BYTES + 1)
    except OSError:
        raise HTTPException(404, 'El documento conservado no está disponible. No se sustituyó por otro archivo.') from None
    if len(content) > MAX_BYTES:
        raise HTTPException(413, 'El documento conservado supera el límite permitido.')
    return source, file, content


def document_preview(source_id):
    source, file, content = source_document(source_id)
    computed = hashlib.sha256(content).hexdigest()
    if not hmac.compare_digest(computed, file['sha256']):
        raise HTTPException(409, 'La copia conservada no coincide con su SHA-256 registrado. Revisa la integridad antes de consultar el documento.')
    if file['extension'] in {'.docx', '.pdf'}:
        text, _ = extract_document(file['name'], content)
    elif file['extension'] in {'.txt', '.csv'}:
        try:
            text = content.decode('utf-8-sig')
        except UnicodeError:
            text = content.decode('cp1252', errors='replace')
    else:
        raise HTTPException(415, 'No hay una vista de texto para este formato. Descarga el original desde sus evidencias.')
    return {'source_id': source_id, 'file_id': file['id'], 'name': file['name'],
            'document_type': file['extension'].lstrip('.').upper(), 'text': text,
            'sha256': computed,
            'notice': 'Vista de texto extraído del documento original; no reproduce su maquetación. El material de referencia no es una captura de una página de internet ni una validación jurídica de su contenido.'}


def document_integrity(source_id):
    source, file, content = source_document(source_id)
    computed = hashlib.sha256(content).hexdigest()
    archive_matches, archive_sha256 = None, None
    if source['demo_key']:
        from .source_demo import DEMO_KEY, reference_from_archive
        if source['demo_key'] == DEMO_KEY:
            try:
                _, original = reference_from_archive()
                archive_sha256 = hashlib.sha256(original).hexdigest()
                archive_matches = hmac.compare_digest(computed, archive_sha256)
            except (FileNotFoundError, ValueError):
                pass  # The retained document remains usable when the ZIP is temporarily absent.
    return {'source_id': source_id, 'file_id': file['id'], 'name': file['name'],
            'stored_sha256': file['sha256'], 'computed_sha256': computed,
            'matches': hmac.compare_digest(computed, file['sha256']),
            'archive_matches': archive_matches, 'archive_sha256': archive_sha256,
            'checked_at': now(),
            'notice': 'SHA-256 comprueba coincidencia de bytes. No acredita veracidad, vigencia normativa, autenticidad pública ni validez jurídica del contenido.'}
