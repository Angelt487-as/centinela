# Centinela 360

Aplicación local funcional para estructurar registros, conservar evidencias de fuentes
públicas, visualizar coordenadas y generar fichas revisadas. Frontend y backend están
separados. Los resultados se obtienen de documentos importados; no se generan eventos ficticios.

## Inicio en Windows

Requisitos: Python 3.11 o posterior, Node.js 22 o posterior y Microsoft Edge, Chrome
o Firefox actualizado. La instalación inicial necesita internet. Si este equipo tiene
el runtime de Codex, el instalador también puede utilizar su Python.
Las versiones fijadas se verificaron con Python 3.12; con Python 3.11 el instalador
resuelve versiones compatibles a partir de requirements.txt.

1. Ejecuta `instalar.cmd` una vez. Crea `.venv` e instala las dependencias fijadas.
2. Ejecuta `crear-administrador.cmd` y elige tu usuario y una contraseña de 12 a 128 caracteres.
   La contraseña se pide de forma oculta. No hay una cuenta ni una clave predeterminadas.
3. Ejecuta `iniciar.cmd`.
4. Abre **http://127.0.0.1:5173/** e inicia sesión. Mantén abierta la consola de inicio.
5. Pulsa Enter en esa consola para detener los dos servidores.

Este espacio de trabajo ya tiene un CSV real importado con 534 eventos, 485 con
coordenadas, y una ficha ficticia pendiente de revisión. En una instalación nueva
puedes preparar el mismo ejemplo sin duplicarlo:

```powershell
.venv\Scripts\python.exe scripts/cargar_ejemplo.py
```

También puedes ejecutar `iniciar-backend.cmd` e `iniciar-frontend.cmd` en dos consolas.
Los puertos 8000 y 5173 deben estar libres. El inicio no modifica la política de
ejecución de Windows: Bypass se aplica solo al proceso de los scripts incluidos.

Si actualizas desde la versión sin autenticación, vuelve a ejecutar `instalar.cmd`
para instalar Argon2 y después configura el administrador. La migración agrega
tablas y conserva datos y documentos existentes. Los administradores crean y
gestionan usuarios desde **Gestión de usuarios**; los analistas usan los cuatro
módulos. El menú de cuenta permite cambiar la contraseña y cerrar sesión.
Consulta `AUTENTICACION.md` para sesiones, CSRF, HTTPS y permisos.

