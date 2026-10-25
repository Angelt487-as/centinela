"""Prepare an actual hackathon reference; do not synthesize an internet evidence source."""
import hashlib
import hmac
import uuid
import zipfile
from pathlib import PurePosixPath

from .database import ROOT, audit, connection, initialize
from .documents import extract_document
from .files import MAX_BYTES, now, original_path, preserve, validate_file
from .sources import source_dict

BUNDLE_NAME = 'hakathon-20261024T164620Z-1-001.zip'
REFERENCE_ENTRY = 'hakathon/busqueda de fuentes abiertas/limitantes legales/LIMITANTES LEGALES PARA FUENTES ABIERTAS.docx'
DEMO_KEY = 'hackathon-osint-local-reference-v1'


def reference_from_archive():
    bundle = ROOT / BUNDLE_NAME
    if not bundle.is_file():
        raise FileNotFoundError('No se encontró el ZIP original del hackathon en la raíz del proyecto.')
    try:
        with zipfile.ZipFile(bundle) as archive:
            info = archive.getinfo(REFERENCE_ENTRY)
            if info.file_size > MAX_BYTES:
                raise ValueError('El documento de referencia supera el límite de tamaño.')
            with archive.open(info) as stream:
                content = stream.read(MAX_BYTES + 1)
    except (zipfile.BadZipFile, KeyError, OSError):
        raise ValueError('No se pudo leer el documento de fuentes abiertas del ZIP original. No se crearon datos sustitutos.') from None
    name = PurePosixPath(REFERENCE_ENTRY).name
    validate_file(name, content, {'.docx'})
    return name, content


def prepare_sources_demo():
    initialize()
    name, content = reference_from_archive()
    text, _ = extract_document(name, content)
    # The title comes from the original text, not a fabricated publication.
    title = next((line.strip() for line in text.splitlines() if line.strip()), '')
    if not title or len(title) > 200:
        raise ValueError('No se reconoció un título válido en el documento original.')
    checksum = hashlib.sha256(content).hexdigest()
    provenance = BUNDLE_NAME + ' · ' + REFERENCE_ENTRY
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('SELECT * FROM sources WHERE demo_key=?', (DEMO_KEY,)).fetchone()
        if existing:
            file = db.execute('SELECT * FROM files WHERE id=?', (existing['original_file_id'],)).fetchone()
            if not file or not hmac.compare_digest(file['sha256'], checksum):
                raise ValueError('El material del ZIP no coincide con la demostración existente. Se conservó el registro previo sin reemplazarlo.')
            try:
                with original_path(file).open('rb') as stream:
                    preserved = stream.read(MAX_BYTES + 1)
                if not hmac.compare_digest(hashlib.sha256(preserved).hexdigest(), checksum):
                    raise ValueError('La copia conservada cambió. No se reparó ni reemplazó automáticamente; revisa su integridad.')
            except OSError:
                raise ValueError('Falta el documento conservado de la demostración. No se creó otro registro ni se modificaron las fuentes existentes.') from None
            return source_dict(db, existing)
        file_id, digest = preserve(db, name, content)
        source_id, incorporated_at = uuid.uuid4().hex, now()
        description = 'Documento de instrucciones del hackathon sobre fijación digital forense, cálculo de hashes, privacidad y protección de datos personales.'
        notes = ('Material de referencia del hackathon; no es evidencia recolectada de internet. '
                 'El documento no proporciona URL pública ni fecha de consulta. '
                 'La fecha de incorporación corresponde a su carga local. '
                 'El cotejo SHA-256 acredita coincidencia de bytes con el ZIP, no vigencia normativa, veracidad ni validez jurídica del contenido.')
        # Empty legacy strings represent absence, and serialize as null in the API.
        db.execute('''INSERT INTO sources(id,title,url,description,observed_at,notes,created_at,
                      source_type,document_type,provenance,verification_status,demo_key,original_file_id)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                   (source_id, title, '', description, '', notes, incorporated_at,
                    'local_reference', 'DOCX', provenance, 'integridad_comprobada', DEMO_KEY, file_id))
        db.execute('INSERT INTO evidence VALUES(?,?,?)', (uuid.uuid4().hex, source_id, file_id))
        audit(db, 'referencia_hackathon_incorporada', source_id, incorporated_at, {'sha256': digest, 'source_type': 'local_reference'})
        return source_dict(db, db.execute('SELECT * FROM sources WHERE id=?', (source_id,)).fetchone())
