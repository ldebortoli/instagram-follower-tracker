# Seguidores de Instagram

Programa local para registrar seguidores y seguidos de una o varias cuentas de Instagram, comparar
capturas diarias y avisar por popup o Telegram. Funciona por ejecución: el programa termina al
completar el chequeo y deja la siguiente ejecución al scheduler nativo del sistema.

## Qué informa

- **No te siguen de vuelta:** cuentas que seguís pero no te siguen.
- **No seguís de vuelta:** cuentas que te siguen pero no seguís.
- **Dejaron de seguirte:** estaban entre tus seguidores en la captura anterior y ya no están.
- Nuevos seguidores, cuentas que empezaste a seguir y cuentas que dejaste de seguir.
- Historial local de cantidades y relaciones en SQLite.

La primera ejecución crea una línea de base. Recién desde la segunda captura se puede afirmar que
alguien empezó o dejó de seguirte.

## Compatibilidad y funcionamiento en segundo plano

| Sistema | Scheduler | Recupera una ejecución perdida |
| --- | --- | --- |
| Windows | Programador de tareas | `StartWhenAvailable` y disparador al iniciar sesión |
| macOS | `launchd` | `RunAtLoad` y control interno de ejecución diaria |
| Linux | timer de usuario de `systemd` | `Persistent=true` |
| Linux sin systemd | `cron` | entrada diaria más `@reboot` |

El chequeo se instala para el usuario actual, sin requerir que una ventana del programa quede
abierta. Las notificaciones de escritorio requieren una sesión gráfica iniciada. En Linux, el popup
usa `notify-send`.

## Requisitos e instalación

- Python 3.11 o posterior.
- Git.
- Una cuenta de Instagram propia con acceso legítimo.

```bash
git clone https://github.com/ldebortoli/instagram-follower-tracker.git
cd instagram-follower-tracker
python -m venv .venv
```

Activar el entorno e instalar:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

```bash
# macOS / Linux
source .venv/bin/activate
python -m pip install -e .
```

No muevas ni borres ese entorno virtual después de instalar la tarea. Si cambia de ruta, ejecutá
`seguidores schedule uninstall` y volvé a instalarla desde el nuevo entorno.

## Configuración inicial

El asistente reúne todos los pasos, pero no se ejecuta automáticamente:

```bash
seguidores setup
```

También se puede configurar paso a paso:

```bash
seguidores init
seguidores account add personal --username MI_USUARIO
seguidores auth login personal
seguidores schedule install --time 09:00
seguidores run
```

La contraseña de Instagram se solicita de forma interactiva y no se guarda. Instaloader conserva
una cookie de sesión en el directorio local de la aplicación para las ejecuciones futuras. Tratá ese
archivo como una credencial.

Para varias cuentas:

```bash
seguidores account add trabajo --username CUENTA_TRABAJO --login-username CUENTA_TRABAJO
seguidores auth login trabajo
seguidores account list
```

Cada cuenta local tiene su propia sesión. `--login-username` también permite observar una cuenta
accesible desde otra sesión autorizada.

## Telegram

1. Creá un bot con BotFather.
2. Agregalo al canal y dale permiso para publicar. Para un chat privado, primero enviale un mensaje.
3. Configurá un ID numérico o el alias público del canal con formato `@canal`.

```bash
seguidores telegram configure --chat-id @mi_canal
seguidores telegram test
```

El token se guarda en el almacén seguro del sistema mediante `keyring`, no en `config.json`. En
servidores sin almacén de credenciales se puede definir `SEGUIDORES_TELEGRAM_BOT_TOKEN` en el
entorno del proceso, teniendo en cuenta que el scheduler también debe recibir esa variable.

```bash
seguidores telegram disable
seguidores telegram disable --forget-token
seguidores popup disable
```

## Importación oficial de Instagram

Como alternativa manual, solicitá en Instagram una descarga de tu información en formato JSON y
pasá el directorio descomprimido:

```bash
seguidores import-export personal /ruta/a/la/exportacion
```

El importador busca `followers_*.json` y `following.json` dentro de sus subdirectorios. Esto crea la
misma clase de captura que el modo automático.

## Otros comandos

```bash
seguidores run --account personal
seguidores run --if-due
seguidores history personal --limit 30
seguidores schedule status
seguidores schedule uninstall
seguidores config show
seguidores config path
```

Datos por plataforma:

- Windows: `%APPDATA%\Seguidores`
- macOS: `~/Library/Application Support/Seguidores`
- Linux: `${XDG_CONFIG_HOME:-~/.config}/seguidores`

Para pruebas o instalaciones portables, `SEGUIDORES_HOME` reemplaza esa ubicación.

## Limitación importante de Instagram

La API oficial de Instagram no ofrece a este tipo de aplicación una lista completa de seguidores y
seguidos. El modo automático usa [Instaloader](https://instaloader.github.io/) con una sesión del
propio usuario. Es una integración no oficial y puede dejar de funcionar, recibir límites de tasa o
pedir una verificación adicional cuando Instagram cambie sus endpoints. El colector está aislado del
resto del programa para poder reemplazarlo sin perder el historial.

Usalo sólo con cuentas propias, con una frecuencia razonable y respetando las condiciones de
Instagram. El programa no evita desafíos, bloqueos ni autenticación de dos factores.

## Desarrollo

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest --cov=seguidores
```

## Licencia

MIT. Consultá [LICENSE](LICENSE).
