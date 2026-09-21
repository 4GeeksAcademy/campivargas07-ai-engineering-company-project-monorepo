# Auditoría de Rendimiento Frontend — Brasaland

## Alcance y metodología

La línea base se ejecutó el 14 de septiembre de 2026 sobre builds de producción
de Next.js (`next build` + `next start`), no sobre el servidor de desarrollo.

- Lighthouse: 13.4.1.
- Chrome for Testing: 153.0.8010.36.
- Website: `http://127.0.0.1:3000`.
- Backoffice: `http://127.0.0.1:3101`.
- Perfiles: emulación móvil predeterminada de Lighthouse y preset de escritorio.
- Categorías: Performance, Accessibility, Best Practices y SEO.
- Backoffice: sesión real autenticada contra una API y una TinyDB temporales fuera
  del repositorio. Los informes confirman como URL final
  `/backoffice/overview`, sin redirección al login.

Lighthouse es una prueba de laboratorio y sus resultados pueden variar entre
ejecuciones. INP necesita interacciones reales suficientes; por ello, en estas
navegaciones se registra Total Blocking Time (TBT) como señal de capacidad de
respuesta del hilo principal.

## Resultados iniciales

| Aplicación | Ruta | Modo | Performance | Accessibility | Best Practices | SEO |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| Website | `/` | Móvil | 97 | 93 | 100 | 100 |
| Website | `/` | Escritorio | 100 | 93 | 100 | 100 |
| Website | `/careers` | Móvil | 94 | 100 | 100 | 100 |
| Website | `/careers` | Escritorio | 100 | 100 | 100 | 100 |
| Backoffice | `/backoffice/overview` | Móvil | 73 | 98 | 96 | 100 |
| Backoffice | `/backoffice/overview` | Escritorio | 100 | 98 | 96 | 100 |

### Core Web Vitals y señales de carga

| Aplicación / ruta | Modo | FCP | LCP | TBT | CLS | TTFB del documento |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Website `/` | Móvil | 0,8 s | 1,2 s | 200 ms | 0 | 10 ms |
| Website `/` | Escritorio | 0,3 s | 0,4 s | 10 ms | 0 | 30 ms |
| Website `/careers` | Móvil | 1,0 s | 1,5 s | 290 ms | 0 | 10 ms |
| Website `/careers` | Escritorio | 0,2 s | 0,3 s | 0 ms | 0 | 10 ms |
| Backoffice `/backoffice/overview` | Móvil | 0,6 s | 2,4 s | 1.310 ms | 0 | 0 ms |
| Backoffice `/backoffice/overview` | Escritorio | 0,2 s | 0,4 s | 0 ms | 0 | 10 ms |

Los informes HTML y JSON originales están en `audit/before/reports/`; las
capturas de la cabecera y métricas de cada informe están en
`audit/before/screenshots/`.

## Problemas, evidencia y causa raíz

### AUD-01 — Recuperación de hidratación en el backoffice

**Impacto:** alto en móvil. Lighthouse registró 2,9 s de trabajo de hilo
principal, 1,8 s de arranque de JavaScript, 12 tareas largas, TBT de 1.310 ms y
Performance de 73.

**Evidencia:** Best Practices detectó `Minified React error #418`. La tarea más
larga duró 604 ms dentro del runtime de React. El LCP fue texto del módulo de
incidencias y acumuló aproximadamente 987 ms de retraso de renderizado.

**Causa raíz:** `AuthProvider` inicializa `loading` como `false` durante SSR,
pero como `true` en el navegador cuando encuentra el token en `localStorage`.
`AuthGuard` produce entonces textos diferentes en servidor y primer render de
cliente (`Redirigiendo...` frente a `Verificando...`). React descarta el árbol
inicial y lo reconstruye en cliente.

**Corrección prevista:** usar un estado inicial determinista en servidor y
cliente, resolver la autenticación después del montaje y cubrir ambos caminos
con pruebas.

### AUD-02 — Imagen LCP del website no descubrible

**Impacto:** medio. El resultado actual sigue dentro del umbral saludable, pero
la carga depende de una imagen remota y carece de prioridad explícita.

**Evidencia:** `lcp-discovery-insight` indica que el recurso LCP no es
descubrible en el documento inicial y no tiene `fetchpriority=high`. El elemento
LCP es `section.hero`.

