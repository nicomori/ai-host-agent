# HostAI E2E — Fast build using pre-baked base
# Base has: Playwright + Chromium + npm deps pre-installed
# This layer just copies test source code (< 1 second)

FROM europe-west3-docker.pkg.dev/nico-drone-ci-poc-2026/hostai/hostai-e2e-base:latest

WORKDIR /e2e

# Only copy source — deps already in base
COPY . .

CMD ["npx", "playwright", "test", "--project=chromium"]
