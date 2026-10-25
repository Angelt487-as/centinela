# Plan de implementación

## Incremento de autenticación

1. Migración aditiva de usuarios, sesiones, desafíos CSRF y límites persistentes; copia de seguridad previa.
2. Argon2id, sesión opaca HttpOnly, validación CSRF, caducidad y autorización en servidor.
3. Administrador inicial solo desde consola local; gestión de usuarios para administradores.
4. Pantalla de acceso responsive y guardas de React; cierre de sesión y cambio de contraseña.
5. Pruebas de acceso anónimo, roles, revocación, límites, datos existentes y seis tamaños.
6. Actualizar instrucciones, dependencias fijadas e informe de seguridad/verificación.

Autenticación completada: 25 pruebas backend y 42 pruebas UI aprobadas. Los
usuarios iniciales se configuran únicamente desde la consola local. La base
principal y sus originales se contrastaron con el respaldo previo a la migración.

## Recursos inspeccionados

El ZIP original contiene 60 archivos (49 contenidos únicos): 22 PDF, 13 XLS binarios,
9 CSV, 9 JPG y 7 DOCX. Hay cuatro carpetas de módulos y una de conversiones.
Los cinco CSV únicos contienen 22,977 filas con fecha reconocible. Sus encabezados
están en distintas filas, algunos se repiten y las coordenadas están en DMS.
Really.png es el logotipo oficial. No existía código de aplicación.

## Incrementos

1. Estructura separada, dependencias, SQLite, endpoints de salud y recursos locales.
2. Importación CSV/XLS/XLSX, normalización, filtros, estadísticas, CSV y vínculos.
3. Fuentes públicas, evidencias conservadas, SHA-256 y bitácora exportable.
4. Coordenadas DMS/decimales, secuencia y mapa; conexiones ilustrativas explícitas.
5. Extracción PDF/DOCX, fichas por pasos, borradores, revisión y Word/PDF.
6. Interfaz responsive mobile first; modo oscuro/claro y carga diferida.
7. Pytest con archivos reales y casos adversos, compilación, flujos y seis tamaños.

## Estado final

Los siete incrementos están implementados y verificados. Backend: 15 pruebas
aprobadas. Interfaz: 18 pruebas aprobadas en los seis tamaños, con compilación
correcta. Inicio integrado de Windows comprobado. VERIFICACION.md documenta
evidencias, incidencias corregidas y comprobaciones manuales pendientes.

## Decisiones

- Aplicación exclusivamente local, ligada a 127.0.0.1. Sin publicación ni telemetría.
- Recursos del ZIP se leen bajo demanda mediante identificadores calculados en servidor.
- Importación idempotente por SHA-256 para evitar duplicar archivos idénticos.
- Tablas paginadas en servidor; red limitada y mapa con máximo explícito de eventos.
- Teselas externas del mapa solo al solicitarlas, con aviso: el proveedor recibe el área visualizada, sin los registros del expediente.
- No buscar automáticamente en internet; abrir una búsqueda externa es una acción explícita.
- Revisar VERIFICACION.md para el estado final y las limitaciones observadas.
