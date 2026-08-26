# Brasaland — Monorepo de Ingeniería de IA

[![4Geeks Academy](https://img.shields.io/badge/4Geeks-Academy-blue)](https://4geeksacademy.com)
[![AI Engineering](https://img.shields.io/badge/track-AI%20Engineering-green)](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)

> _Available in English and Spanish. Para versión en español, ver [README.es.md](./README.es.md)._

---

## 📌 Visión General del Proyecto

**Brasaland** es una cadena de restaurantes a la brasa con 14 sedes en Colombia y Florida (USA). Este monorepo implementa la plataforma integral AI-ready para gestión de pedidos, incidencias, directorio de proveedores y autenticación centralizada mediante JWT.

---

## 🚀 Guía Rápida: Cómo Levantar el Proyecto

### 1. Requisitos Previos

- **Node.js**: v18.0 o superior (se recomienda v20+)
- **npm**: v9.0 o superior
- **Python**: v3.11 o superior
- **pip** / **venv**

---

### 2. Configuración de Variables de Entorno

El repositorio incluye plantillas `.env.example`. Copia los archivos de ejemplo antes de iniciar:

```bash
# 1. Configuración general en la raíz
cp .env.example .env

# 2. Configuración para el servicio Backend API
cp services/api/.env.example services/api/.env

# 3. Configuración para el Backoffice
cp uis/backoffice/.env.example uis/backoffice/.env

# 4. Configuración para el Website
cp uis/website/.env.example uis/website/.env
```

---

### 3. Instalación de Dependencias

```bash
# Instalar dependencias de frontend (workspaces npm en la raíz)
npm install

# Instalar dependencias del backend Python
pip install -r services/api/requirements.txt
```

---

### 4. Levantar los Servicios

Recomendamos utilizar dos terminales separadas (una para el Backend y otra para el Frontend):

#### 🔹 Terminal 1: Backend FastAPI (Puerto 8000)

```bash
cd services/api
uvicorn app.main:app --reload --port 8000
```
- **API URL:** `http://localhost:8000`
- **Documentación Swagger Interactiva:** `http://localhost:8000/docs`
- **Healthcheck:** `http://localhost:8000/health`

#### 🔹 Terminal 2: Frontend Backoffice Next.js (Puerto 3000)

```bash
# Desde la raíz del monorepo:
npm run dev:backoffice

# O directamente desde la carpeta:
cd uis/backoffice
npm run dev
```
- **Backoffice URL:** `http://localhost:3000`
- **Página de Login:** `http://localhost:3000/login`
- **Página de Registro:** `http://localhost:3000/register`
- **Página de Perfil:** `http://localhost:3000/account/profile`
- **Analizador de Incidencias:** `http://localhost:3000/incidents`

#### 🔹 (Opcional) Terminal 3: Website Público Next.js (Puerto 3001)

```bash
# Desde la raíz del monorepo:
npm run dev:website
```
- **Website URL:** `http://localhost:3001`

---

## 🔐 Autenticación y Cuentas de Usuario

El sistema cuenta con autenticación completa mediante **JWT (JSON Web Tokens)**:

1. **Crear una cuenta**: Visita `http://localhost:3000/register` o haz clic en **Registrarse** en la barra superior. Los usuarios registrados desde el backoffice se crean automáticamente con rol `admin`.
2. **Iniciar sesión**: Visita `http://localhost:3000/login` o haz clic en **Iniciar Sesión**. El token JWT se almacena de forma segura en `localStorage` y se incluye en los encabezados `Authorization: Bearer <token>`.
3. **Mi Perfil**: Una vez conectado, haz clic en tu usuario en la cabecera para ver o editar tu información de contacto (`/account/profile`).
4. **Cerrar sesión**: Puedes cerrar sesión en cualquier momento mediante el botón **Salir** de la cabecera.

---

## 🧪 Pruebas y Validación

### Pruebas Unitarias del Backend (Python / pytest)
```bash
python3 -m pytest services/api/tests
```

### Typecheck de TypeScript (Frontend / Next.js)
```bash
npm run typecheck:uis
```

### Build de Producción (Next.js)
```bash
npm run build:uis
```

---

## 📂 Estructura del Repositorio

```text
ai-engineering-company-project-monorepo/
├── .env.example               # Configuración global de variables de entorno
├── AGENTS.md                  # Protocolo y directrices para agentes de IA
├── memory-bank/               # Documentación viva del proyecto (projectbrief, techContext, progress)
├── packages/
│   └── shared/                # Tipos y utilidades compartidas (@repo/shared-types, auth)
├── services/
│   └── api/                   # Backend FastAPI (Auth, Users, Profiles, Suppliers, Incidents)
│       ├── app/
│       ├── tests/             # Pruebas unitarias con pytest
│       ├── requirements.txt   # Dependencias de Python
│       └── .env.example
├── uis/                       # Aplicaciones Frontend
│   ├── backoffice/            # Panel de control Next.js (Auth, KPIs, Incidents, Suppliers)
│   ├── website/               # Sitio web corporativo Next.js
│   ├── loyalty-app/           # Aplicación de fidelización
│   └── operations-ui/         # Interfaz operativa
└── docs/                      # Documentación de arquitectura y datos
```

---

## 👥 Contribuidores & Créditos

Proyecto desarrollado como parte del programa de **AI Engineering** de **4Geeks Academy**.
