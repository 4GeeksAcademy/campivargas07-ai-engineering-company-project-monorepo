#!/usr/bin/env bash
# ==============================================================================
# Brasaland Environment Disk Cleanup Script
# Safely frees up space in GitHub Codespaces without affecting Git PRs or databases
# ==============================================================================
set -euo pipefail

echo "=================================================="
echo "🧹 Limpiando entorno de GitHub Codespaces..."
echo "=================================================="

echo "1. Liberando caché de compilación de Docker (BuildKit)..."
docker builder prune -a -f || true

echo "2. Eliminando volúmenes anónimos huérfanos de Docker..."
docker volume prune -f || true

echo "3. Eliminando contenedores detenidos de Docker..."
docker container prune -f || true

echo "4. Limpiando cachés de gestores de paquetes de usuario..."
npm cache clean --force 2>/dev/null || true
rm -rf "${HOME}/.cache/ms-playwright" 2>/dev/null || true
uv cache clean 2>/dev/null || true
pip cache purge 2>/dev/null || true

if command -v sudo >/dev/null 2>&1; then
  echo "5. Limpiando caché de paquetes APT del sistema..."
  sudo apt-get clean 2>/dev/null || true
fi

echo "6. Limpiando artefactos temporales de compilación Next.js y cachés Python..."
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rm -rf "${REPO_DIR}/uis"/*/.next 2>/dev/null || true
rm -rf "${REPO_DIR}/.pytest_cache" "${REPO_DIR}/services"/*/.pytest_cache 2>/dev/null || true

echo ""
echo "=================================================="
echo "✅ Limpieza completada con éxito."
echo "📊 Estado actual del almacenamiento:"
echo "=================================================="
df -h /workspaces

