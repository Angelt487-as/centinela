import hashlib
import io
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from fastapi import HTTPException, UploadFile

from .database import ROOT, data_root

MAX_BYTES = 25 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_file(name: str, content: bytes, allowed: set[str]):
    # Neither POSIX nor Windows paths supplied by clients are accepted.
    if not name or '/' in name or '\\' in name or '\x00' in name or len(name) > 240:
        raise HTTPException(400, 'El nombre del archivo no es válido. Usa un nombre sin carpetas.')
    ext = Path(name).suffix.lower()
    if ext not in allowed:
        raise HTTPException(415, 'Formato no permitido. Formatos aceptados: ' + ', '.join(sorted(allowed)))
    if not content:
        raise HTTPException(400, 'El archivo está vacío.')
    if len(content) > MAX_BYTES:
        raise HTTPException(413, 'El archivo supera el límite de 25 MB.')
    signatures = {'.pdf': b'%PDF-', '.xls': bytes.fromhex('d0cf11e0a1b11ae1'), '.png': b'\x89PNG\r\n\x1a\n', '.jpg': b'\xff\xd8\xff', '.jpeg': b'\xff\xd8\xff'}
    if ext in signatures and not content.startswith(signatures[ext]):
        raise HTTPException(400, 'El contenido no coincide con el formato del archivo.')
    if ext in {'.docx', '.xlsx'}:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                entries = z.infolist()
                if len(entries) > 3000 or sum(i.file_size for i in entries) > 100 * 1024 * 1024:
                    raise ValueError('size')
                for item in entries:
                    parts = PurePosixPath(item.filename.replace('\\', '/')).parts
                    if '..' in parts or item.filename.startswith(('/', '\\')) or ':' in item.filename:
                        raise ValueError('path')
                    if 'vbaproject' in item.filename.lower() or '/embeddings/' in item.filename.lower():
                        raise ValueError('embedded executable')
                required = 'word/document.xml' if ext == '.docx' else 'xl/workbook.xml'
                if required not in z.namelist():
                    raise ValueError('structure')
        except (zipfile.BadZipFile, ValueError):
            raise HTTPException(400, 'El documento está dañado o contiene una estructura no admitida.') from None
    if ext in {'.txt', '.csv'} and b'\x00' in content[:8192] and not content.startswith((b'\xff\xfe', b'\xfe\xff')):
        raise HTTPException(400, 'El archivo de texto contiene datos binarios no admitidos.')
    return ext


async def read_upload(file: UploadFile, allowed: set[str]):
    content = await file.read(MAX_BYTES + 1)
    await file.close()
    name = file.filename or ''
    validate_file(name, content, allowed)
    return name, content


def preserve(db, name, content):
    ext = Path(name).suffix.lower()
    file_id = uuid.uuid4().hex
    digest = hashlib.sha256(content).hexdigest()
    (data_root() / 'originals' / (file_id + ext)).write_bytes(content)
    db.execute('INSERT INTO files VALUES(?,?,?,?,?,?)', (file_id, name, digest, ext, len(content), now()))
    return file_id, digest


def original_path(row):
    return data_root() / 'originals' / (row['id'] + row['extension'])


def resources():
    bundle = ROOT / 'hakathon-20261024T164620Z-1-001.zip'
    if not bundle.exists():
        return []
    items = []
    with zipfile.ZipFile(bundle) as z:
        for entry in z.infolist():
            path = PurePosixPath(entry.filename)
            ext = path.suffix.lower()
            if ext not in {'.csv', '.xls', '.xlsx', '.docx', '.pdf'}:
                continue
            group = 'datos' if ext in {'.csv', '.xls', '.xlsx'} else 'fichas' if '/automatizacion de fichas' in entry.filename else 'referencias'
            items.append({'id': hashlib.sha256(entry.filename.encode('utf-8')).hexdigest()[:24],
                          'name': path.name, 'folder': str(path.parent), 'group': group,
                          'size': entry.file_size, 'extension': ext})
    return items


def resource_bytes(resource_id, group):
    item = next((r for r in resources() if r['id'] == resource_id and r['group'] == group), None)
    if not item:
        raise HTTPException(404, 'El recurso solicitado no existe en esta categoría.')
    if item['size'] > MAX_BYTES:
        raise HTTPException(413, 'El recurso supera el límite de 25 MB.')
    with zipfile.ZipFile(ROOT / 'hakathon-20261024T164620Z-1-001.zip') as z:
        with z.open(item['folder'] + '/' + item['name']) as stream:
            content = stream.read(MAX_BYTES + 1)
    validate_file(item['name'], content, {item['extension']})
    return item['name'], content