**Causa raíz:** el hero y las tarjetas usan URLs de Unsplash mediante
`background-image` en CSS o estilos inline. El navegador solo descubre esos
recursos después de descargar y analizar el CSS/DOM y Next.js no puede generar
variantes responsivas.

**Corrección prevista:** representar las fotografías con `next/image`, reservar
su geometría, declarar `sizes` y dar prioridad solo al hero.

### AUD-03 — Contraste insuficiente en CTA del website

**Impacto:** Accessibility queda en 93 en la home.

**Evidencia:** los enlaces `Reservar mesa` y `Descargar app` presentan una
relación de contraste 3,65:1 entre texto blanco y fondo `#ff2a5f`; Lighthouse
requiere 4,5:1 para ese tamaño de texto.

**Causa raíz:** el color primario fue elegido visualmente sin un token separado
para superficies que contienen texto pequeño.

**Corrección prevista:** oscurecer el token del CTA manteniendo la identidad
visual y verificar el contraste en ambos modos.

### AUD-04 — Jerarquía de encabezados incompleta

**Impacto:** afecta la navegación semántica en website y backoffice.

**Evidencia:** la home salta de `h2` a `h4` en la lista de historia; el dashboard
salta del `h1` del encabezado a los `h3` de KPIs.

**Causa raíz:** los niveles se escogieron por apariencia, aunque el estilo ya se
controla mediante CSS.

**Corrección prevista:** corregir los niveles sin alterar el aspecto visual.

## Análisis de reutilización

### Caso 1 — Selector de restaurante repetido

`ProductsTable` y `OrdersLedger` repiten la etiqueta, el `<select>`, el listado
de sedes y sus estilos. Los formularios inbound/outbound contienen una tercera
variante. Es candidato a un componente `RestaurantSelect` parametrizable, que
mantenga identificadores y comportamiento específicos de cada pantalla.

**Decisión:** extraer e integrar `RestaurantSelect` al menos en las dos vistas de
listado, con pruebas que preserven filtrado, accesibilidad y opciones.

### Caso 2 — Flujo de formularios inbound/outbound repetido

`InboundOrderForm` y `OutboundOrderForm` repiten selección de sede e ingrediente,
carga cancelable del catálogo, estado de envío, actualización optimista,
reconciliación y avisos. Una futura abstracción puede separar un hook de
catálogo/reconciliación de las reglas propias de cada movimiento. No se
fusionarán las validaciones de salida con las de entrada, porque eso ocultaría
reglas de negocio diferentes.

### Caso 3 — Campos visuales repetidos en Careers

La página `/careers` repite estilos inline de etiqueta, `input` y `select`.
Puede evolucionar a `FormField`, aunque no es prioritario: la vista ya alcanza
100 en accesibilidad y su impacto medido es menor que la hidratación del
backoffice.

## Orden de corrección

1. Corregir la hidratación de autenticación y volver a medir el dashboard.
2. Hacer descubrible y responsiva la imagen LCP del website.
3. Corregir contraste y jerarquía semántica.
4. Extraer el selector reutilizable sin cambiar reglas de dominio.
5. Ejecutar la medición final bajo la misma matriz y documentarla en
   `REPORT.md`.

## Estado de cierre

Los cuatro hallazgos quedaron corregidos y verificados el 14 de septiembre de
2026:

- **AUD-01 resuelto:** el primer render de `AuthProvider` es determinista y la
  consulta de sesión ocurre tras el montaje. Lighthouse dejó de registrar el
  error React de hidratación; el TBT móvil bajó de 1.310 ms a 580 ms.
- **AUD-02 resuelto:** las imágenes ahora se sirven localmente mediante
  `next/image`, con tamaños responsivos; el hero es descubrible desde el HTML,
  carga de forma eager y declara `fetchpriority=high`.
- **AUD-03 resuelto:** el CTA con texto blanco usa un rojo de contraste 4,95:1
  y los botones conservan explícitamente el color de texto. Accessibility en
  la home y Careers quedó en 100.
- **AUD-04 resuelto:** se repararon los saltos de encabezado sin cambios de
  presentación.
- **Reutilización aplicada:** `RestaurantSelect` sustituyó la duplicación en
  productos y órdenes, manteniendo las reglas de filtrado fuera del componente.

La comparación completa, las limitaciones y las validaciones están en
`REPORT.md`. Los reportes originales permanecen en `audit/before/` y
`audit/after/`.
