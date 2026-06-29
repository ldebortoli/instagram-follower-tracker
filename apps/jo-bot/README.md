# Jo Bot

Esta carpeta contiene exclusivamente la aplicación de Telegram:

- `src/jo_bot`: comandos, permisos, `JobQueue` y arranque.
- `scripts`: ejecución local en Windows.
- `deploy`: instalación como servicio `systemd`.
- `docs`: guía de Google Cloud.
- `tests`: pruebas específicas del bot.

Jo Bot usa la lógica compartida de `packages/core` y no importa código de `apps/desktop`.

Desde la raíz del repositorio:

```powershell
jobot
```

La configuración local privada está en `.env.local` dentro de esta carpeta. El archivo está
ignorado por Git; `.env.example` documenta sus variables.
