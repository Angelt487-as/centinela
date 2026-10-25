import csv
import io
import math
import re
import unicodedata
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
from fastapi import HTTPException

MAX_ROWS = 150_000


def key(value):
    text = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]', '', text)


ALIASES = {
    'subject': ['telefono', 'telfono', 'linea', 'numeroobjetivo', 'numeroconsultado'],
    'kind': ['tipo', 'tipodeevento', 'tipollamada', 'tipodecomunicacion', 'tipointeraccion'],
    'number_a': ['numeroa', 'nmeroa', 'origen', 'numeroorigen', 'a', 'llamante'],
    'number_b': ['numerob', 'nmerob', 'destino', 'numerodestino', 'b', 'llamado'],
    'date': ['fecha', 'fechainicio', 'fechadeinicio', 'fechahora', 'datetime', 'timestamp'],
    'time': ['hora', 'horainicio', 'horadeinicio'],
    'duration': ['duracseg', 'duracion', 'duracionseg', 'duracionsegundos', 'duracionseg'],
    'imei': ['imei'], 'latitude': ['latitud', 'latitude', 'lat'],
    'longitude': ['longitud', 'longitude', 'lon', 'long'],
    'azimuth': ['azimuth', 'azimut'],
}
LOOKUP = {alias: field for field, aliases in ALIASES.items() for alias in aliases}


