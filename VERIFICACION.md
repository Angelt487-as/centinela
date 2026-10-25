# Verificación de Centinela 360

## Incremento de autenticación 1.1

Comprobado el 24 de octubre de 2026 con Python 3.12 y Microsoft Edge en Windows.
La autenticación se integró sin sustituir los módulos ni alterar sus documentos.

| Comprobación actual | Resultado |
|---|---|
| Pytest, autenticación y regresión de los cuatro módulos | 25 aprobadas, sin fallos |
| Playwright, siete recorridos en cada uno de los seis tamaños | 42 aprobadas, sin fallos ni omisiones |
| TypeScript y compilación de producción | Correctos |
| pip check y sintaxis PowerShell | Correctos |
| SQLite y ZIP mediante acceso directo al servidor de desarrollo | HTTP 403, acceso denegado |
| Recursos y exportaciones sin sesión | HTTP 401, sin datos |
| Comparación de las tablas previas con el respaldo | Sin diferencias de registros |
| SHA-256 de los originales conservados | Coincide con los hashes previos |

Los seis tamaños son 360×800, 390×844, 768×1024, 1024×768, 1366×768 y 1920×1080.
Se revisó visualmente el inicio de sesión en los seis tamaños y capturas de
administración y cuenta. Se comprobó también el zoom del acceso al 200 % mediante
CSS zoom. Las auditorías axe de las vistas incluidas no reportaron infracciones
de las reglas activadas; esto no equivale a una certificación WCAG.

Se verificó: acceso genérico incorrecto, cookie HttpOnly/SameSite y Secure bajo
HTTPS, rotación y cierre, almacenamiento exclusivo del hash de sesión, CSRF en
login y mutaciones, caducidad absoluta e inactiva, límites persistentes, rechazo
del analista al gestionar cuentas, revocación tras desactivación/cambio de rol o
contraseña y protección del último administrador activo. Un 401 privado desmonta
el módulo y dirige a #acceso. El cambio de contraseña propio se verificó de
principio a fin, rechazando después la contraseña anterior.

Los siete recorridos UI por tamaño cubren acceso/cierre, gestión y rechazo de
roles, revocación, cambio de contraseña, las cinco vistas originales, teclado y
tema/zoom, y el flujo completo de filtros, red, mapa, evidencia y ficha exportable.
Las pruebas crean contraseñas aleatorias y bases independientes; no dejan cuentas
predeterminadas en el espacio de trabajo principal ni guardan tokens de navegador.

Después de la migración, la base principal conserva un archivo, 534 eventos,
485 eventos con coordenadas, una ficha y ninguna fuente. Conserva **cero usuarios
predeterminados**: su propietario debe ejecutar crear-administrador.cmd para
elegir el primer acceso. Se preservó un respaldo previo en data/backups/.

El arranque integrado sigue comprobándose con scripts/iniciar.ps1 -SoloVerificar.
La configuración HTTP local no instala TLS: HTTPS exige certificados/proxy
apropiados y cookies Secure configuradas como se detalla en AUTENTICACION.md.
La recuperación automática de contraseña, MFA y aislamiento por expediente
quedan fuera de esta versión. Los límites anteriores de OCR y revisión visual
de Word se mantienen.

## Verificación del MVP inicial

Comprobación realizada el 24 de octubre de 2026 en Windows. El proyecto se construyó
y ejecutó localmente; no se publicaron documentos ni se desplegó un servicio externo.

## Resultado

| Comprobación | Resultado |
|---|---|
| Backend con Pytest | 15 pruebas aprobadas, sin fallos |
| TypeScript y compilación Vite | Correctos |
| Playwright sobre Edge | 18 pruebas aprobadas, sin fallos ni omisiones |
| Dependencias Python con pip check | Sin dependencias incompatibles |
| Sintaxis de los tres scripts PowerShell | Correcta |
| Inicio integrado de Windows con -SoloVerificar | Ambos servidores responden y se detienen al terminar |
| Originales del proyecto | ZIP y Really.png conservan tamaño y fecha de modificación originales |

## Tamaños e interacción

Cada tamaño ejecutó tres pruebas: las cinco vistas, navegación/tema/zoom y el
recorrido completo con filtros, grafo, mapa, evidencias y fichas.

| Tamaño | Vistas y accesibilidad automática | Teclado, tema y reflujo | Recorrido completo |
|---|---|---|---|
| 360 × 800 | Aprobado | Aprobado | Aprobado |
| 390 × 844 | Aprobado | Aprobado | Aprobado |
| 768 × 1024 | Aprobado | Aprobado | Aprobado |
| 1024 × 768 | Aprobado | Aprobado | Aprobado |
| 1366 × 768 | Aprobado | Aprobado | Aprobado |
| 1920 × 1080 | Aprobado | Aprobado | Aprobado |

Se generaron 30 capturas de las cinco vistas en los seis tamaños. Se revisaron
capturas representativas de cada tamaño, incluidos los filtros visibles de
escritorio, las tarjetas móviles, fichas y el mapa. No se detectó desplazamiento
horizontal de la página principal. Tablas y visualizadores tienen contenedores propios.

