# Jo Bot en Google Cloud

Jo Bot puede ejecutarse como servicio de Telegram, pero desde 0.4.0 no consulta Instagram ni
programa chequeos. Sirve para ayuda, `/debug` y administración de nombres de perfiles.

Variables requeridas:

```text
SEGUIDORES_TELEGRAM_BOT_TOKEN=TOKEN_DE_BOTFATHER
JO_BOT_ADMIN_USER_IDS=267832653,793942836
JO_BOT_TIMEZONE=America/Argentina/Buenos_Aires
```

Para probarlo localmente desde la raíz del repositorio:

```powershell
python -m pip install -e ".[bot]"
jobot
```

En una VM Linux, instalá el proyecto en un entorno virtual, configurá las mismas variables en el
archivo de entorno del servicio y usá `apps/jo-bot/deploy/jo-bot.service` como base. No hace falta
guardar cookies ni credenciales de Instagram.
