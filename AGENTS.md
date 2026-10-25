# Centinela 360

- Aplicación local para datos autorizados. No publicar documentos ni expedientes.
- Conservar el ZIP y el logotipo originales. No ejecutar acciones destructivas.
- Frontend: React, TypeScript, Vite y Tailwind. Backend: Python 3.11+, FastAPI y SQLite.
- Interfaz en español, mobile first, accesible mediante teclado y con controles de 44 px.
- Los resultados deben proceder de archivos importados; las demostraciones deben estar etiquetadas.
- Conservar originales en `data/originals` y resultados en SQLite. No registrar valores personales en logs.
- Validar extensión, firma, tamaño y estructura de las cargas. No aceptar rutas de cliente.
- Las líneas del mapa representan conexiones cronológicas ilustrativas, no recorridos GPS.
- Toda ficha requiere revisión humana explícita antes de exportarse. Editarla invalida la revisión.
- Ejecutar Pytest después de cada incremento de backend y compilar TypeScript antes de entregar.
- Documentar limitaciones y resultados reales en `VERIFICACION.md`; no afirmar certificación WCAG.
- No añadir reconocimiento facial, seguimiento en tiempo real ni inferencias sobre personas.
- Toda API de datos, originales y exportaciones exige sesión válida; los roles se comprueban en servidor.
- Contraseñas Argon2id; nunca credenciales, tokens de sesión ni secretos en código, logs o almacenamiento web.
- Primer administrador exclusivamente por consola local con getpass. No crear cuentas predeterminadas.
- Mutaciones autenticadas y login requieren CSRF. Revocar sesiones al desactivar usuarios o cambiar credenciales/rol.
