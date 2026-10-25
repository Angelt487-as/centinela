# Decisiones responsive

## Acceso y administración

La pantalla de acceso utiliza una tarjeta centrada de hasta 440 px, logotipo
oficial y controles de 44 a 52 px, sin recursos remotos ni animaciones constantes.
El botón de contraseña comunica su acción y estado; los errores se anuncian y
reciben foco. Los estados de comprobación de sesión no muestran módulos privados.
El menú de cuenta es compacto en móviles y muestra el usuario/rol cuando hay
espacio. La gestión de usuarios pasa de dos paneles a una columna y conserva
etiquetas individuales, estados escritos y formularios de contraseña protegidos.

## Distribución

Mobile first: una columna, acciones principales de ancho completo, filtros
desplegables y tarjetas de eventos. A partir de 640 px hay formularios de dos
columnas y tablas desplazables. A partir de 768 px se distribuyen paneles dobles.
Desde 1024 px se muestra el menú lateral fijo de 252 px. El menú compacto utiliza
un dialog nativo con bloqueo del foco, cierre por Escape y botón de cierre.

Los mapas priorizan el espacio de visualización: la cronología se apila debajo
en espacios reducidos y queda a la derecha cuando hay ancho suficiente. La red
se abre en un dialog amplio con controles de zoom y ajuste. Las fichas tienen
tres pasos y guardan progreso antes de pasar al siguiente.

Se combinan media queries y container queries: los paneles responden al ancho
real del espacio de trabajo, incluido el espacio restante al ampliar el navegador.
Ningún contenedor principal impone un ancho mínimo. El desplazamiento horizontal
se limita a tablas o a sus visualizaciones. Los textos largos y hashes se parten.

## Accesibilidad

Base de 16 px. Controles principales de 44 px o más, foco de 3 px visible,
etiquetas, avisos mediante alert/status, estados escritos y enlace para saltar
al contenido. No se depende del color. La red incluye una lista textual y se
puede desplazar con flechas, +, - y Home. La cronología ofrece una alternativa
al uso directo de marcadores. El tema claro adapta colores semánticos.

Los diálogos usan showModal, Escape y devolución nativa del foco. No se aplican
animaciones al mapa ni a la red. El indicador de carga es la única animación
temporal y se desactiva con prefers-reduced-motion.

## Rendimiento

Sin tipografías remotas ni librería de componentes. Iconos SVG importados por
componente. El logotipo original se conserva; la copia WebP pesa aproximadamente
12 KB. Los módulos, Leaflet y Cytoscape se dividen en paquetes diferidos.
Consultas paginadas, filtros aplicados explícitamente y ninguna petición periódica.
La red limita elementos y usa distribución estática. La capa geográfica usa SVG
para evitar tareas Canvas pendientes al desmontar en React StrictMode.

## Comprobación manual adicional

1. En las herramientas del navegador revisa 360x800, 390x844, 768x1024, 1024x768,
   1366x768 y 1920x1080. Abre los cuatro módulos en tema claro y oscuro.
2. Confirma que la página no se desplaza horizontalmente. En tablas, desplaza
   solo su contenedor. En móviles abre y cierra filtros y menú.
3. Usa Tab y Shift+Tab, Enter, Espacio, flechas y Escape. Comprueba foco visible,
   retorno del foco al cerrar diálogos y acceso a todos los formularios.
4. Ajusta el zoom nativo del navegador al 200 %. Comprueba campos, mensajes,
   navegación y exportaciones. La prueba automatizada complementa esto con CSS zoom.
5. En un teléfono y una tablet físicos verifica pulsaciones, pellizco del mapa,
   orientación y teclado virtual. La emulación automática no prueba el hardware.
6. Con NVDA o VoiceOver confirma etiquetas, avisos, tablas/listas y orden de lectura.
7. Desconecta internet: datos, fichas y marcadores deben funcionar localmente;
   solo el mapa base externo y los enlaces de búsqueda requieren conexión.
