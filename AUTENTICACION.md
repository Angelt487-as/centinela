# Autenticación de Centinela 360

La aplicación requiere iniciar sesión para consultar sus módulos, originales y
exportaciones. La autorización se aplica en FastAPI y React. Los usuarios
autorizados comparten el espacio local; esta versión no separa expedientes por propietario.

## Primer acceso

1. Ejecuta `instalar.cmd` para instalar las dependencias actualizadas.
2. Ejecuta `crear-administrador.cmd` en una consola de esta computadora.
3. Elige un nombre de usuario y una contraseña de 12 a 128 caracteres. Usa una
   frase larga y única. La contraseña y su confirmación no se muestran ni se
   reciben por argumentos, archivos de configuración o mensajes de chat.
4. Ejecuta `iniciar.cmd`, abre http://127.0.0.1:5173/ e inicia sesión.
5. Desde **Gestión de usuarios**, crea las cuentas que necesites.

El comando inicial se niega a crear otra cuenta cuando ya existen usuarios.
No hay registro público, cuenta predeterminada ni endpoint de alta del primer
administrador. Los administradores existentes gestionan las altas posteriores.
Si necesitas recuperar acceso, utiliza otro administrador autorizado; esta versión
no incluye recuperación automática por correo ni una contraseña maestra.

El usuario se normaliza a minúsculas y admite de 3 a 50 caracteres ASCII: letras,
números, punto, guion y guion bajo; empieza por letra o número. Las contraseñas
se conservan exactamente como se escriben, incluidas mayúsculas y espacios.

## Permisos

| Función | Administrador | Analista | Sin sesión |
|---|---|---|---|
| Cuatro módulos, filtros y visualizaciones | Sí | Sí | No |
| Originales, evidencias y exportaciones | Sí | Sí | No |
| Cambiar su propia contraseña | Sí | Sí | No |
| Listar y crear usuarios | Sí | No | No |
| Cambiar rol, estado o restablecer contraseñas | Sí | No | No |
| Consultar salud del servicio | Sí | Sí | Sí |

No se permite desactivar ni degradar al último administrador activo. No se
eliminan cuentas ni documentos desde la gestión de usuarios. Cambiar el rol,
estado o contraseña revoca las sesiones de la cuenta afectada. El cambio de
contraseña propio pide la actual y cierra todas sus sesiones.

## Contraseñas y sesiones

- Argon2id mediante argon2-cffi: 64 MiB, tres iteraciones, paralelismo dos, sal
  aleatoria de 16 bytes y hash de 32 bytes. Se comprueba si hace falta actualizar
  el hash al iniciar sesión. No se almacenan contraseñas en texto plano.
- Identificador de sesión aleatorio de 256 bits, opaco para el navegador. SQLite
  conserva su SHA-256, no el valor de la cookie. No se utilizan JWT ni claves
  de firma fijas incorporadas al código.
- Cookie de sesión `c360_session`: HttpOnly, SameSite=Strict, host-only, Path=/.
  Usa Secure cuando la solicitud es HTTPS o se configura el modo HTTPS.
- Caducidad absoluta por defecto de ocho horas y por inactividad de 30 minutos.
  FastAPI comprueba ambas en cada solicitud privada, así como el estado y rol actuales.
- React comprueba la sesión al arrancar y al recuperar el foco. Las respuestas
  actualizan su fecha límite; un temporizador y cualquier 401 privado cierran la
  vista privada. El cierre de sesión revoca el registro del servidor y borra la cookie.
- Los cambios de sesión se comunican entre pestañas mediante BroadcastChannel,
  sin transmitir contraseñas ni tokens. No se guardan credenciales o tokens en
  localStorage o sessionStorage; únicamente se conserva la preferencia de tema.

## CSRF y límites de acceso

Las mutaciones privadas exigen `X-CSRF-Token`. El token se deriva de la sesión,
se compara en tiempo constante y se mantiene solo en memoria en React. No basta
con poseer una URL o enviar una cookie desde un formulario externo.

El inicio de sesión también exige un desafío CSRF previo, con una cookie HttpOnly
independiente de diez minutos. No se crean sesiones a partir de un identificador
enviado por el cliente: un acceso correcto genera un token nuevo.

