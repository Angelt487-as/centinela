import csv
import hashlib
import io
import zipfile

import pytest
from fastapi import HTTPException

from backend.app.database import ROOT
from backend.app.files import validate_file
from backend.app.parsers import coordinate, parse_events, timestamp


def test_health_and_real_csv_roundtrip(client):
    assert client.get('/api/health').json()['status'] == 'ok'
    resources = client.get('/api/resources').json()['items']
    resource = next(r for r in resources if r['name'] == '6271218386.csv' and 'estructuracion' in r['folder'])
    response = client.post('/api/datasets/resource/' + resource['id'])
    assert response.status_code == 200
    dataset = response.json()
    assert dataset['row_count'] == 534
    assert dataset['metadata']['coordinates'] == 485
    assert dataset['metadata']['sheets'][0]['header_row'] == 8
    query = {'dataset_id': dataset['id']}
    summary = client.get('/api/stats', params=query).json()
    assert summary['total'] == 534
    assert sum(t['count'] for t in summary['kinds']) == 534
    page = client.get('/api/events', params={**query, 'page_size': 10}).json()
    assert len(page['items']) == 10 and page['total'] == 534
    kind = page['items'][0]['kind']
    filtered = client.get('/api/events', params={**query, 'kind': kind}).json()
    assert all(e['kind'] == kind for e in filtered['items'])
    assert filtered['total'] == next(x['count'] for x in summary['kinds'] if x['kind'] == kind)
    geo = client.get('/api/geo', params=query).json()
    assert geo['total'] == 485
    assert 'no son recorridos GPS' in geo['notice']
    assert all(-90 <= e['latitude'] <= 90 and -180 <= e['longitude'] <= 180 for e in geo['items'])
    graph = client.get('/api/graph', params=query).json()
    node_ids = {n['data']['id'] for n in graph['nodes']}
    assert all(e['data']['source'] in node_ids and e['data']['target'] in node_ids for e in graph['edges'])
    exported = client.get('/api/events/export', params=query)
    assert len(list(csv.reader(io.StringIO(exported.text.lstrip('\ufeff'))))) == 535
    assert client.post('/api/datasets/resource/' + resource['id']).json()['duplicate']
    assert client.get('/api/overview').json()['events'] == 534
    original = client.get('/api/files/' + dataset['file_id']).content
    assert hashlib.sha256(original).hexdigest() == dataset['sha256']
    assert client.get('/api/events', params={**query, 'date_from': '2026-12-31', 'date_to': '2026-01-01'}).status_code == 422


def test_all_original_data_files():
    csv_counts = []
    with zipfile.ZipFile(ROOT / 'hakathon-20261024T164620Z-1-001.zip') as bundle:
        names = [n for n in bundle.namelist() if '/estructuracion y analisis de datos/' in n and n.endswith(('.csv', '.xls'))]
        assert len(names) == 12
        for name in names:
            events, metadata = parse_events(name, bundle.read(name))
            assert events
            assert all(e['timestamp'] for e in events)
            if name.endswith('.csv'):
                csv_counts.append(len(events))
            else:
                assert metadata['selected_sheet'] == metadata['available_sheets'][0]
                assert len(metadata['available_sheets']) > 1
                # Excel dates stored at midnight must use their separate time column.
                raw = events[0]['raw']['values']
                if raw.get('Hora'):
                    assert events[0]['timestamp'].endswith(raw['Hora'])
        assert sum(csv_counts) == 22977


def test_encoding_separator_and_missing_values(client):
    content = 'Reporte autorizado\nTeléfono;Tipo;Número A;Número B;Fecha;Hora;LATITUD;LONGITUD\n001;VOZ ENTRANTE;001;002;24/10/2026;;28.5;-106.1\n'.encode('cp1252')
    result = client.post('/api/datasets/upload', files={'file': ('registros.csv', content, 'text/csv')})
    assert result.status_code == 200
    assert result.json()['metadata']['encoding'] == 'cp1252'
    event = client.get('/api/events', params={'dataset_id': result.json()['id']}).json()['items'][0]
    assert event['number_a'] == '001'
    assert event['duration'] is None
    assert event['timestamp'] == '2026-10-24'


def test_xlsx_import(client):
    from openpyxl import Workbook
    book = Workbook()
    book.active.append(['Telefono', 'Tipo', 'Numero A', 'Numero B', 'Fecha', 'Hora', 'LATITUD', 'LONGITUD'])
    book.active.append(['001', 'DATOS', '001', '002', '2026-10-24', '10:30:00', 28.5, -106.1])
    output = io.BytesIO()
    book.save(output)
    result = client.post('/api/datasets/upload', files={'file': ('registros.xlsx', output.getvalue())})
    assert result.status_code == 200
    assert result.json()['row_count'] == 1


@pytest.mark.parametrize('value,lat,expected', [('28°30\'00"N', True, 28.5), ('106°06\'00"W', False, -106.1), ('-106.1', False, -106.1), ('91', True, None), ('28°90\'00"', True, None), ('nan', True, None)])
def test_coordinates(value, lat, expected):
    assert coordinate(value, lat) == expected


def test_unsafe_uploads_and_origin(client):
    assert client.post('/api/datasets/upload', files={'file': ('../escape.csv', b'text')}).status_code == 400
    assert client.post('/api/datasets/upload', files={'file': ('fake.xls', b'not excel')}).status_code == 400
    assert client.post('/api/datasets/upload', files={'file': ('script.exe', b'text')}).status_code == 415
    assert client.post('/api/datasets/upload', files={'file': ('empty.csv', b'')}).status_code == 400
    assert client.post('/api/datasets/upload', files={'file': ('invalid.csv', b'a,b,c\n1,2,3')}).status_code == 422
    assert client.post('/api/dossiers/demo', headers={'Origin': 'https://untrusted.example'}).status_code == 403
    assert client.post('/api/datasets/resource/not-an-id').status_code == 404
    with pytest.raises(HTTPException) as error:
        validate_file('large.csv', b'a' * (25 * 1024 * 1024 + 1), {'.csv'})
    assert error.value.status_code == 413
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as z:
        z.writestr('word/document.xml', '<document/>')
        z.writestr('../outside', 'x')
    with pytest.raises(HTTPException):
        validate_file('unsafe.docx', buffer.getvalue(), {'.docx'})
