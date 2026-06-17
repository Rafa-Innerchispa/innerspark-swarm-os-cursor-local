# Arranque automático — InnerOS / Ralphi IA

**No necesitas recordar comandos.** Tras un apagón o `sudo reboot`, todo vuelve solo.

## Ya configurado en tu servidor

- `swarm-api` y `swarm-admin` → **systemd habilitados** (arrancan solos)
- **Crontab @reboot** → ngrok + seed demo + archivo con tu URL
- Tras reiniciar, lee: `data/public_demo_url.txt`

## Qué arranca automáticamente

| Servicio systemd | Qué hace |
|------------------|----------|
| `swarm-api` | FastAPI en `:8100` + MongoDB Docker |
| `swarm-admin` | Admin React en `:5173` (build + preview) |
| `swarm-ngrok` | Túnel público → `:5173/inneros` |
| `swarm-bootstrap` | Seed demo + guarda URL en `data/public_demo_url.txt` |
| `ralf-portal` | Portal `:8800` |

## Tu URL pública (después de reiniciar)

```bash
cat /home/rlopez/projects/innerspark-swarm-os-cursor-local/data/public_demo_url.txt
```

## Solo si algo falla (raro)

```bash
sudo systemctl status swarm-api swarm-admin swarm-ngrok
sudo systemctl restart swarm-api swarm-admin swarm-ngrok
```

## Reinstalar servicios (tras cambios)

```bash
bash /home/rlopez/projects/innerspark-swarm-os-cursor-local/scripts/install_services.sh
```

## ngrok

El token debe estar en `.env` del proyecto:

```
NGROK_AUTHTOKEN=tu_token
```

O en `~/.config/ngrok/ngrok.yml` (una sola vez: `ngrok config add-authtoken ...`).
