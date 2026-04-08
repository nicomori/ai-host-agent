# HostAI E2E — Playwright Test Runner
# =====================================
# Imagen liviana para ejecutar tests de Playwright en Drone CI.
#
# Uso local:
#   docker build -t hostai-e2e ./e2e
#   docker run --rm --network host hostai-e2e npx playwright test --grep @smoke
#
# En Drone CI la imagen se pushea a GHCR y se usa en cada pipeline step.

FROM node:20-slim

# Dependencias del sistema para Chromium headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /e2e

# Instalar dependencias (cache layer)
COPY package.json package-lock.json* ./
RUN npm ci

# Instalar Chromium de Playwright
RUN npx playwright install chromium

# Copiar codigo fuente
COPY . .

# Default: correr todos los tests
CMD ["npx", "playwright", "test", "--project=chromium"]
