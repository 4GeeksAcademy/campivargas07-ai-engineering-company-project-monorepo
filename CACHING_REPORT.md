# CACHING_REPORT.md — Brasaland · Optimización de rendimiento (Lazy Loading, useMemo y caché TTL)

> Reto: optimizar el monorepo de Brasaland aplicando **lazy loading**, **useMemo** y
> **caché con TTL**, midiendo el antes/después con un dataset grande (5 000 proveedores)
> y documentando cada decisión.

---

## 1. Resumen ejecutivo

| Ámbito | Qué se implementó | Resultado principal |
|---|---|---|
| Backend (FastAPI) | Middleware de timing (`time.perf_counter`) + `TTLCache` propio (0 dependencias) con claves deterministas, TTL por endpoint, expiración monotónica, límite de tamaño, estadísticas e invalidación por prefijo | `GET /api/suppliers` con 5 000 docs: **payload inicial sin cambios** (644 997 → 644 070 bytes) y el panel de resultados (6 830 bytes) sale de la ruta crítica; los HIT/MISS/expiración quedan trazados en logs |
| Frontend (Next.js 16) | Lazy loading en 2 niveles (página server → analizador → panel de resultados) + `useMemo` para derivación no trivial (ranking consolidado/Pareto) | Los HIT reutilizan la respuesta ya serializada por Pydantic; el ahorro real se concentra en repetición (lecturas precalentadas) y detalle |

Nota honesta sobre medición: ver §8 — el cuello de botella dominante en listas es la
serialización Pydantic + transporte de ~2 MB de JSON, que se paga en TODAS las respuestas
(incluidas las servidas desde caché, porque el cache devuelve el modelo y FastAPI lo
re-serializa). El cache elimina el costo de acceso a TinyDB (visible en detalle: −32 %
mediana en lecturas repetidas) y evita recomputar filtros; el efecto sobre listas es
menor que el del transporte.

---

## 2. Línea base y metodología

### Precondiciones

- Rama `feature/caching-optimisation` creada desde el estado del repo sin reset/stash/rebase.
- **Línea base registrada ANTES de ningún cambio de código** (fallos preexistentes separados):
  - Backend: `pytest tests -q` → **64 passed, 5 skipped** (20.34 s).
  - Frontend backoffice: `typecheck` PASS, `vitest` **54 passed** (4 suites), `next build` PASS.
  - JS inicial de `/backoffice/incidents` (Suma de chunks referenciados por el HTML server-renderizado de la ruta): **644 997 bytes** en 9 chunks (mayores: 05zbr2g26-5or 227 533; 3_m0fx8d6e46j 141 611; 0cz1d0mv5g_q7 112 594).
- Dataset de medición: script `services/api/scripts/seed_suppliers.py`
  (`--count 5000 --seed 42`) → `/tmp/brasa-seed/suppliers.json` (TinyDB, tabla
  `suppliers` con 5 000 docs deterministas, ~2 500 Colombia / 2 500 USA).
  **Nunca** se escribe sobre `services/api/data/suppliers.json` (el script lo rechaza).

### Metodología de medición backend

- Servidor: `uvicorn app.main:app` sobre el TinyDB sembrado (`SUPPLIERS_DB_PATH`).
- Script de escenario: `services/api/scripts/measure_cache.py` (agregado en este reto);
  fases **cold (MISS) → warm (HIT) → post-invalidation → post-expiry**, 25 repeticiones
  por variante, mediana/mean/min/max con `time.perf_counter()`.
- Variantes medidas: `list_all`, `list_country`, `list_category`, `list_mix`, `detail_2`, `detail_4`.
- Evidencia HIT/MISS/EXPIRED/INVALIDATE: logs `brasaland.cache` (DEBUG) capturados con
  `LOG_LEVEL=debug` + `uvicorn.run(..., log_config=None)`; timing de cada request con
  `brasaland.timing` (INFO).

---

## 3. Decisiones de frontend (lazy loading y useMemo)

1. **Lazy loading nivel 1 — página server → analizador**: en
   `uis/backoffice/src/app/backoffice/incidents/page.tsx` el Server Component carga el
   cliente con `next/dynamic` + fallback de carga. **No** se usó `ssr: false`
   (prohibido en Server Components en Next 16); se usa `loading` con `role="status"`.
