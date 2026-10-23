# Jo Bot

Bot auxiliar de Telegram. Mantiene `/start`, `/help`, `/debug`, `/account`, `/remove`, `/accounts`
y `/status`.

El acceso directo a Instagram, la carga de `sessionid` y los chequeos programados fueron retirados.
La comparación se realiza cargando los JSON oficiales en la aplicación de escritorio.

```powershell
python -m pip install -e ".[bot]"
jobot
```

La configuración local se lee desde `apps/jo-bot/.env.local`. `JO_BOT_ADMIN_USER_IDS` admite IDs
separados por comas. `/start`, `/help` y `/debug` son públicos.
