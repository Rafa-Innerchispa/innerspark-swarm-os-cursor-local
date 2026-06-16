# Instrucciones para agentes IA (Cursor / cualquier modelo)

**Proyecto:** InnerSpark Swarm-OS — PC Doctor S.A. (local, MongoDB, sin créditos cloud).

## Lee esto PRIMERO (orden obligatorio)

1. [`docs/INSTRUCCIONES_AGENTE.md`](docs/INSTRUCCIONES_AGENTE.md) — cómo retomar sin romper nada
2. [`docs/MAPA_PROYECTO.md`](docs/MAPA_PROYECTO.md) — visión, qué funciona, qué falta, decisiones tomadas
3. [`docs/ESQUEMA_MONGODB_DBxx.md`](docs/ESQUEMA_MONGODB_DBxx.md) — esquema canónico DB01–DB52
4. [`docs/CANON_CORRECCIONES_DBxx.md`](docs/CANON_CORRECCIONES_DBxx.md) — errores corregidos vs Notion
5. [`docs/SOPS_LOGICA_OPERATIVA.md`](docs/SOPS_LOGICA_OPERATIVA.md) — SOPs + invariantes Playbook
6. [`docs/RELACIONES_Y_FLUJOS.md`](docs/RELACIONES_Y_FLUJOS.md) — relaciones DB → Mongo + gates
7. [`docs/ARQUITECTURA_FLUJOS.md`](docs/ARQUITECTURA_FLUJOS.md) — por qué no las 52 DB en cada flujo
7. [`docs/ACCESO_RED.md`](docs/ACCESO_RED.md) — Windows usa 192.168.1.4, no localhost

## Reglas al programar

- **MongoDB** (`pcdoctor_swarm`) = fuente de verdad operativa. Notion = referencia humana.
- **No mezclar** con `/home/rlopez/inneros/` (hackathon) ni `/home/rlopez/agentes/`.
- **No copiar** lógica rota de Google AI Studio; solo plantillas/reglas.
- **Cabecera ≠ líneas:** cotización = `quotes` + `quote_lines` (DB27/DB38).
- **No fusionar** visita + reporte + cotización en un solo documento (`inspections` es legacy).
- **Hub-first:** todo entregable lleva `client_id`.
- **Secuenciales:** usar `tools/schema.py` → `next_serial()` (DB40), nunca inventar códigos.
- **`.env` nunca a git.** Credenciales solo en `.env`.
- **Cambios mínimos:** no refactorizar fuera del alcance pedido.
- **Español** en documentación y respuestas al usuario (Rafael).

## Código clave

| Archivo | Rol |
|---------|-----|
| `api/main.py` | FastAPI :8100 |
| `agents/crew.py` | Flujo multi-agente |
| `tools/mongo.py` | Acceso BD (legacy + v2) |
| `tools/schema.py` | Colecciones, índices, secuenciales |
| `tools/workflow_v2.py` | Flujo campo DB42→45→27/38 |
| `tools/gates.py` | Gates Playbook (hub, DB38, PDF-first, duplicados) |
| `scripts/migrate_v1_to_v2.py` | Migrar `inspections` → modelo v2 |

## Arranque

```bash
cd /home/rlopez/projects/innerspark-swarm-os-cursor-local
source venv/bin/activate
./run_api.sh
curl http://192.168.1.4:8100/status
```

## Fase actual

**Fase A:** flujo campo end-to-end con esquema v2 (DB04→DB45→DB27/38→DB40→DB41→DB52).

Ver checklist en `docs/MAPA_PROYECTO.md` sección 5.

## Cursor Cloud specific instructions

Esta sección es para agentes en el VM de Cursor Cloud (NO el servidor `192.168.1.4`).
El update script ya dejó listo: `venv` con `requirements.txt` y `admin/node_modules`.
MongoDB 8.0 (apt) ya está instalado a nivel de sistema; los datos viven en `/var/lib/mongodb`.

**Servicios (todo en localhost, no 192.168.1.4):**

| Servicio | Puerto | Arranque | Notas |
|----------|--------|----------|-------|
| MongoDB | 27017 | `mongod --dbpath /var/lib/mongodb --bind_ip 127.0.0.1 --port 27017` | No hay systemd en el contenedor; arráncalo a mano (p.ej. en tmux) antes que la API |
| API FastAPI | 8100 | `venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8100` | Requiere MongoDB arriba. `run_api.sh` no sirve aquí (espera `source venv/bin/activate` + puerto) |
| Admin Refine | 5173 | `npm run dev --prefix admin` | Lee `admin/.env` → `VITE_API_URL=http://localhost:8100/api/v1` |
| Portal estático | 8800 | `python3 -m http.server 8800 --directory portal` | Solo HTML estático |

**Setup no cubierto por el update script (hazlo en cada sesión nueva):**
- Arrancar `mongod` (ver tabla) — los datos persisten en `/var/lib/mongodb`.
- Init esquema una vez (idempotente): `venv/bin/python scripts/init_mongodb_schema.py`.
- `.env` (raíz) y `admin/.env` están gitignored y apuntan a `localhost`; si faltan, recréalos desde `.env.example` cambiando los hosts a `localhost`/`127.0.0.1`.

**Verificación rápida:** `curl http://localhost:8100/status` (no `192.168.1.4`).

**Caveats no obvios (comportamiento del código existente, no "bugs" del entorno):**
- **Ollama no está instalado.** `POST /inspection/start` (flujo CrewAI completo, agentes) falla sin Ollama en `:11434` con `neural-chat:7b` (+ `llava:7b` para visión). El resto de la API funciona sin Ollama: `/status`, CRUD `/api/v1/*`, `/ruc/lookup`, gates.
- **RUC lookup** cae a mock local (`tools/sri_mock.py`) si `RUC_API_USER/PASS` están vacíos — útil para pruebas sin credenciales.
- **Páginas admin genéricas** (Inventario, Catálogo, Proveedores, Cotizaciones, Visitas) usan `GenericList`, que renderiza la tabla SIN columnas definidas: se ven vacías aunque los datos sí cargan. Verifica datos vía `curl http://localhost:8100/api/v1/<recurso>`.
- **Configuración (empresas):** editar y "Guardar" hace PATCH y persiste, pero `tools/companies.ensure_companies()` se ejecuta en cada `GET /companies` y reescribe los campos a los valores por defecto; los logos 404 porque la página tiene hardcodeado `http://192.168.1.4:8100`.
- **No hay suite de tests.** El "build" del admin es `npm run build --prefix admin` (Vite). `npx tsc --noEmit` reporta errores preexistentes de `import.meta.env` (faltan tipos `vite/client`) que NO afectan al dev server ni al build.