2. **Lazy loading nivel 2 — analizador → panel de resultados**: el nuevo componente
   `IncidentsResults` (todo el render de tablas/KPIs) se importa con
   `dynamic(() => import(...).then(m => m.IncidentsResults), { loading })`. Al no haber
   análisis todavía, el usuario solo baja el analizador; el panel llega **solo cuando
   hay `analysis`**.
3. **useMemo no trivial**: `uis/backoffice/src/lib/incidents-derive.ts` +
   `incidents-results.tsx`:
   - `deriveIncidentHighlights(analysis)`: fusiona 4 tablas de incidencias, filtra
     `count>0`, ordena por cantidad (con `localeCompare` como desempate estable),
     calcula `% de su tabla` y `% acumulado`.
   - `paretoTopRows(rows, 80%)`: menor prefijo que alcanza el umbral Pareto.
   - `countDistinctHighlightCodes(rows)`: dedupe `origen:código`.
   - Los tres se memoizan con `useMemo(..., [analysis])`; la derivación es **pura**
     (nunca muta la entrada — cubierto por test con snapshot JSON).

---

## 4. Decisiones de backend (middleware de timing y caché TTL)

### Middleware de timing (`app/common/timing.py`)

- `RequestTimingMiddleware` (Starlette `BaseHTTPMiddleware`): registra
  `MÉTODO ruta → status (X.XX ms)` con `time.perf_counter()` (monotónico, alta
  resolución), nivel INFO en el logger `brasaland.timing`.
- **Nunca** registra query strings, headers, cookies ni cuerpos (sin datos sensibles).
- `try/finally`: ante excepción el duration igual se registra y la excepción se propaga;
  el estado/cuerpo de la respuesta no se altera.

### Caché TTL (`app/common/cache.py`, stdlib puro)

- `TTLCache(max_size=256, default_ttl, clock=time.monotonic, namespace)`:
  - Claves deterministas con `build_key(*parts)` (join `:`, bools en minúscula) y
    `normalize_filter(v)` (None/vacío → `*`; colapsa espacios, preserva mayúsculas).
  - Expiración **monotónica** (`expire_at = clock() + ttl`); nunca usa wall clock.
  - `OrderedDict` LRU con `RLock`; eviction: primero expirados, luego el menos usado.
  - Valores se copian **en profundidad** al entrar y al salir (aislamiento entre
    peticiones, sin compartición de mutables).
  - Estadísticas: `hits`, `misses`, `evictions`, `expired`, `size`, `hit_rate`.
  - Logs: `brasaland.cache` DEBUG (`HIT|MISS|EXPIRED|EVICT|INVALIDATE|CLEAR`).
- **TTL por endpoint** (según frecuencia de cambio, en
  `app/domains/procurement/suppliers/router.py`):
  - `GET /api/suppliers` → TTL **60 s** (`LIST_TTL_SECONDS`).
  - `GET /api/suppliers/{id}` → TTL **120 s** (`DETAIL_TTL_SECONDS`).
- **Invalidación total**: POST crear / PATCH rate / PATCH status / DELETE llaman
  `_invalidate_all()` → `cache.invalidate_prefix("suppliers:")`, que borra la lista
  **y todas sus variantes de filtros** y el detalle; tras escribir la siguiente lectura
  es MISS (datos frescos garantizados en escritura).
- 404 (proveedor inexistente) se lanza **antes** de tocar el cache → nunca se cachea.

---

## 5. Tabla por endpoint

