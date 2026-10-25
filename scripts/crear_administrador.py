"""Inicialización local interactiva. Nunca recibe contraseñas por argumentos o archivos."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from backend.app.auth import create_user
from backend.app.database import connection, initialize


def main():
    initialize()
    with connection() as db:
        if db.execute('SELECT id FROM users LIMIT 1').fetchone():
            print('El administrador inicial ya esta configurado. Gestiona las cuentas dentro de Centinela 360.')
            return 0
    if not sys.stdin.isatty():
        print('Abre crear-administrador.cmd en una consola local interactiva para elegir tus datos de acceso.')
        return 1
    print('Centinela 360 - Configurar primer administrador')
    print('Elige una frase de acceso de 12 a 128 caracteres. No se mostrara en pantalla.')
    username = input('Nombre de usuario: ')
    password = getpass.getpass('Contrasena: ')
    confirmation = getpass.getpass('Confirmar contrasena: ')
    if password != confirmation:
        print('Las contrasenas no coinciden. No se creo ninguna cuenta.')
        return 1
    try:
        create_user(username, password, 'administrador', initial_only=True)
    except HTTPException as error:
        print(error.detail)
        return 1
    print('Administrador creado. Ya puedes iniciar sesion en Centinela 360.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print('\nConfiguracion cancelada. No se mostraron ni guardaron contrasenas en texto plano.')
        raise SystemExit(1)
