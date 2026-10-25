"""Carga idempotente de material real de referencia del hackathon, sin URLs ficticias."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
from backend.app.source_demo import prepare_sources_demo


def main():
    try:
        source = prepare_sources_demo()
    except (FileNotFoundError, ValueError, HTTPException) as error:
        print(getattr(error, 'detail', str(error)))
        return 1
    print('Demostracion preparada: material de referencia del hackathon.')
    print('Documento:', source['original_name'])
    print('SHA-256:', source['evidence'][0]['sha256'])
    print('Sin URL publica ni fecha de consulta. No se duplican registros al repetir la carga.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