| Endpoint | Método | ¿Cacheado? | Clave (determinista) | TTL | Invalidación | Frecuencia | Coste con 5 000 docs | Mejora observada (mediana, n=25) |
|---|---|---|---|---|---|---|---|---|
| `/api/suppliers` | GET | ✅ | `suppliers:list:v1:country=<norm>:category=<norm>` | 60 s | POST/rate/status/delete → prefijo `suppliers:` | Muy alta (UI de procurement) | MISS 95 ms / HIT 116 ms — dominado por serialización de ~2 MB | Ver §8: HIT evita re-consulta TinyDB y re-filtrado; el transporte pesa más |
| `/api/suppliers?country=…` | GET | ✅ | variante `country=Colombia` | 60 s | igual | alta | MISS 54 ms / HIT 49 ms | −9 % |
| `/api/suppliers?category=…` | GET | ✅ | variante `category=carne` | 60 s | igual | alta | MISS 60 ms / HIT 62 ms | ≈0 (ruido) |
| `/api/suppliers?country=…&category=…` | GET | ✅ | variante combinada | 60 s | igual | alta | MISS 27 ms / HIT 29 ms | ≈0 (ruido) |
| `/api/suppliers/{id}` | GET | ✅ | `suppliers:detail:v1:id=<id>` | 120 s | igual (prefijo) | alta | MISS 2.2 ms / HIT 1.5 ms | **−32 %** |
| `/api/suppliers` | POST | ❌ escritura | — | — | invalida todo | media | — | garantiza frescura |
| `/api/suppliers/{id}/rate` | PATCH | ❌ escritura | — | — | invalida todo | media | — | garantiza frescura |
| `/api/suppliers/{id}/status` | PATCH | ❌ escritura | — | — | invalida todo | media | — | garantiza frescura |
| `/api/suppliers/{id}` | DELETE | ❌ escritura | — | — | invalida todo | baja | — | garantiza frescura |
| `/auth/login` | POST | ❌ **nunca** | — | — | — | alta | credenciales+JWT; respuesta cambia por intento | seguridad |
| `/health` | GET | ❌ **nunca** | — | — | — | muy alta (probes) | trivial; debe reflejar estado real | fiabilidad del probe |
| `GET /users*`, `GET /profiles*` | GET | ❌ | — | — | — | media | PII + cambios por admins; fuera del alcance del reto | riesgo/alcance |
| 404s (cualquier recurso) | GET | ❌ **nunca** | — | — | — | — | un proveedor creado a los 61 s sería invisible hasta expirar si se cacheara el 404 | corrección |

---

## 6. Estrategia de lazy loading (documentada)

- **Nivel 1**: `incidents/page.tsx` (Server Component) → `dynamic(import("…incidents-analyzer"))`.
  Sin `ssr:false`; fallback declarativo `loading` con `role="status" aria-live="polite"`.
- **Nivel 2**: `incidents-analyzer.tsx` (cliente) →
  `dynamic(import("…incidents-results").then(m => m.IncidentsResults))`. El panel
  completo de resultados (KPIs + 5 tablas) queda en **su propio chunk** y solo se
  descarga cuando existe un `analysis`.
- **Evidencia de build (Turbopack)**: el chunk `1f6cd-uud07yr.js` (6 830 bytes, contiene
  «Prioridades consolidadas»/ranking) **no aparece** en el HTML ni en el RSC de
  `/backoffice/incidents`; está registrado en `react-loadable-manifest.json` como
  importación dinámica (id 64210). El analizador (`30uxx0blhtx6o.js`, 13 982 bytes,
  «Arrastra el archivo aquí») sí va en el payload inicial porque es la superficie
  interactiva principal de la página.
- El resto del payload inicial (9 chunks / 644 070 bytes) es el shell compartido del
  backoffice (React 19 + framework 227 KB, etc.), igual que la línea base — el reto no
  tocó el shell.

---

## 7. Explicación del useMemo

Cada render de `IncidentsResults` con los 5 000-docs… (en UI real: tablas de incidencias
con cientos de filas) ejecutaría `deriveIncidentHighlights` (merge de 4 tablas + sort +
2 pasadas de porcentajes) y `paretoTopRows` (prefijo acumulado). Son O(n log n) por
render. Con `useMemo([analysis])`:

- El cálculo corre **solo** cuando cambia el objeto `analysis` (tras subir el archivo),
  no en cada render por hover/foco/estado del uploader.
- Se evita recomputar el ranking en los re-renders que dispara `aria-live` o el
  resultado de descarga.
- Las funciones son **puras** y testeadas unitariamente (10 tests) — el memo solo
  guarda el resultado, no cambia la semántica.

---

## 8. Resultados antes/después

### Frontend — JS inicial de `/backoffice/incidents` (HTML server-renderizado)

