import csv
import hashlib
import io
import ipaddress
import json
import uuid
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .database import ROOT, as_dict, audit, connection, initialize
from .documents import FIELD_LABELS, export_dossier, extract_document
from .files import now, original_path, preserve, read_upload, resource_bytes, resources
from .parsers import parse_events
from .auth import allowed_origins, authenticate_request, clear_cookie, router as auth_router
from .sources import document_integrity, document_preview, get_source, source_dict


@asynccontextmanager
async def lifespan(app):
    initialize()
    yield


app = FastAPI(title='Centinela 360', version='1.1.0', lifespan=lifespan)
app.include_router(auth_router)
ORIGINS = allowed_origins()
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_credentials=True,
                   allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Content-Type', 'X-CSRF-Token'],
                   expose_headers=['X-Session-Expires-At'])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])


@app.middleware('http')
async def local_protection(request: Request, call_next):
    length = request.headers.get('content-length', '')
    if length.isdigit() and int(length) > 26 * 1024 * 1024:
        return JSONResponse({'detail': 'La carga supera el límite permitido de 25 MB por archivo.'}, status_code=413)
    if request.method not in {'GET', 'HEAD', 'OPTIONS'} and request.headers.get('origin') and request.headers['origin'] not in allowed_origins():
        return JSONResponse({'detail': 'Origen no autorizado para modificar datos locales.'}, status_code=403)
    if request.method not in {'GET', 'HEAD', 'OPTIONS'} and request.headers.get('sec-fetch-site') == 'cross-site':
        return JSONResponse({'detail': 'Solicitud de un sitio no autorizado.'}, status_code=403)
    try:
        authenticate_request(request)
    except HTTPException as error:
        response = JSONResponse({'detail': error.detail}, status_code=error.status_code, headers=error.headers)
        if error.status_code == 401:
            clear_cookie(response, request)
    else:
        response = await call_next(request)
    deadline = getattr(request.state, 'session_deadline', None)
    if deadline:
        response.headers['X-Session-Expires-At'] = str(deadline)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Validation errors must not echo the supplied personal data.
    return JSONResponse({'detail': 'Revisa los campos obligatorios, las fechas y el formato de los datos.'}, status_code=422)


@app.get('/api/health')
def health():
    with connection() as db:
        db.execute('SELECT 1')
    return {'status': 'ok', 'name': 'Centinela 360', 'mode': 'local'}


@app.get('/api/resources')
def list_resources():
    return {'items': resources()}


@app.get('/api/overview')
def overview():
    with connection() as db:
        return {'datasets': db.execute('SELECT COUNT(*) FROM datasets').fetchone()[0],
                'events': db.execute('SELECT COUNT(*) FROM events').fetchone()[0],
                'geographic_events': db.execute('SELECT COUNT(*) FROM events WHERE latitude IS NOT NULL').fetchone()[0],
                'sources': db.execute('SELECT COUNT(*) FROM sources').fetchone()[0],
                'evidence': db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0],
                'dossiers': db.execute('SELECT COUNT(*) FROM dossiers').fetchone()[0],
                'recent': [dict(r) for r in db.execute('SELECT action,created_at FROM audit ORDER BY id DESC LIMIT 6')]}


