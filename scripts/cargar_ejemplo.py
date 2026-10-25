"""Importa un archivo real del ZIP y crea una ficha ficticia etiquetada, sin duplicarlos."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.database import connection, initialize
from backend.app.files import resource_bytes, resources
from backend.app.main import demo_dossier, import_dataset

initialize()
resource = next((r for r in resources() if r['name'] == '6271218386.csv' and 'estructuracion' in r['folder']), None)
if not resource:
    raise SystemExit('No se encontró el CSV de ejemplo en el ZIP original.')
dataset = import_dataset(*resource_bytes(resource['id'], 'datos'))
with connection() as db:
    has_demo = db.execute('SELECT id FROM dossiers WHERE demo=1 LIMIT 1').fetchone()
if not has_demo:
    demo_dossier()
print(f"Archivo real listo: {dataset['row_count']} eventos; {dataset['metadata']['coordinates']} con coordenadas.")
print('Ficha de demostración ficticia disponible, pendiente de revisión humana.')
