# Reporte final — Auditoría de Rendimiento Frontend

## Resultado ejecutivo

La auditoría cubrió el sitio corporativo y el backoffice autenticado en builds
de producción. Se corrigieron los cuatro problemas confirmados por evidencia y
se extrajo un componente compartido. Ninguna ruta, contrato de API ni regla de
negocio cambió.

El resultado de mayor impacto está en el backoffice móvil: Performance subió de
73 a 85, LCP bajó de 2,4 s a 1,5 s y TBT bajó de 1.310 ms a 580 ms. El error de
hidratación desapareció. Las seis combinaciones auditadas terminan con 100 en
Accessibility, Best Practices y SEO.

## Comparación Lighthouse

| Aplicación | Ruta | Modo | Performance antes → después | Accessibility | Best Practices | SEO |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Website | `/` | Móvil | 97 → **98** | 93 → **100** | 100 → **100** | 100 → **100** |
| Website | `/` | Escritorio | 100 → **100** | 93 → **100** | 100 → **100** | 100 → **100** |
| Website | `/careers` | Móvil | 94 → **100** | 100 → **100** | 100 → **100** | 100 → **100** |
| Website | `/careers` | Escritorio | 100 → **100** | 100 → **100** | 100 → **100** | 100 → **100** |
| Backoffice | `/backoffice/overview` | Móvil | 73 → **85** | 98 → **100** | 96 → **100** | 100 → **100** |
| Backoffice | `/backoffice/overview` | Escritorio | 100 → **100** | 98 → **100** | 96 → **100** | 100 → **100** |

### Métricas de carga

| Aplicación / ruta | Modo | FCP antes → después | LCP antes → después | TBT antes → después | CLS antes → después | TTFB final |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Website `/` | Móvil | 0,8 → **0,8 s** | 1,2 → **1,1 s** | 200 → **160 ms** | 0 → **0** | 10 ms |
| Website `/` | Escritorio | 0,3 → **0,2 s** | 0,4 → **0,2 s** | 10 → **0 ms** | 0 → **0** | 10 ms |
| Website `/careers` | Móvil | 1,0 → **0,8 s** | 1,5 → **1,1 s** | 290 → **90 ms** | 0 → **0** | 100 ms |
| Website `/careers` | Escritorio | 0,2 → **0,2 s** | 0,3 → **0,3 s** | 0 → **0 ms** | 0 → **0** | 10 ms |
| Backoffice `/backoffice/overview` | Móvil | 0,6 → **0,6 s** | 2,4 → **1,5 s** | 1.310 → **580 ms** | 0 → **0** | 10 ms |
| Backoffice `/backoffice/overview` | Escritorio | 0,2 → **0,2 s** | 0,4 → **0,4 s** | 0 → **10 ms** | 0 → **0** | 0 ms |

## Correcciones y efecto observado

### 1. Hidratación estable en autenticación

`AuthProvider` ya no consulta `localStorage` para decidir el estado del primer
render. Servidor y cliente comienzan en `loading=true`; después del montaje se
resuelve la sesión y se actualiza el usuario. Esto elimina el cambio de texto
entre SSR y cliente que obligaba a React a descartar y reconstruir el árbol.

En el backoffice móvil, el trabajo del hilo principal pasó de 2,9 s a 1,6 s, el
arranque de JavaScript de 1,8 s a 0,9 s y las tareas largas de 12 a 5. Lighthouse
ya no reporta el error minificado React #418.

### 2. Imágenes descubribles y responsivas

El hero, las tarjetas de menú y el collage dejaron de usar fondos remotos de
Unsplash. Ahora usan `next/image`, dimensiones reservadas mediante contenedores,
`sizes` por breakpoint y archivos WebP locales. El hero declara prioridad alta
y carga eager, por lo que Lighthouse confirma que el recurso LCP es descubrible
en el documento inicial.

Una primera implementación con optimización de imágenes remotas provocó un LCP
frío de 4,3 s. La segunda medición permitió encontrar ese costo de transformación
y sustituir las URLs remotas por activos locales. La corrida final de Home móvil
quedó en LCP 1,1 s y Performance 98. La corrida de calentamiento local se conserva
en `audit/after/reports/website-home-mobile-warmup.*` para hacer visible la
variabilidad observada.

### 3. Contraste y semántica

Se separó el rojo usado bajo texto pequeño blanco y se fijó explícitamente el
color del contenido de `.btn-primary`. También se cambiaron los encabezados de
la historia de la marca de `h4` a `h3` y los KPIs del backoffice de `h3` a `h2`.
La apariencia se conserva y Accessibility queda en 100 en todas las mediciones.

La primera pasada de verificación reveló que el botón nativo de Careers heredaba
texto negro sobre el nuevo rojo. Se corrigió el alcance del estilo antes de
aceptar los resultados finales.

### 4. Componente reutilizable

Se creó `RestaurantSelect` y se integró en `ProductsTable` y `OrdersLedger`.
El componente comparte etiqueta, opciones, selección y soporte para “todas las
sedes”; cada consumidor sigue siendo responsable de persistencia, consulta y
filtrado. Esto reduce duplicación sin mezclar reglas de dominio.

## Evidencias

- Línea base: `audit/before/reports/` y `audit/before/screenshots/`.
- Medición final: `audit/after/reports/` y `audit/after/screenshots/`.
- Cada escenario incluye el reporte navegable HTML, el JSON completo y una
  captura de la cabecera con puntuaciones y métricas.
- El backoffice fue medido con una sesión autenticada real contra una API y una
  TinyDB temporales fuera del repositorio. La URL final registrada fue siempre
  `/backoffice/overview`.

## Validación funcional y técnica

- Pruebas del nuevo estado de autenticación: SSR determinista, usuario anónimo
  y carga de usuario autenticado.
- Pruebas de `RestaurantSelect`: opciones, opción global y propagación del
  cambio.
- Pruebas completas de interfaces, typecheck, lint y builds de producción.
- Verificación visual del website, Careers y dashboard autenticado en navegador,
  sin overlay de Next.js ni errores de consola al cierre.

## Límites y siguiente ciclo

Lighthouse produce datos de laboratorio y varía con carga de CPU, cachés y
calentamiento del optimizador. Se mantuvieron versión, URLs, perfiles y presets
entre antes y después, pero las cifras no sustituyen telemetría real.

INP no puede inferirse de una navegación sin una muestra de interacciones. TBT
se usó como señal de bloqueo del hilo principal. Para el siguiente ciclo se
recomienda instrumentar Core Web Vitals de campo y atacar las cinco tareas largas
que aún dejan el backoffice móvil en TBT 580 ms; ese trabajo requiere perfilar
interacciones reales, no reestructurar la aplicación completa.