def import_dataset(name, content):
    digest = hashlib.sha256(content).hexdigest()
    with connection() as db:
        previous = db.execute('SELECT * FROM datasets WHERE sha256=?', (digest,)).fetchone()
        if previous:
            return {**dataset_dict(previous), 'duplicate': True}
    events, metadata = parse_events(name, content)
    dataset_id = uuid.uuid4().hex
    with connection() as db:
        # Also check inside the write transaction for concurrent imports.
        db.execute('BEGIN IMMEDIATE')
        previous = db.execute('SELECT * FROM datasets WHERE sha256=?', (digest,)).fetchone()
        if previous:
            return {**dataset_dict(previous), 'duplicate': True}
        file_id, _ = preserve(db, name, content)
        created = now()
        db.execute('INSERT INTO datasets VALUES(?,?,?,?,?,?,?)',
                   (dataset_id, file_id, name, digest, created, len(events), json.dumps(metadata, ensure_ascii=False)))
        db.executemany('''INSERT INTO events(dataset_id,subject,kind,number_a,number_b,timestamp,
                          duration,imei,latitude,longitude,azimuth,raw) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                       [(dataset_id, e['subject'], e['kind'], e['number_a'], e['number_b'], e['timestamp'],
                         e['duration'], e['imei'], e['latitude'], e['longitude'], e['azimuth'],
                         json.dumps(e['raw'], ensure_ascii=False)) for e in events])
        audit(db, 'datos_importados', dataset_id, created, {'rows': len(events)})
        return dataset_dict(db.execute('SELECT * FROM datasets WHERE id=?', (dataset_id,)).fetchone())


def dataset_dict(row):
    result = dict(row)
    result['metadata'] = json.loads(result['metadata'])
    return result


@app.get('/api/datasets')
def datasets():
    with connection() as db:
        return {'items': [dataset_dict(r) for r in db.execute('SELECT * FROM datasets ORDER BY created_at DESC')]}


@app.post('/api/datasets/upload')
async def upload_dataset(file: UploadFile = File(...)):
    name, content = await read_upload(file, {'.csv', '.xls', '.xlsx'})
    return import_dataset(name, content)


@app.post('/api/datasets/resource/{resource_id}')
def dataset_resource(resource_id: str):
    return import_dataset(*resource_bytes(resource_id, 'datos'))


def event_query(dataset_id, number='', kind='', date_from='', date_to=''):
    conditions, params = ['dataset_id=?'], [dataset_id]
    with connection() as db:
        if not db.execute('SELECT id FROM datasets WHERE id=?', (dataset_id,)).fetchone():
            raise HTTPException(404, 'Selecciona un archivo importado válido.')
    if number:
        conditions.append('(instr(subject,?)>0 OR instr(number_a,?)>0 OR instr(number_b,?)>0)')
        params.extend([number] * 3)
    if kind:
        conditions.append('kind=?')
        params.append(kind)
    for value in (date_from, date_to):
        if value:
            try:
                date.fromisoformat(value)
            except ValueError:
                raise HTTPException(422, 'Usa fechas válidas en formato AAAA-MM-DD.') from None
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, 'La fecha inicial debe ser anterior o igual a la fecha final.')
    if date_from:
        conditions.append('substr(timestamp,1,10)>=?')
        params.append(date_from)
    if date_to:
        conditions.append('substr(timestamp,1,10)<=?')
        params.append(date_to)
    return ' AND '.join(conditions), params


@app.get('/api/events')
def events(dataset_id: str, number: str = '', kind: str = '', date_from: str = '', date_to: str = '',
           page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    where, params = event_query(dataset_id, number, kind, date_from, date_to)
    with connection() as db:
        total = db.execute('SELECT COUNT(*) FROM events WHERE ' + where, params).fetchone()[0]
        rows = db.execute('SELECT * FROM events WHERE ' + where + ' ORDER BY timestamp,id LIMIT ? OFFSET ?',
                          [*params, page_size, (page - 1) * page_size])
        items = []
        for row in rows:
            item = dict(row)
            item['raw'] = json.loads(item['raw'])
            items.append(item)
        return {'items': items, 'total': total, 'page': page, 'page_size': page_size}


@app.get('/api/stats')
def stats(dataset_id: str, number: str = '', kind: str = '', date_from: str = '', date_to: str = ''):
    where, params = event_query(dataset_id, number, kind, date_from, date_to)
    with connection() as db:
        summary = dict(db.execute('''SELECT COUNT(*) AS total, COUNT(duration) AS durations_known,
                    SUM(duration) AS duration_seconds, COUNT(latitude) AS geographic_events,
                    MIN(timestamp) AS first_event, MAX(timestamp) AS last_event FROM events WHERE ''' + where, params).fetchone())
        summary['kinds'] = [dict(r) for r in db.execute('SELECT kind,COUNT(*) AS count FROM events WHERE ' + where + ' GROUP BY kind ORDER BY count DESC', params)]
        summary['daily'] = [dict(r) for r in db.execute('SELECT substr(timestamp,1,10) AS date,COUNT(*) AS count FROM events WHERE ' + where + ' GROUP BY substr(timestamp,1,10) ORDER BY date', params)]
        summary['unique_numbers'] = db.execute('SELECT COUNT(DISTINCT n) FROM (SELECT number_a n FROM events WHERE ' + where + ' UNION SELECT number_b n FROM events WHERE ' + where + ") WHERE n<>''", params + params).fetchone()[0]
        return summary


def csv_response(rows, columns, filename):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(columns)
    for row in rows:
        # Prevent exported text from becoming a spreadsheet formula.
        writer.writerow([("'" + str(v)) if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else '' if v is None else v for v in row])
    return Response('\ufeff' + stream.getvalue(), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@app.get('/api/events/export')
def export_events(dataset_id: str, number: str = '', kind: str = '', date_from: str = '', date_to: str = ''):
    where, params = event_query(dataset_id, number, kind, date_from, date_to)
    columns = ['subject', 'kind', 'number_a', 'number_b', 'timestamp', 'duration', 'imei', 'latitude', 'longitude', 'azimuth']
    with connection() as db:
        rows = db.execute('SELECT ' + ','.join(columns) + ' FROM events WHERE ' + where + ' ORDER BY timestamp,id', params).fetchall()
    return csv_response(rows, ['telefono', 'tipo', 'numero_a', 'numero_b', 'fecha_hora', 'duracion_seg', 'imei', 'latitud', 'longitud', 'azimut'], 'centinela-eventos.csv')


@app.get('/api/graph')
def graph(dataset_id: str, number: str = '', kind: str = '', date_from: str = '', date_to: str = ''):
    where, params = event_query(dataset_id, number, kind, date_from, date_to)
    with connection() as db:
        rows = db.execute('''SELECT number_a,number_b,COUNT(*) AS weight FROM events WHERE ''' + where +
                          " AND number_a<>'' AND number_b<>'' GROUP BY number_a,number_b ORDER BY weight DESC,number_a,number_b LIMIT 101", params).fetchall()
    truncated = len(rows) > 100
    rows = rows[:100]
    numbers = sorted({r[k] for r in rows for k in ('number_a', 'number_b')})
    ids = {n: f'n{i}' for i, n in enumerate(numbers)}
    return {'nodes': [{'data': {'id': ids[n], 'label': n}} for n in numbers],
            'edges': [{'data': {'id': f'e{i}', 'source': ids[r['number_a']], 'target': ids[r['number_b']], 'weight': r['weight']}} for i, r in enumerate(rows)],
            'truncated': truncated, 'limit': 100,
            'description': 'Interacciones observadas entre los identificadores A y B. Pueden incluir teléfonos y servicios. No implica relaciones personales.'}


@app.get('/api/geo')
def geo(dataset_id: str, number: str = '', kind: str = '', date_from: str = '', date_to: str = '', limit: int = Query(500, ge=1, le=2000)):
    where, params = event_query(dataset_id, number, kind, date_from, date_to)
    with connection() as db:
        total = db.execute('SELECT COUNT(*) FROM events WHERE ' + where + ' AND latitude IS NOT NULL', params).fetchone()[0]
        items = [dict(r) for r in db.execute('''SELECT id,subject,kind,timestamp,latitude,longitude,azimuth FROM events WHERE ''' + where +
                                            ' AND latitude IS NOT NULL ORDER BY timestamp,id LIMIT ?', [*params, limit])]
        antennas = [dict(r) for r in db.execute('''SELECT latitude,longitude,azimuth,COUNT(*) AS connections,COUNT(DISTINCT subject) AS observed_lines
                        FROM events WHERE ''' + where + ' AND latitude IS NOT NULL GROUP BY latitude,longitude,azimuth ORDER BY connections DESC LIMIT 2000', params)]
    return {'items': items, 'antennas': antennas, 'total': total, 'limit': limit, 'truncated': total > limit,
            'notice': 'Conexiones cronológicas ilustrativas; no son recorridos GPS comprobados. Las ubicaciones corresponden a coordenadas informadas por la fuente.'}


@app.get('/api/geo/export')
def export_geo(dataset_id: str, number: str = '', kind: str = '', date_from: str = '', date_to: str = ''):
    where, params = event_query(dataset_id, number, kind, date_from, date_to)
    with connection() as db:
        rows = db.execute('SELECT timestamp,subject,kind,latitude,longitude,azimuth FROM events WHERE ' + where + ' AND latitude IS NOT NULL ORDER BY timestamp,id', params).fetchall()
    return csv_response(rows, ['fecha_hora', 'linea', 'tipo', 'latitud_fuente', 'longitud_fuente', 'azimut'], 'centinela-geografia.csv')


class SourceInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    source_type: Literal['web', 'local_reference'] = 'web'
    url: HttpUrl | None = None
    description: str = Field(default='', max_length=4000)
    observed_at: date | None = None
    notes: str = Field(default='', max_length=8000)
    document_type: str = Field(default='', max_length=80)
    provenance: str = Field(default='', max_length=2000)

    @field_validator('title')
    @classmethod
    def title_not_blank(cls, v):
        if not v.strip():
            raise ValueError('blank')
        return v.strip()

    @field_validator('url')
    @classmethod
    def public_url(cls, v):
        if v is None:
            return None
        host = v.host or ''
        if v.username or v.password or host.lower() in {'localhost', 'localhost.localdomain'}:
            raise ValueError('not public')
        try:
            if not ipaddress.ip_address(host.strip('[]')).is_global:
                raise ValueError('not public')
        except ValueError as exc:
            if str(exc) == 'not public':
                raise
        return v

    @model_validator(mode='after')
    def source_fields(self):
        if self.source_type == 'web' and (self.url is None or self.observed_at is None):
            raise ValueError('Las fuentes web requieren URL y fecha de consulta.')
        if self.source_type == 'local_reference':
            if self.url is not None or self.observed_at is not None:
                raise ValueError('Una referencia local no debe atribuirse una URL o fecha de consulta web.')
            if not self.document_type.strip() or not self.provenance.strip():
                raise ValueError('Una referencia local requiere tipo de documento y procedencia.')
        return self


@app.post('/api/sources')
def create_source(value: SourceInput):
    id_ = uuid.uuid4().hex
    with connection() as db:
        db.execute('''INSERT INTO sources(id,title,url,description,observed_at,notes,created_at,
                      source_type,document_type,provenance) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                   (id_, value.title, str(value.url) if value.url else '', value.description,
                    str(value.observed_at) if value.observed_at else '', value.notes, now(),
                    value.source_type, value.document_type, value.provenance))
        audit(db, 'fuente_registrada' if value.source_type == 'web' else 'referencia_local_registrada', id_, now())
    return {'id': id_}