Se verifican Origin y Sec-Fetch-Site en mutaciones. Las respuestas privadas usan
Cache-Control: no-store; los archivos se entregan como adjuntos y sus rutas no
se sirven como archivos públicos. El servidor de desarrollo restringe el acceso
al directorio frontend y deniega datos, bases SQLite, ZIP, logs y archivos de entorno.

Los límites persisten en SQLite: cinco intentos fallidos por nombre de usuario
en 15 minutos y 100 intentos totales por dirección de conexión en ese intervalo.
El nombre utilizado y la dirección se convierten en hashes para las claves del
limitador. Un acceso correcto limpia el contador del nombre, pero no el contador
de conexión. Los intentos simultáneos se reservan antes de verificar Argon2 y
se limita la verificación a dos operaciones simultáneas.

Usuario inexistente, contraseña incorrecta o cuenta inactiva producen el mismo
mensaje y estado. Para usuarios inexistentes también se verifica un hash Argon2id
de descarte. Un exceso de intentos devuelve 429 y Retry-After sin indicar si existe
la cuenta.

## Configuración HTTPS y duración

La instalación incluida sigue en HTTP **solo en 127.0.0.1**. No instala certificados
ni publica el servicio. Si se coloca tras un proxy HTTPS autorizado, antes de
iniciar configura las cookies seguras y el origen HTTPS exacto:

```powershell
$env:CENTINELA_COOKIE_SECURE = '1'
$env:CENTINELA_ALLOWED_ORIGINS = 'https://localhost:5173'
# Solo si necesitas cambiar los valores por defecto:
$env:CENTINELA_SESSION_SECONDS = '28800'
$env:CENTINELA_IDLE_SECONDS = '1800'
```

El origen del ejemplo debe sustituirse por el real. No uses comodines. Los hosts
del backend siguen restringidos a localhost y loopback; no es una receta de
despliegue público. Secure requiere que el navegador use HTTPS. Detrás de un proxy
que termina TLS, `CENTINELA_COOKIE_SECURE=1` es obligatorio. Los scripts de inicio
no confían en encabezados de proxy proporcionados por clientes.

La duración absoluta se limita a entre 60 segundos y 24 horas; la de inactividad
no puede superar la absoluta. Se requiere un reloj correcto en el equipo.

## Datos y migración

La migración agrega `users`, `sessions`, `login_challenges` y `auth_limits` con
CREATE TABLE IF NOT EXISTS. No borra datos existentes. Se conservó una copia
SQLite previa al cambio en `data/backups/`. La base principal queda sin usuarios
predeterminados para que su propietario elija el primer acceso de forma local.

Los datos de acceso son sensibles incluso almacenados como hashes: protege
permisos de la carpeta y copias de seguridad. Esta versión no implementa MFA,
cifrado de disco propio, aislamiento por expediente, recuperación por correo ni
una auditoría resistente a alteraciones. Conserva el alcance de aplicación local.

## Pruebas

```powershell
.venv\Scripts\python.exe -m pytest backend/tests --basetemp data/test-auth -q
.venv\Scripts\python.exe scripts/probar_interfaz.py
```

El ejecutor UI usa cuentas aleatorias efímeras, una carpeta `data/ui-auth-*` nueva
y Edge en modo de pruebas. Pasa credenciales solo en memoria/entorno de procesos,
no en argumentos, archivos de estado de navegador o código fuente. Las trazas
de red de Playwright están desactivadas para no conservar cuerpos de login.
Las capturas, bases y resultados de QA están excluidos de Git.

Las pruebas comprueban las rutas privadas, CSRF, roles, contraseñas, revocación,
caducidad absoluta e inactiva, límites persistentes, migración y las funciones
previas. La UI añade login, mostrar/ocultar contraseña, administración, rechazo
del analista y retorno al acceso después de revocar una sesión en seis tamaños.

## Referencias de implementación

Los parámetros y el manejo de contraseñas se contrastaron con [OWASP Password
Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
y [argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/howto.html). El diseño
de sesiones y CSRF se contrastó con [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
y [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
