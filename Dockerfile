# ─── Stage 0: UI builder (uses cached node_modules from base) ────────────────
FROM node:20-alpine AS ui-builder

WORKDIR /ui
COPY ui/package.json ui/package-lock.json* ./
RUN npm install --legacy-peer-deps
COPY ui/ .
RUN npm run build

# ─── Stage 1: Runtime (FROM base with pre-installed deps) ───────────────────
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