@app.get('/api/sources')
def sources():
    with connection() as db:
        return {'items': [source_dict(db, row) for row in db.execute('SELECT * FROM sources ORDER BY created_at DESC')]}


@app.post('/api/sources/{source_id}/evidence')
async def attach_evidence(source_id: str, file: UploadFile = File(...)):
    name, content = await read_upload(file, {'.pdf', '.docx', '.png', '.jpg', '.jpeg', '.txt', '.csv'})
    with connection() as db:
        if not db.execute('SELECT id FROM sources WHERE id=?', (source_id,)).fetchone():
            raise HTTPException(404, 'La fuente no existe.')
        file_id, digest = preserve(db, name, content)
        db.execute('INSERT INTO evidence VALUES(?,?,?)', (uuid.uuid4().hex, source_id, file_id))
        audit(db, 'evidencia_conservada', source_id, now(), {'sha256': digest})
    return {'id': file_id, 'sha256': digest, 'name': name}


@app.get('/api/sources/export')
def export_sources():
    return sources_csv()


def sources_csv(source_id=None):
    condition = ' WHERE s.id=?' if source_id else ''
    params = (source_id,) if source_id else ()
    with connection() as db:
        if source_id and not db.execute('SELECT id FROM sources WHERE id=?', (source_id,)).fetchone():
            raise HTTPException(404, 'La fuente no existe.')
        rows = db.execute('''SELECT s.title,s.url,s.description,s.observed_at,s.notes,f.name,f.sha256,f.created_at
                            ,s.source_type,s.document_type,s.provenance,s.created_at,s.verification_status,
                            CASE WHEN s.demo_key IS NULL THEN 'no' ELSE 'si' END
                            FROM sources s LEFT JOIN evidence e ON e.source_id=s.id LEFT JOIN files f ON f.id=e.file_id'''
                          + condition + ' ORDER BY s.created_at DESC,f.created_at', params).fetchall()
    columns = ['titulo', 'url', 'descripcion', 'fecha_observacion', 'notas', 'archivo_evidencia', 'sha256', 'fecha_conservacion',
               'tipo_fuente', 'tipo_documento', 'procedencia', 'fecha_incorporacion', 'estado_verificacion', 'demostracion']
    return csv_response(rows, columns, 'centinela-bitacora.csv')


