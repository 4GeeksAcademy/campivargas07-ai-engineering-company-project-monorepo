# 🎯 Historial de Proyectos — Brasaland

> Notas técnicas de cada hito completado, para mantener contexto y tracción entre entregas.

---

## **`</> Propuesta de Arquitectura de Backend`**

### 🧠 ¿Qué hice?

Redacté el documento **`docs/ARCHITECTURE_PROPOSAL.md`** — la propuesta de arquitectura del backend de Brasaland que el CTO (Nicolás) pidió antes de empezar a programar.

### La decisión central

Elegí un **Monolito Modular con capas por dominio** — ¿qué significa eso?

- **Monolito**: todo el backend es una sola aplicación que se despliega junta. No microservicios.
- **Modular**: el código está organizado en **10 dominios de negocio** (locales, menú, ventas, inventario, compras, clientes, lealtad, RRHH, capacitación, analytics).
- **Capas**: cada dominio se divide en router → service → repository (la estructura clásica de FastAPI).

### ¿Por qué?

| Para Brasaland | Para el equipo |
|---|---|
| 14 locales, 2 países, mucha complejidad real | Equipo pequeño, evitar sobreingeniería |
| Datos en tiempo real (ventas, stock) | FastAPI es async nativo |
| Múltiples frontends (app, web, backoffice) | Una API unificada sirve a todos |

### Lo que incluye el documento

1. **Patrón arquitectónico** y por qué descarté microservicios, serverless, MVC y hexagonal.
2. **Estructura de carpetas** completa (`services/backend/`) siguiendo las convenciones oficiales de FastAPI.
3. **Rutas y endpoints** organizados por dominio con tabla detallada.
4. **Separación frontend/backend** — monorepo compartido, CORS, JWT, variables de entorno.
5. **Decisiones técnicas** — FastAPI, PostgreSQL, SQLAlchemy async, Redis, Docker.
6. **5 riesgos** con mitigaciones concretas (acoplamiento, common/ desordenado, confusión Pydantic vs SQLAlchemy, etc.).

---

## **`🔐 AUTH-02 — Flujos de autenticación y vistas protegidas en el frontend`**

### 🧠 ¿Qué hice?

Implementé la infraestructura completa de autenticación para el frontend del monorepo Brasaland, conectando con la API existente que ya exige JWT en rutas protegidas. Esto cierra el ciclo de seguridad: la API rechaza requests sin token → el frontend ahora puede obtener, almacenar, enviar y limpiar ese token.

### 📋 Archivos creados o modificados

| Archivo | Propósito |
|---------|-----------|
| `packages/shared/types/auth.ts` | Tipos TypeScript para LoginRequest, TokenResponse, RegisterRequest, UserOut, ProfileOut, AuthMeResponse, ProfileUpdate |
| `packages/shared/types/index.ts` | Modificado: agrega `export * from './auth'` para exportar tipos de autenticación |
| `packages/shared/auth/api.ts` | Cliente API (`AuthApiClient`) con manejo de token en localStorage, headers Authorization, manejo de 401 |
| `packages/shared/auth/context.tsx` | Contexto de React (`AuthProvider`) con hooks: `useAuth()`, `login()`, `register()`, `logout()`, `refreshUser()` |
| `packages/shared/auth/index.ts` | Barrel export de api.ts y context.tsx |
| `uis/backoffice/src/app/login/page.tsx` | Vista `/login` — formulario email+password, manejo de errores, redirección al éxito |
| `uis/backoffice/src/app/register/page.tsx` | Vista `/register` — formulario con campos obligatorios y opcionales, validación client-side |
| `uis/backoffice/src/app/account/profile/page.tsx` | Vista `/account/profile` — muestra datos de usuario y perfil, modo edición con PUT a `/profiles/me` |
| `uis/backoffice/src/middleware.ts` | Middleware Next.js — permite rutas públicas (/login, /register), protege el resto |
| `uis/backoffice/src/components/auth-provider.tsx` | Wrapper `'use client'` que envuelve children con `AuthProvider` |
| `uis/backoffice/src/app/layout.tsx` | Modificado: envuelve `{children}` con `<AuthProviderWrapper>` |
| `uis/backoffice/src/lib/api.ts` | Re-export del `authApi` para uso interno del backoffice |
| `uis/backoffice/src/lib/auth/` | Copia local de los módulos compartidos (api.ts, context.tsx, index.ts) |
| `uis/backoffice/src/lib/types/auth.ts` | Copia local de tipos de autenticación |
| `uis/backoffice/tsconfig.json` | Modificado: agregado `baseUrl: "."` y paths `@/*` |
| `memory-bank/progress.md` | Actualizado con estado de AUTH-02 y próximos pasos |

### 🔧 Decisiones técnicas importantes

1. **Almacenamiento en `localStorage`** — el ticket lo especifica así. En producción se recomendaría cookies `HttpOnly` + `Secure`, pero para esta entrega seguimos el contrato.

2. **Código compartido en `packages/shared/`** — la lógica de autenticación vive aquí para ser reutilizable en todas las apps del monorepo (backoffice, loyalty-app, operations-ui, talent-pipeline-tracker). El website público no la usa.

