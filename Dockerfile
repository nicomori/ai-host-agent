# ─── Stage 0: Get cached UI node_modules from base ──────────────────────────
FROM europe-west3-docker.pkg.dev/nico-drone-ci-poc-2026/hostai/hostai-api-base:latest AS deps-cache

# ─── Stage 1: UI builder (near-instant with cached node_modules) ────────────
FROM node:20-alpine AS ui-builder

WORKDIR /ui
COPY --from=deps-cache /app/_ui_node_modules ./node_modules
COPY ui/package.json ui/package-lock.json* ./
RUN npm install --legacy-peer-deps 2>/dev/null || true
COPY ui/ .
RUN npm run build

# ─── Stage 2: Runtime (FROM base with pre-installed Python deps) ────────────
FROM europe-west3-docker.pkg.dev/nico-drone-ci-poc-2026/hostai/hostai-api-base:latest AS runtime

WORKDIR /app

# Copy full source
COPY . .

# Copy built UI from ui-builder stage
COPY --from=ui-builder /ui/dist /app/ui/dist

RUN chown -R appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