def scalar(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ''
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def coordinate(value, latitude=True):
    s = scalar(value).strip().upper().replace(',', '.')
    if not s or s in {'N/A', 'ND', '-', 'SIN DATOS'}:
        return None
    try:
        number = float(s)
    except ValueError:
        parts = re.findall(r'[-+]?\d+(?:\.\d+)?', s)
        if not 2 <= len(parts) <= 3:
            return None
        degrees, minutes = float(parts[0]), float(parts[1])
        seconds = float(parts[2]) if len(parts) == 3 else 0
        if not 0 <= minutes < 60 or not 0 <= seconds < 60:
            return None
        number = abs(degrees) + minutes / 60 + seconds / 3600
        if degrees < 0 or re.search(r'[SWO]', s):
            number = -number
    bound = 90 if latitude else 180
    return number if math.isfinite(number) and -bound <= number <= bound else None


def timestamp(date_value, time_value=''):
    s = scalar(date_value)
    if not s:
        return None
    parsed = None
    for fmt in ('%Y/%m/%d', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%Y%m%d'):
        try:
            parsed = datetime.strptime(s, fmt).date().isoformat()
            break
        except ValueError:
            pass
    if parsed is None:
        try:
            dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
            if ('T' in s or ' ' in s) and not scalar(time_value):
                return dt.isoformat(timespec='seconds')
            parsed = dt.date().isoformat()
        except ValueError:
            return None
    t = scalar(time_value)
    if not t:
        return parsed  # A missing hour is not an invented midnight.
    try:
        if re.fullmatch(r'0\.\d+', t):
            seconds = round(float(t) * 86400) % 86400
            t = str(timedelta(seconds=seconds))
        return parsed + 'T' + time.fromisoformat(t).isoformat(timespec='seconds')
    except ValueError:
        return None


def numeric(value):
    try:
        n = float(scalar(value).replace(',', '.'))
        return n if math.isfinite(n) else None
    except ValueError:
        return None


def parse_table(rows, sheet):
    header = None
    for i, row in enumerate(rows[:80]):
        mapped = {LOOKUP[key(v)]: j for j, v in enumerate(row) if key(v) in LOOKUP}
        for j, value in enumerate(row):
            if 'latitud' in key(value) and 'longitud' in key(value) and j + 1 < len(row) and not scalar(row[j + 1]):
                mapped.update(latitude=j, longitude=j + 1)
        if 'date' in mapped and len(mapped) >= 4 and ('number_a' in mapped or 'subject' in mapped):
            header = (i, row, mapped)
            break
    if not header:
        return [], {'sheet': sheet, 'error': 'No se reconocieron los encabezados.'}
    index, labels, mapping = header
    events, issues = [], Counter()
    for row_index, row in enumerate(rows[index + 1:], index + 2):
        if not any(scalar(v) for v in row):
            continue
        def get(field):
            pos = mapping.get(field)
            return row[pos] if pos is not None and pos < len(row) else ''
        if key(get('date')) in ALIASES['date']:
            issues['encabezados_repetidos'] += 1
            continue
        ts = timestamp(get('date'), get('time'))
        if not ts:
            issues['filas_sin_fecha_valida'] += 1
            continue
        lat, lon = coordinate(get('latitude')), coordinate(get('longitude'), False)
        if lat is None or lon is None or (lat == 0 and lon == 0):
            lat, lon = None, None
            issues['eventos_sin_coordenadas_validas'] += 1
        dur = numeric(get('duration'))
        if dur is not None and dur < 0:
            dur = None
            issues['duraciones_invalidas'] += 1
        az = numeric(get('azimuth'))
        if az is not None and not 0 <= az <= 360:
            az = None
        events.append({
            'subject': scalar(get('subject')), 'kind': scalar(get('kind')) or 'Sin tipo',
            'number_a': scalar(get('number_a')), 'number_b': scalar(get('number_b')),
            'timestamp': ts, 'duration': dur, 'imei': scalar(get('imei')),
            'latitude': lat, 'longitude': lon, 'azimuth': az,
            'raw': {'sheet': sheet, 'row': row_index,
                    'values': {scalar(label) or f'col_{j+1}': scalar(row[j]) if j < len(row) else ''
                               for j, label in enumerate(labels)}},
        })
    return events, {'sheet': sheet, 'header_row': index + 1, 'columns': [scalar(c) for c in labels],
                    'issues': dict(issues), 'accepted': len(events)}


def parse_events(name, content):
    ext = Path(name).suffix.lower()
    sheets = []
    metadata = {'format': ext, 'sheets': [], 'warnings': []}
    try:
        if ext == '.csv':
            text = None
            encodings = ('utf-16',) if content.startswith((b'\xff\xfe', b'\xfe\xff')) else ('utf-8-sig', 'cp1252', 'latin1')
            for encoding in encodings:
                try:
                    text = content.decode(encoding)
                    metadata['encoding'] = encoding
                    break
                except UnicodeError:
                    continue
            if text is None:
                raise ValueError('encoding')
            # Delimiter voting tolerates metadata lines of different widths.
            candidates = []
            for separator in (',', ';', '\t', '|'):
                preview = list(csv.reader(io.StringIO(text[:30000]), delimiter=separator))
                score = max((len([v for v in row if key(v) in LOOKUP]) for row in preview[:80]), default=0)
                candidates.append((score, separator))
            separator = max(candidates, key=lambda x: x[0])[1]
            rows = list(csv.reader(io.StringIO(text), delimiter=separator))
            metadata['delimiter'] = separator
            sheets = [('CSV', rows)]
        else:
            engine = 'xlrd' if ext == '.xls' else 'openpyxl'
            with pd.ExcelFile(io.BytesIO(content), engine=engine) as book:
                if len(book.sheet_names) > 30:
                    raise HTTPException(400, 'El libro supera el límite de 30 hojas.')
                for sheet in book.sheet_names:
                    frame = pd.read_excel(book, sheet_name=sheet, header=None, dtype=object, nrows=MAX_ROWS + 81)
                    sheets.append((sheet, frame.values.tolist()))
        if sum(len(rows) for _, rows in sheets) > MAX_ROWS + 80 * len(sheets):
            raise HTTPException(413, 'El archivo supera el límite de 150,000 filas.')
        events = []
        metadata['available_sheets'] = [s for s, _ in sheets]
        for name_, rows in sheets:
            parsed, report = parse_table(rows, name_)
            metadata['sheets'].append(report)
            if parsed:
                events = parsed
                metadata['selected_sheet'] = name_
                break
        if not events:
            raise HTTPException(422, 'No se encontraron eventos con encabezados y fechas válidos. Revisa el formato del archivo.')
        if len(events) > MAX_ROWS:
            raise HTTPException(413, 'El archivo supera el límite de 150,000 eventos.')
        metadata['warnings'] = [f"{k}: {v}" for s in metadata['sheets'] for k, v in s.get('issues', {}).items()]
        if len(sheets) > 1:
            metadata['warnings'].insert(0, 'Se importó únicamente la primera hoja con eventos reconocibles: ' + metadata['selected_sheet'] + '. Las otras hojas se conservaron en el original; no se sumaron sus posibles copias.')
        metadata['coordinates'] = sum(e['latitude'] is not None for e in events)
        return events, metadata
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, 'No se pudo leer el archivo de datos. Verifica que no esté dañado, cifrado o protegido.') from None