@app.get('/api/sources/{source_id}')
def source_detail(source_id: str):
    return get_source(source_id)


@app.get('/api/sources/{source_id}/document')
def source_document_preview(source_id: str):
    return document_preview(source_id)


@app.get('/api/sources/{source_id}/integrity')
def source_integrity(source_id: str):
    return document_integrity(source_id)


@app.get('/api/sources/{source_id}/export')
def export_one_source(source_id: str):
    return sources_csv(source_id)


@app.get('/api/files/{file_id}')
def download_original(file_id: str):
    with connection() as db:
        row = db.execute('SELECT * FROM files WHERE id=?', (file_id,)).fetchone()
        if not row or not original_path(row).is_file():
            raise HTTPException(404, 'El archivo conservado no está disponible.')
        return FileResponse(original_path(row), filename=row['name'], media_type='application/octet-stream')


def dossier_dict(row):
    item = dict(row)
    item['fields'] = json.loads(item['fields'])
    item['reviewed'] = bool(item['reviewed'])
    item['demo'] = bool(item['demo'])
    item['missing'] = [label for key_, label in FIELD_LABELS.items() if not item['fields'].get(key_, '').strip()]
    return item


def import_dossier(name, content):
    text, fields = extract_document(name, content)
    id_ = uuid.uuid4().hex
    with connection() as db:
        file_id, _ = preserve(db, name, content)
        db.execute('INSERT INTO dossiers VALUES(?,?,?,?,?,?,?,?)',
                   (id_, name, json.dumps(fields, ensure_ascii=False), file_id, text, 0, 0, now()))
        audit(db, 'ficha_importada', id_, now())
        return dossier_dict(db.execute('SELECT * FROM dossiers WHERE id=?', (id_,)).fetchone())