Para indicar un Python concreto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/instalar.ps1 -Python "C:\ruta\python.exe"
```

## Recorrido funcional

- **Análisis de datos:** importa CSV, XLS o XLSX, o selecciona un archivo del ZIP.
  Se detectan codificación, separador y encabezados. Se conservan las filas originales
  y su hoja de procedencia. Usa filtros por número, tipo y fecha, estadísticas, tabla
  paginada, red de vínculos y exportación CSV. La pestaña Origen y calidad muestra
  el SHA-256 y los avisos. Archivos idénticos no duplican eventos.
- **Fuentes abiertas:** registra título, URL pública, fecha, descripción y notas.
  Abre sus detalles y adjunta PDF, DOCX, JPG, PNG, TXT o CSV para conservar evidencia
  y calcular SHA-256. Exporta la bitácora. La búsqueda abre Google bajo una acción
  explícita; no existe un proveedor de búsqueda integrado ni captura automática.
- **Geolocalización:** usa el mismo archivo importado. Convierte coordenadas DMS
  o decimales, muestra eventos, agrupaciones por coordenadas/azimut y su cronología.
  Los marcadores funcionan sin red. El mapa base externo es opcional; al activarlo,
  OpenStreetMap recibe solicitudes del área visualizada. Las líneas entre eventos
  del mismo número consultado son ilustrativas y no prueban recorridos GPS.
- **Fichas:** importa PDF con texto o DOCX. Los campos reconocibles se proponen para
  revisión. Completa tres pasos, guarda progreso y confirma expresamente la revisión
  humana. Después de guardar la confirmación, descarga Word o PDF. Editar un campo
  invalida la revisión. Los campos faltantes se identifican y se exportan como
  No proporcionado. El botón de demostración crea una ficha claramente ficticia.

## Archivos del hackathon

El ZIP original tiene 60 entradas de archivos y 49 contenidos únicos. Los criterios
se encuentran en DOCX. Hay 12 archivos de datos distintos en la carpeta de análisis
(5 CSV y 7 XLS). Los cinco CSV contienen 22,977 eventos con fecha reconocible.
Las pruebas verifican la lectura de los 12 archivos y los seis documentos de fichas.

Los XLS contienen hojas de trabajo, copias y vistas de análisis. Para evitar sumar
copias, se importa **la primera hoja con eventos reconocibles** y se informa su
nombre y las hojas disponibles. Para analizar otra hoja, expórtala como CSV y
cárgala por separado. No se eliminan ni alteran las demás hojas del original.

## Límites del MVP

- Archivos de hasta 25 MB, hasta 150,000 filas y 30 hojas por libro; PDF hasta 250 páginas.
- No incluye OCR. Los PDF escaneados sin texto muestran un error comprensible.
- La extracción de campos es conservadora y no garantiza reconocer todo documento.
  La ficha exportada utiliza un formato estructurado nuevo; no reproduce el diseño original.
- Red limitada a los 100 vínculos más frecuentes de la consulta. Mapa limitado a los
  primeros 500 eventos; la exportación incluye todos los resultados filtrados.
  Las ubicaciones agrupadas se limitan a 2,000; no se infieren antenas ni identificadores.
- Las fechas ambiguas de texto se interpretan día/mes/año. Las horas de los documentos
  se conservan sin inventar zona horaria; las operaciones se registran en UTC.
- El SHA-256 permite comprobar integridad, no certifica autenticidad, veracidad
  ni admisibilidad jurídica de una evidencia.
- Autenticación por usuario y contraseña, con roles Administrador y Analista.
  Los usuarios autorizados comparten el espacio de trabajo; no hay aislamiento
  de expedientes por usuario. Sin auditoría resistente a alteraciones ni cifrado
  de disco propio. Sigue ligado a 127.0.0.1 y no se ha desplegado en internet.
- No incluye reconocimiento facial, seguimiento en tiempo real ni inferencias personales.

## Arquitectura y persistencia

```text
backend/app/        FastAPI, validación, importadores y exportadores
backend/tests/      Pruebas de integración con archivos reales
frontend/src/       React, TypeScript, componentes y módulos diferidos
frontend/tests/     Playwright y axe, seis tamaños de pantalla
scripts/           Instalación, inicio y comprobación para Windows
data/originals/    Originales conservados con identificadores internos
data/centinela.sqlite3  Datos procesados, borradores y bitácora
```

`data/`, dependencias, capturas y logs están excluidos de Git. El ZIP y Really.png
se conservan en su ubicación original. El logotipo servido se optimizó a WebP de
aproximadamente 12 KB. No hay fuentes externas ni telemetría. Mapas y grafos se
cargan cuando se abren; no hay sondeos periódicos ni animaciones permanentes.

La API está documentada en http://127.0.0.1:8000/docs, después de iniciar sesión.
Salud pública: `/api/health`. Los datos, archivos y exportaciones requieren sesión;
las mutaciones requieren además el encabezado `X-CSRF-Token`.
Endpoints principales: `/api/datasets`, `/api/events`, `/api/stats`, `/api/graph`,
`/api/geo`, `/api/sources`, `/api/dossiers` y sus exportaciones.
`CENTINELA_DATA_DIR` permite usar una carpeta de datos independiente para pruebas.

## Responsive y accesibilidad

Consulta `RESPONSIVE.md` para las decisiones y `VERIFICACION.md` para los resultados.
Hay modo oscuro por defecto y modo claro, navegación por teclado, foco visible,
enlace para saltar al contenido y paneles modales con gestión nativa del foco.
Las tablas móviles se presentan en tarjetas y los filtros se despliegan.
La red ofrece controles, pantalla completa y lista textual; el mapa tiene una
secuencia operable mediante teclado. Se respeta movimiento reducido.

## Ejecutar pruebas

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/comprobar.ps1
```

Para pruebas UI, instala Microsoft Edge y deja libres los puertos 8000 y 5173.
El ejecutor crea una base aislada y cuentas con contraseñas aleatorias en memoria,
inicia los servidores y los detiene al terminar. No usa ni modifica tus cuentas:

```powershell
.venv\Scripts\python.exe scripts/probar_interfaz.py
# Solo celular y laptop:
.venv\Scripts\python.exe scripts/probar_interfaz.py --project=390x844 --project=1366x768
```

Las pruebas generan capturas y resultados dentro de `data/`. Los recorridos completos
usan fuentes y fichas expresamente ficticias. Los archivos reales se usan para comprobar
importación, estadísticas y geografía. Las pruebas automáticas no equivalen a una
certificación WCAG ni sustituyen la comprobación con lectores de pantalla y equipos físicos.