3. **Copia local en `uis/backoffice/src/lib/auth/`** — se copió el código compartido localmente porque TypeScript no podía resolver importaciones relativas que cruzan fuera del `src/` del proyecto Next.js. El código fuente权威 sigue en `packages/shared/`.

4. **Protección de rutas en cliente** — el middleware de Next.js se ejecuta en el servidor y no tiene acceso a `localStorage`. La protección real se hace en el cliente mediante el hook `useAuth()` que verifica si hay token. Las vistas que requieren sesión hacen `redirect` a `/login` si `user` es `null`.

5. **Flujo de registro** — `POST /users` (registro) → `POST /auth/login` (login automático) → almacena token → redirige a `/`. El usuario no necesita hacer login manual después de registrarse.

6. **Manejo de 401** — el `AuthApiClient.handleResponse()` intercepta respuestas 401, limpia el token de localStorage y redirige a `/login`. Esto aplica a todas las llamadas API protegidas.

7. **Website público no afectado** — `uis/website` no recibe ningún cambio. No tiene AuthProvider, no tiene middleware de autenticación.

### ✅ Verificaciones ejecutadas

| Verificación | Resultado |
|-------------|-----------|
| `tsc --noEmit` (typecheck) | ✅ Pasado — 0 errores de tipos en archivos nuevos (1 error pre-existente en `.next/dev/types/validator.ts` unrelated) |
| Estructura de archivos | ✅ Todos los archivos creados en las rutas correctas |
| Importaciones | ✅ Todas las rutas de importación verificadas y funcionales |
| Git status | ✅ Todos los archivos rastreados en la rama `feature/auth-frontend` |

### ⚠️ Limitaciones y pasos manuales pendientes

1. **API debe estar corriendo** — el frontend asume `http://localhost:8000` como API base. Si la API no está corriendo, login/registro fallarán con error de red.

2. **Variable de entorno** — crear `uis/backoffice/.env.local` con:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

3. **CORS en la API** — asegurarse de que la API permite requests desde `http://localhost:3000` (puerto del frontend Next.js).

4. **Protección server-side incompleta** — el middleware actual no verifica tokens (no puede acceder a localStorage). Para producción, implementar tokens en cookies HttpOnly que el middleware sí pueda leer.

5. **Otras apps del monorepo** — `loyalty-app`, `operations-ui` y `talent-pipeline-tracker` aún no tienen autenticación. Se puede reutilizar el mismo patrón.

6. **Error pre-existente** — `.next/dev/types/validator.ts` tiene un error de tipos que no está relacionado con AUTH-02.

### 🧪 Instrucciones para probar

#### 1. Registro
```
1. Iniciar la API: cd services/api && uvicorn app.main:app --reload
2. Iniciar el frontend: cd uis/backoffice && npm run dev
3. Navegar a http://localhost:3000/register
4. Llenar el formulario:
   - Email: test@brasaland.com
   - Contraseña: password123
   - Nombre: Juan Pérez (opcional)
   - Teléfono: +57 300 1234567 (opcional)
   - Dirección: Cra. 37 #8A-29 (opcional)
5. Hacer clic en "Crear cuenta"
6. Esperado: redirección automática a http://localhost:3000/ (ya logueado)
```

#### 2. Login
```
1. Si ya estás logueado, cerrar sesión (ver paso 5)
2. Navegar a http://localhost:3000/login
3. Ingresar email y contraseña del paso anterior
4. Hacer clic en "Iniciar sesión"
5. Esperado: redirección a http://localhost:3000/
6. Login fallido: se muestra mensaje "Incorrect email or password"
```

#### 3. Perfil
```
1. Estando logueado, navegar a http://localhost:3000/account/profile
2. Verificar que se muestran: email, rol, estado, nombre, teléfono, dirección
3. Hacer clic en "Editar"
4. Modificar nombre o teléfono
5. Hacer clic en "Guardar cambios"
6. Esperado: mensaje "Perfil actualizado correctamente"
7. Hacer clic en "Cancelar" para salir del modo edición sin guardar
```

#### 4. Logout
```
1. Estando logueado, cualquier vista protegida debería tener un botón de cerrar sesión
   (o ejecutar authApi.logout() desde la consola del navegador)
2. Esperado: token eliminado de localStorage, redirección a http://localhost:3000/login
3. Verificar: intentar navegar a http://localhost:3000/account/profile → redirige a /login
```

#### 5. Manejo de 401
```
1. Abrir DevTools → Application → Local Storage → eliminar "brasaland_token"
2. Recargar la página
3. Esperado: redirección automática a http://localhost:3000/login
4. Alternativa: con el token eliminado, intentar acceder a /account/profile
5. Esperado: la página detecta que no hay usuario y redirige a /login
```

#### 6. Acceso público (website)
```
1. Navegar a http://localhost:3000 (o el puerto del website)
2. Verificar que el website carga normalmente
3. No debe haber redirecciones a /login
4. No debe haber llamadas a /auth/me
5. El website permanece completamente público sin autenticación
```

#### 7. Verificar token en localStorage
```
1. Abrir DevTools → Application → Local Storage
2. Después de login: debe existir "brasaland_token" con valor JWT
3. Después de logout: "brasaland_token" debe estar eliminado
4. En Network tab: verificar que requests a /auth/me incluyen header "Authorization: Bearer <token>"
```

---

*Documento interno — Brasaland Digital*