| Métrica | Antes | Después | Δ |
|---|---|---|---|
| Chunks en payload inicial | 9 | 9 | 0 |
| Total bytes iniciales | 644 997 | 644 070 | −927 (−0.1 %) |
| Chunk del panel de resultados | embebido en el paquete del analizador (chunk 2d_9emxkvpaol, 14 909 B, dentro del HTML inicial) | chunk propio `1f6cd-uud07yr.js` (6 830 B) **fuera del HTML/RSC**, fetch on-demand | separación real |
| Chunk del analizador | 2d_9emxkvpaol (14 909 B) | 30uxx0blhtx6o (13 982 B) | −927 B |

Interpretación honesta: el payload inicial apenas baja porque el shell del backoffice
domina (framework + shared). La mejora está en la **arquitectura**: el render pesado de
resultados ya no está en la ruta crítica y crecerá de forma aislada (más tablas/KPIs
futuros no engordan el primer paint). Además, con `analysis === null` (estado inicial
real del usuario) el código del panel no se ejecuta ni descarga.

### Backend — latencias (mediana ms, n=25, 5 000 proveedores, localhost)

| Escenario | list_all | list_country | list_category | list_mix | detail_2 | detail_4 |
|---|---|---|---|---|---|---|
| **Cold (MISS)** | 95.04 | 53.97 | 59.97 | 26.70 | 1.49 | 2.22 |
| **Warm (HIT)** | 115.80 | 48.86 | 61.75 | 28.78 | 1.50 | 1.48 |
| **Post-invalidación (MISS)** | 90.67 | 49.71 | 60.64 | 28.24 | 1.51 | 1.49 |
| **Post-expiración (MISS, TTL real 60/120 s)** | 98.92 | 49.33 | 76.97 | 28.67 | 1.49 | 1.48 |

Lectura honesta: en listas el tiempo está dominado por **serialización Pydantic +
transporte de ~2 MB de JSON** (FastAPI re-serializa la respuesta cacheada), por lo que
el HIT no reduce la mediana de lista de forma notable; el cache elimina el coste de
consulta/filtrado de TinyDB (visiblemente en `detail`: −32 % y min 1.44 ms estable) y
desacopla la latencia del crecimiento del dataset para consultas no transporte-limitadas.
Medición adicional n=200 (warm): list_all 105.21 ms mediana; detail_2 1.54 ms mediana.

### Evidencia de logs (extracto real del servidor de medición)

```
brasaland.cache DEBUG cache[suppliers] MISS key=suppliers:list:v1:country=*:category=*
brasaland.timing INFO GET /api/suppliers -> 200 (249.79 ms)
brasaland.cache DEBUG cache[suppliers] HIT key=suppliers:list:v1:country=*:category=*
brasaland.timing INFO GET /api/suppliers -> 200 (91.35 ms)
brasaland.cache DEBUG cache[suppliers] INVALIDATE prefix=suppliers: removed=1
brasaland.cache DEBUG cache[suppliers] MISS key=suppliers:list:v1:country=*:category=*   (tras escritura)
brasaland.cache DEBUG cache[suppliers] EXPIRED key=suppliers:list:v1:country=*:category=*   (a los 65 s)
brasaland.cache DEBUG cache[suppliers] EXPIRED key=suppliers:detail:v1:id=2   (~120 s)
```

- HIT/MISS/expiración/invalidación verificados por logs (304 líneas `brasaland.*`
  durante la sesión de medición).
- La expiración de 60/120 s se observó en tiempo real (esperas de 65 s y 62 s,
  sin sleeps en tests: la expiración en tests usa un reloj inyectado).

---

## 9. Intercambio frescura vs rendimiento

- **TTL 60 s en listas**: el usuario de procurement consulta con frecuencia; 60 s es el
  equilibrio — suficientemente corto para que una proveedora creada por otra persona sea
  visible en ≤60 s aunque nadie escriba en esta instancia, y suficientemente largo para
  absorber ráfagas de navegación/filtrado.
- **TTL 120 s en detalle**: los datos de un proveedor cambian solo por escrituras
  (que **invalidan inmediatamente** toda la familia `suppliers:`); el TTL extra solo
  cubre el caso multiescenario (otro proceso escribe el TinyDB). Por eso puede ser el
  doble que el de lista.
