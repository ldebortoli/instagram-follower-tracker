# Seguidores de Instagram

Aplicación local y multiplataforma para comparar los archivos JSON oficiales de seguidores y
seguidos de Instagram. No inicia sesión, no usa `sessionid`, no consulta endpoints privados y no
instala chequeos diarios.

## Qué informa

- Cuentas que seguís y no te siguen de vuelta.
- Cuentas que te siguen y no seguís de vuelta.
- Cambios respecto de la importación anterior: bajas, altas y cambios en seguidos.
- Historial local de capturas en SQLite.
- Reporte opcional por popup o Telegram; si es largo se adjunta como `.txt`.

La primera importación queda guardada como línea de base. Los cambios aparecen desde la segunda.

## Uso desde la interfaz gráfica

Abrí `seguidores-gui` o el ejecutable correspondiente a tu sistema:

1. Elegí un perfil guardado o ingresá un nombre local y el usuario de Instagram.
2. Seleccioná uno o más `followers_*.json`.
3. Seleccioná `following.json`.
4. Presioná **Comparar y guardar captura**.

El importador acepta los formatos habituales del Centro de cuentas, incluidos archivos de
seguidores divididos en varias partes. También valida el origen: un reporte de Threads se rechaza
para evitar compararlo accidentalmente con datos de Instagram.

El archivo `followers.json` usado como ejemplo en este desarrollo contiene la clave
`text_post_app_text_post_app_followers` y enlaces a `threads.com`; corresponde a Threads. Para
Instagram necesitás el archivo que normalmente se llama `followers_1.json` y contiene
`relationships_followers` o una lista de relaciones con enlaces a `instagram.com`.

## Migración desde 0.3.x

Al abrir la GUI 0.4.0 por primera vez, la aplicación:

- conserva perfiles, notificaciones e historial;
- descarta los campos antiguos de sesión y automatización;
- elimina las sesiones locales guardadas;
- intenta quitar la tarea diaria antigua del sistema.

## Instalación desde el código

Requiere Python 3.11 o posterior. Tkinter viene incluido normalmente en Windows y macOS.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
seguidores-gui
```

En macOS/Linux, activá el entorno con `source .venv/bin/activate`.

## Jo Bot

Jo Bot mantiene `/start`, `/help`, `/debug` y la administración básica de perfiles. Ya no acepta
`sessionid`, no ejecuta chequeos y no programa tareas. La comparación de JSON se hace en la GUI.

```powershell
python -m pip install -e ".[bot]"
jobot
```

`JO_BOT_ADMIN_USER_IDS` acepta cualquier cantidad de IDs separados por comas. `/start`, `/help` y
`/debug` siguen siendo públicos.

## Datos locales

- Windows: `%APPDATA%\Seguidores`
- macOS: `~/Library/Application Support/Seguidores`
- Linux: `${XDG_CONFIG_HOME:-~/.config}/seguidores`

`SEGUIDORES_HOME` permite reemplazar esa ubicación para pruebas o instalaciones portables.

## Desarrollo y build

```powershell
ruff check .
pytest
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build-windows.ps1" -Extract -PushCode
```

El script ejecuta validaciones, crea el paquete y, con `-PushCode`, sube los cambios. Si falla,
genera `%TEMP%\Seguidores-build\PROMPT-build-latest.txt` y
`%TEMP%\Seguidores-build\build-latest.log`; una nueva ejecución reemplaza ambos.

## Licencia

MIT.