@app.get('/api/dossiers')
def dossiers():
    with connection() as db:
        return {'items': [dossier_dict(r) for r in db.execute('SELECT * FROM dossiers ORDER BY updated_at DESC')]}


@app.post('/api/dossiers/upload')
async def upload_dossier(file: UploadFile = File(...)):
    return import_dossier(*await read_upload(file, {'.pdf', '.docx'}))


@app.post('/api/dossiers/resource/{resource_id}')
def dossier_resource(resource_id: str):
    return import_dossier(*resource_bytes(resource_id, 'fichas'))


@app.post('/api/dossiers/demo')
def demo_dossier():
    id_ = uuid.uuid4().hex
    fields = {k: '' for k in FIELD_LABELS}
    fields.update(name='Persona de demostración', birth_date='1990-01-01',
                  nationality='Dato ficticio', notes='Ficha completamente ficticia para probar el formulario y la exportación. Sin validez documental.')
    with connection() as db:
        db.execute('INSERT INTO dossiers VALUES(?,?,?,?,?,?,?,?)',
                   (id_, 'Demostración ficticia', json.dumps(fields, ensure_ascii=False), None, 'Ejemplo ficticio. No corresponde a una persona real.', 0, 1, now()))
        audit(db, 'demostracion_creada', id_, now())
        return dossier_dict(db.execute('SELECT * FROM dossiers WHERE id=?', (id_,)).fetchone())


class DossierInput(BaseModel):
    fields: dict[str, str]
    reviewed: bool = False

    @field_validator('fields')
    @classmethod
    def check_fields(cls, v):
        if set(v) - set(FIELD_LABELS) or any(len(value) > 10000 for value in v.values()):
            raise ValueError('fields')
        return {key_: v.get(key_, '').strip() for key_ in FIELD_LABELS}


@app.put('/api/dossiers/{dossier_id}')
def update_dossier(dossier_id: str, value: DossierInput):
    if value.reviewed and not value.fields.get('name', '').strip():
        raise HTTPException(422, 'Completa el nombre antes de confirmar la revisión.')
    with connection() as db:
        if not db.execute('SELECT id FROM dossiers WHERE id=?', (dossier_id,)).fetchone():
            raise HTTPException(404, 'La ficha no existe.')
        db.execute('UPDATE dossiers SET fields=?,reviewed=?,updated_at=? WHERE id=?',
                   (json.dumps(value.fields, ensure_ascii=False), int(value.reviewed), now(), dossier_id))
        audit(db, 'ficha_revisada' if value.reviewed else 'borrador_guardado', dossier_id, now())
        return dossier_dict(db.execute('SELECT * FROM dossiers WHERE id=?', (dossier_id,)).fetchone())


@app.get('/api/dossiers/{dossier_id}/export/{format_}')
def download_dossier(dossier_id: str, format_: Literal['docx', 'pdf']):
    with connection() as db:
        row = db.execute('SELECT * FROM dossiers WHERE id=?', (dossier_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'La ficha no existe.')
    if not row['reviewed']:
        raise HTTPException(409, 'Confirma la revisión humana y guarda la ficha antes de exportar.')
    fields = json.loads(row['fields'])
    content = export_dossier(row, fields, format_)
    media = 'application/pdf' if format_ == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return Response(content, media_type=media, headers={'Content-Disposition': f'attachment; filename="centinela-ficha.{format_}"'})
