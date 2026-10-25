"""QA aislado: cuentas aleatorias en memoria, sin credenciales fijas ni endpoints de prueba."""
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def available(port):
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False


def main():
    if not all(available(p) for p in (8000, 5173)):
        print('Cierra las instancias locales que usan 8000 y 5173 antes de probar. No se detuvieron procesos ajenos.')
        return 1
    node = shutil.which('node')
    vite = ROOT / 'frontend/node_modules/vite/bin/vite.js'
    tsc = ROOT / 'frontend/node_modules/typescript/bin/tsc'
    playwright = ROOT / 'frontend/node_modules/@playwright/test/cli.js'
    if not node or not vite.is_file() or not playwright.is_file():
        print('Ejecuta instalar.cmd e instala Node.js antes de probar la interfaz.')
        return 1
    folder = ROOT / 'data' / ('ui-auth-' + uuid.uuid4().hex[:12])
    os.environ['CENTINELA_DATA_DIR'] = str(folder)
    from backend.app.database import initialize
    from backend.app.auth import create_user
    initialize()
    env = os.environ.copy()
    for name, role in (('ADMIN', 'administrador'), ('ANALYST', 'analista')):
        username, password = name.lower() + '-qa', secrets.token_urlsafe(32)
        create_user(username, password, role)
        env['C360_TEST_' + name + '_USER'] = username
        env['C360_TEST_' + name + '_PASSWORD'] = password
    from backend.app.files import resource_bytes, resources
    from backend.app.main import import_dataset
    resource = next((r for r in resources() if r['name'] == '6271218386.csv' and 'estructuracion' in r['folder']), None)
    if not resource:
        print('Hace falta el ZIP original del proyecto para verificar los flujos con datos reales.')
        return 1
    import_dataset(*resource_bytes(resource['id'], 'datos'))
    from backend.app.source_demo import prepare_sources_demo
    prepare_sources_demo()
    for command in ([node, str(tsc), '-b'], [node, str(vite), 'build']):
        result = subprocess.run(command, cwd=ROOT / 'frontend')
        if result.returncode:
            return result.returncode
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    children = []
    try:
        children.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8000', '--no-access-log', '--no-proxy-headers'], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags))
        children.append(subprocess.Popen([node, str(vite), 'preview', '--host', '127.0.0.1', '--port', '5173', '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags))
        ready = False
        for _ in range(60):
            if any(p.poll() is not None for p in children):
                break
            try:
                with urlopen('http://127.0.0.1:8000/api/health', timeout=1) as r:
                    healthy = r.status == 200
                with urlopen('http://127.0.0.1:5173/', timeout=1) as r:
                    ready = healthy and r.status == 200
                if ready:
                    break
            except OSError:
                time.sleep(.25)
        if not ready:
            print('No se pudieron iniciar los servidores de prueba.')
            return 1
        print('Pruebas con cuentas efimeras y base aislada. No se muestran ni guardan las contrasenas.', flush=True)
        return subprocess.run([node, str(playwright), 'test', *sys.argv[1:]], cwd=ROOT / 'frontend', env=env).returncode
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())