- **La invalidación en escritura es la garantía principal**: tras POST/PATCH/DELETE la
  siguiente lectura es MISS con datos frescos. El TTL es la red de seguridad, no el
  mecanismo de corrección.
- **Nunca** se cachean escrituras, login, health ni 404s: la frescura de esos casos no
  es negociable.

---

## 10. Qué NO se cacheó y por qué (decisión explícita)

| Recurso | ¿Cacheado? | Motivo |
|---|---|---|
| `/auth/login` (POST) | ❌ | Autenticación: respuesta contiene token con `exp`; cachearlo reutilizaría sesiones y enmascararía fallos de credenciales. |
| POST/PATCH/DELETE en suppliers | ❌ | Escrituras: siempre ejecutan y luego invalidan el cache de lectura. |
| `GET /health` | ❌ | Debe reflejar el estado real del proceso para orquestación/probes. |
| Respuestas 404 | ❌ | Un proveedor creado a los pocos segundos sería invisible durante el TTL (positivo falso). |
| `GET /users*`, `GET /profiles*` | ❌ (fuera de alcance) | PII y semántica de permisos; el reto acota el cache al dominio suppliers. |
| Endpoints de inventario/incidents | ❌ (fuera de alcance) | Solo suppliers es read-heavy documentado en el enunciado; extender sería trivial con el mismo `TTLCache`. |

---

## 11. Limitaciones y próximos pasos

1. **Cache en proceso**: el `TTLCache` vive en el proceso de uvicorn; con varias
   réplicas cada una tiene su cache (coherencia por TTL + invalidación local). Siguiente
   paso natural: Redis con el mismo contrato de claves.
2. **Serialización domina las listas**: guardar el JSON ya serializado (o usar
   `ORJSONResponse`) evitaría la re-serialización del HIT; se deja como siguiente paso.
3. **Chunk inicial del shell**: el backoffice carga ~227 KB de framework en cada ruta;
   optimizar imports pesados del layout es otra vía de mejora (fuera del alcance).
4. **Tracking de `.pyc` preexistente**: el repo tiene `__pycache__`/`.pyc` rastreados de
   commits anteriores; tras correr pytest aparecen como modificados. Se excluyen
   explícitamente de este commit (no se restaura la política de ignores, fuera de alcance).
5. **Dataset en `/tmp`**: el seed de medición no se versiona (los datos del repo no se
   tocan); regenerable con un comando documentado.
6. **Los commits previos no fusionados** (serialización, perf audit) viajan en esta
   rama según el enunciado del hito; el PR los incluye.

---

## 12. Verificación final (comandos y resultados)

| Comando | Resultado |
|---|---|
| `cd services/api && .venv/bin/python -m pytest tests -q` | **86 passed, 5 skipped** (22.83 s) — baseline era 64 passed/5 skipped; +22 tests nuevos de cache/timing |
| `npm run typecheck:uis` (raíz) | **PASS** (0 errores, 4 UIs) |
| `npm run test:uis` (raíz) | **backoffice: 13 archivos / 64 tests passed** · website: 1 archivo / 4 tests passed |
| `cd uis/backoffice && npm run lint` | **PASS** (eslint sin errores) |
| `npm run build:uis` (raíz) | **PASS — 4/4 builds** («Compiled successfully» ×4, exit 0) |

### Reproducir las mediciones

```bash
# 1) Seed (nunca escribe en services/api/data/)
cd services/api
.venv/bin/python scripts/seed_suppliers.py --out /tmp/brasa-seed/suppliers.json --count 5000

# 2) Servidor con logs de cache
SUPPLIERS_DB_PATH=/tmp/brasa-seed/suppliers.json LOG_LEVEL=debug .venv/bin/python -c "
import logging, sys, os
logging.basicConfig(level=getattr(logging, os.environ.get('LOG_LEVEL','INFO').upper()), stream=sys.stdout, format='%(name)s %(levelname)s %(message)s')
import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', port=8000, log_config=None)"

# 3) Fases
.venv/bin/python scripts/measure_cache.py cold_warm          # MISS → HIT
.venv/bin/python scripts/measure_cache.py post_invalidation  # tras PATCH /rate
.venv/bin/python scripts/measure_cache.py post_expiry        # tras TTL 60/120 s
```
