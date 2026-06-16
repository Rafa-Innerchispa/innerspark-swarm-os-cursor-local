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

Este entorno NO es el servidor `192.168.1.4`: todo corre en `localhost`. La VM
trae instaladas las dependencias (venv Python en `./venv`, `admin/node_modules`)
y el binario de MongoDB; el update script solo refresca dependencias, no arranca
servicios. Cada sesión debes arrancar los servicios tú.

**Servicios (3) y cómo arrancarlos:**

- **MongoDB** (necesario para todo): no es un `systemd` service aquí. Arráncalo así
  (datadir/log ya existen): `sudo mongod --dbpath /var/lib/mongodb --bind_ip 127.0.0.1 --port 27017 --logpath /var/log/mongodb/mongod.log` (déjalo en segundo plano, p.ej. tmux). Verifica: `mongosh pcdoctor_swarm --eval 'db.runCommand({ping:1})'`.
- **API FastAPI** (`:8100`): `./run_api.sh` (usa `./venv`). Endpoints REST en `/api/v1/*`, Swagger en `/docs`. La primera vez corre `python scripts/init_mongodb_schema.py` para crear las ~63 colecciones (idempotente).
- **admin** (Refine/Vite React, `:5173`): `npm --prefix admin run dev`. Lee la API desde `VITE_API_URL` (`admin/.env`); en esta VM apúntalo a `http://localhost:8100/api/v1` (el `.env.example` usa `192.168.1.4`).
- **portal** (estático, `:8800`): `./run_portal.sh`.

**Caveats no obvios:**

- `.env` se crea copiando `.env.example`; los defaults `127.0.0.1` ya sirven en esta VM.
- El flujo multi-agente `POST /inspection/start` (CrewAI) requiere **Ollama** + modelo
  `neural-chat:7b`, que **no** están instalados aquí (descarga pesada). El resto del
  producto (admin ERP: clientes, inventario, catálogo, cotizaciones, visitas, branding)
  funciona sin Ollama. Instala Ollama solo si necesitas probar ese flujo IA.
- No hay tests ni ESLint configurados. El "lint/build" del admin es `npm --prefix admin run build` (Vite). `tsc --noEmit` por separado reporta errores de `import.meta.env` por falta de tipos `vite/client` en `tsconfig` (preexistente); Vite los resuelve, no afecta a `dev`/`build`.
- Whisper (`:9001`) y n8n son opcionales y externos; sin ellos, subir audio y notificar fallan, pero el resto opera.
