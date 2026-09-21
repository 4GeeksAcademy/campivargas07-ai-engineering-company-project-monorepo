FROM node:22-alpine

WORKDIR /app/uis

# Copy dependency manifests for layer caching
COPY website/package*.json ./website/
COPY backoffice/package*.json ./backoffice/

# Install dependencies (npm ci if lockfile exists, otherwise npm install with peer deps handling)
RUN cd /app/uis/website && \
    if [ -f package-lock.json ]; then \
      npm ci --no-audit --no-fund; \
    else \
      npm install --legacy-peer-deps --no-audit --no-fund; \
    fi

RUN cd /app/uis/backoffice && \
    if [ -f package-lock.json ]; then \
      npm ci --no-audit --no-fund; \
    else \
      npm install --legacy-peer-deps --no-audit --no-fund; \
    fi

# Copy application source code and startup script
COPY website ./website
COPY backoffice ./backoffice
COPY start.sh ./start.sh
RUN chmod +x ./start.sh

# Pre-create .next cache directories and set ownership to node user
RUN mkdir -p /app/uis/website/.next /app/uis/backoffice/.next /app/src && \
    chown -R node:node /app

USER node

EXPOSE 3000 3001

CMD ["./start.sh"]
