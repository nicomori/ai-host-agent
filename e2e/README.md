# HostAI — E2E Test Framework

Framework de automation testing para HostAI usando **Playwright** con el patron
**Page Object Model (POM)** y **Custom Fixtures**.

## Estructura del proyecto

```
e2e/
├── playwright.config.ts        # Configuracion de Playwright
├── package.json                # Dependencias y scripts
│
├── fixtures/
│   └── base.fixture.ts         # ★ Custom test con fixtures inyectados
│
├── helpers/
│   ├── api-client.ts           # Cliente HTTP tipado para el backend
│   └── test-data.ts            # Generadores de datos + tipos compartidos
│
├── pages/                      # Page Objects (1 clase = 1 pagina)
│   ├── login.page.ts
│   ├── dashboard.page.ts
│   └── floor-plan-editor.page.ts
│
└── tests/
    ├── global-setup.ts         # Verifica infra antes de todo
    ├── ui/                     # Tests de interfaz (browser)
    │   ├── auth.spec.ts
    │   ├── dashboard.spec.ts
    │   ├── rbac.spec.ts
    │   ├── chat.spec.ts
    │   └── floor-plan.spec.ts
    └── api/                    # Tests de API (sin browser)
        ├── health.spec.ts
        ├── auth.spec.ts
        ├── reservations.spec.ts
        ├── floor-plan.spec.ts
        ├── agent.spec.ts
        ├── config.spec.ts
        └── security.spec.ts
```

## Patron de diseno: Fixtures + POM

### 1. Custom Fixtures (`fixtures/base.fixture.ts`)

En vez de instanciar page objects manualmente con `new LoginPage(page)`,
los recibimos inyectados como parametros del test:

```typescript
// ❌ Antes (manual, repetitivo)
test("mi test", async ({ page }) => {
  const loginPage = new LoginPage(page);
  await loginPage.goto();
  await loginPage.loginAndWait("admin", "1234");
  const dashboard = new DashboardPage(page);
  // ...
});

// ✅ Ahora (fixtures inyectados, limpio)
test("mi test", async ({ loginAs, dashboardPage }) => {
  await loginAs("admin");
  await dashboardPage.createReservation({ ... });
});
```

**Fixtures disponibles:**

| Fixture | Tipo | Descripcion |
|---------|------|-------------|
| `api` | `ApiClient` | Cliente HTTP con API key (sin JWT) |
| `apiAsAdmin` | `ApiClient` | Cliente HTTP autenticado como admin |
| `loginPage` | `LoginPage` | Page object de /login (ya navegado) |
| `dashboardPage` | `DashboardPage` | Page object de /dashboard |
| `editorPage` | `FloorPlanEditorPage` | Page object del editor |
| `loginAs` | `(role?) => Promise` | Helper: login rapido como admin/writer/reader |

### 2. Page Objects (`pages/`)

Cada pagina tiene una clase con:
- **Locators** como propiedades `readonly` (definidos en el constructor)
- **Acciones** como metodos async (click, fill, navigate)
- **Assertions** como metodos con prefijo `expect` (expectCardWithName, expectError)

```typescript
// pages/dashboard.page.ts
export class DashboardPage {
  readonly newReservationBtn: Locator;   // ← Locator
  async createReservation(data) { ... } // ← Accion
  async expectCardWithName(name) { ... } // ← Assertion
}
```

### 3. test.step() para reportes legibles

Cada test multi-paso usa `test.step()` para que el reporte HTML muestre
pasos claros que un QA puede leer sin ver el codigo:

```typescript
test("crear y buscar reserva", async ({ dashboardPage, page }) => {
  await test.step("Crear reserva para hoy", async () => {
    await dashboardPage.createReservation({ ... });
  });

  await test.step("Refrescar y buscar por nombre", async () => {
    await page.reload();
    await dashboardPage.search(name);
    await dashboardPage.expectCardWithName(name);
  });
});
```

## Comandos

```bash
# Instalar dependencias
npm install
npx playwright install chromium

# Ejecutar todos los tests
npm test

# Solo API tests (rapido, sin browser)
npm run test:api

# Solo smoke tests (criticos)
npm run test:smoke

# Solo regression tests (completo)
npm run test:regression

# Con browser visible
npm run test:headed

# Modo debug (step-by-step)
npm run test:debug

# UI interactiva de Playwright
npm run test:ui

# Ver ultimo reporte HTML
npm run report
```

## Tags

Los tests estan tagueados en el nombre del `describe`:
- **@smoke** — Tests criticos, correr en cada PR (~30s)
- **@regression** — Suite completa, correr antes de release (~40s)
- **@api** — Solo backend, sin browser

Se filtran con `--grep`:
```bash
npx playwright test --grep @smoke
npx playwright test --grep "@api.*@smoke"
```

## Como agregar un test nuevo

### Test de UI

1. Agregar el locator necesario al Page Object correspondiente
2. Si necesitas una accion nueva, agregar metodo al Page Object
3. Crear el test en el `.spec.ts` correspondiente
4. Usar fixtures: `loginAs`, `dashboardPage`, etc.
5. Usar `test.step()` si el test tiene mas de 2 pasos

### Test de API

1. Si el endpoint no existe en `ApiClient`, agregar el metodo con JSDoc
2. Crear el test en el `.spec.ts` correspondiente
3. Usar fixture `api` (sin JWT) o `apiAsAdmin` (con JWT admin)

### Test data

- Usar `uniqueGuest("Prefix")` para nombres unicos
- Usar `futureDate(N)` para fechas (0=hoy, 1=manana)
- Nunca hardcodear datos que puedan colisionar entre tests paralelos

## Pre-requisitos

Para que los tests pasen necesitas:

1. **Backend corriendo** en http://localhost:8000
2. **Frontend corriendo** en http://localhost:5173
3. **PostgreSQL + Redis** corriendo (via Docker Compose)

```bash
# Desde la raiz del proyecto:
docker compose up -d          # PostgreSQL + Redis + API
cd ui && npm run dev          # Frontend
```

## Troubleshooting

| Problema | Solucion |
|----------|----------|
| "Backend not reachable" | Verificar `docker compose ps` y `curl localhost:8000/health` |
| Floor plan tests fallan | El plano puede estar vacio. Los tests tienen self-healing via API |
| Chat tests lentos | Normal, el agente usa Claude Haiku (~3-5s por respuesta) |
| Login falla para writer/reader | Recrear con admin: POST /api/v1/auth/users |