Las auditorías axe no reportaron infracciones de las reglas activadas de WCAG A/AA
en las vistas revisadas. También se auditó Análisis en tema claro. Se probaron
el enlace para saltar al contenido, menú móvil con toque emulado, foco mediante
teclado, cierre del grafo con Escape y ampliación mediante CSS zoom al 200 %.

Esto no constituye una certificación WCAG. Quedan como comprobación manual el zoom
nativo del navegador, lectores de pantalla, el teclado virtual, gestos de pellizco
y equipos físicos. Las instrucciones están en RESPONSIVE.md.

## Datos y flujos reales

- Se leyeron correctamente los **12 archivos de datos originales** de la carpeta
  de análisis: cinco CSV y siete XLS. Los cinco CSV suman 22,977 eventos con
  fecha reconocible. Se verificaron encabezados, coordenadas y fechas/horas de Excel.
- En el recorrido de integración se importó un CSV real con **534 eventos y 485
  con coordenadas**. Se contrastaron estadísticas, filtrado, paginación, CSV,
  red, cronología e integridad de la copia original descargada.
- Reimportar el mismo archivo no duplicó eventos. Las hojas de copias de Excel
  no se suman a la primera hoja reconocida; esto se informa al usuario.
- Se probó XLSX con un libro generado expresamente para prueba, así como CSV
  Windows-1252, separador punto y coma, identificadores con ceros iniciales y hora faltante.
- Se extrajo texto de los **seis documentos originales de fichas**, tres PDF y
  tres DOCX. Los campos propuestos permanecen pendientes de revisión.
- Fuentes: registro, carga de evidencia TXT, comparación independiente de SHA-256,
  descarga del mismo contenido y exportación de bitácora. Los registros usados
  para probar la interfaz están etiquetados como ficticios y en carpetas de QA.
- Fichas: bloqueo de exportación sin revisión, edición, guardado por pasos,
  confirmación, descarga PDF y DOCX e invalidación de la revisión tras editar.
- Se abrió estructuralmente el Word generado con python-docx. El PDF ficticio se
  volvió a leer, se renderizó y se inspeccionó visualmente: una página sin recortes.

## Validaciones y errores

Pruebas de archivos vacíos, extensión no admitida, firma XLS falsa, nombre con
traversal de carpetas, estructura ZIP insegura dentro de DOCX, tamaño excesivo,
datos sin encabezados reconocibles, fechas invertidas, URL no admitida, origen
web no autorizado, recurso inexistente y PDF sin texto. Los errores se muestran
en español sin repetir valores personales en la respuesta de validación.

Las exportaciones CSV protegen valores textuales que podrían interpretarse como
fórmulas de hoja de cálculo. Las consultas SQLite utilizan parámetros. Los originales
usan identificadores internos y se descargan como adjuntos.

## Estado del espacio de trabajo entregado

La base principal `data/centinela.sqlite3` contiene un archivo real importado,
534 eventos, 485 eventos geográficos, ninguna fuente ficticia registrada y una
ficha de demostración ficticia pendiente de revisión. Las pruebas de interfaz
utilizaron bases independientes en `data/ui-qa*`. No se mezclaron sus fuentes
ficticias con el espacio de trabajo principal.

Los servidores temporales de comprobación se detuvieron. Ejecuta `iniciar.cmd`
para abrir tu espacio de trabajo en http://127.0.0.1:5173/.

## Limitaciones y avisos pendientes

- No hay OCR, búsqueda web integrada, captura automática de páginas, seguimiento
  en tiempo real ni reconocimiento facial.
- Importación Excel de la primera hoja reconocible; otras hojas deben exportarse
  como CSV para analizarlas por separado. Las originales permanecen conservadas.
- Red de hasta 100 vínculos y vista de hasta 500 eventos geográficos, con avisos.
  Las exportaciones conservan todos los resultados filtrados.
- El mapa base externo de OpenStreetMap no se verificó mediante solicitudes a
  internet; su activación es opcional. Sí se probaron los marcadores locales,
  controles de acercamiento y selección desde la cronología.
- La revisión visual del DOCX en Word/LibreOffice queda pendiente. El renderizador
  disponible no pudo ejecutarla porque falta LibreOffice; la validación estructural
  del DOCX y la inspección visual del PDF sí se completaron.
- Pytest emitió ocho avisos de deprecación de las dependencias: TestClient/httpx
  y el motor xlrd de Pandas. No fueron errores. Las versiones instaladas están
  fijadas en requirements.lock.txt para reproducir esta comprobación.
- La versión actual agrega usuarios y roles; sigue siendo una aplicación local
  con datos compartidos y sin cifrado de disco propio. Los límites de extracción
  y conservación se detallan en README.md y el acceso en AUTENTICACION.md.

## Reproducción

```powershell
.venv\Scripts\python.exe -m pytest backend/tests --basetemp data/test-current -q
cd frontend
npm run build
# Para la versión actual, desde la raíz y con los puertos libres:
# .venv\Scripts\python.exe scripts/probar_interfaz.py
```

El resultado JSON de la última ejecución UI está en `data/ui-results.json` y las
capturas están en `data/screenshots/`. Ambos se excluyen de Git por contener datos
del espacio local. Para comprobar únicamente el arranque, con los puertos libres:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/iniciar.ps1 -SoloVerificar
```
