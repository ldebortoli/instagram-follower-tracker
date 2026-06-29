# Seguidores de Instagram

Programa local para registrar seguidores y seguidos de una o varias cuentas de Instagram, comparar
capturas diarias y avisar por popup o Telegram. Funciona por ejecución: el programa termina al
completar el chequeo y deja la siguiente ejecución al scheduler nativo del sistema.

## Estructura del repositorio

- `apps/desktop`: interfaz gráfica, CLI, schedulers y empaquetado multiplataforma.
- `apps/jo-bot`: bot de Telegram, configuración local, despliegue y documentación del servidor.
- `packages/core`: lógica compartida de Instagram, sesiones, cooldown, datos y reportes.

Las dos aplicaciones dependen del núcleo compartido, pero no dependen entre sí.

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
abierta ni solicitar elevación como administrador. En Windows, tanto la ejecución diaria como la
recuperación al iniciar sesión quedan limitadas a ese usuario. Las notificaciones de escritorio
requieren una sesión gráfica iniciada. En Linux, el popup usa `notify-send`.

## Aplicaciones autónomas

La página de [Releases](https://github.com/ldebortoli/instagram-follower-tracker/releases) publica
paquetes que no requieren instalar Python:

- `Windows-x86_64`: `seguidores-gui.exe` para doble clic y `seguidores.exe` para consola.
- `macOS-arm64`: `Seguidores.app` y `seguidores-cli` para equipos Apple Silicon.
- `macOS-x86_64`: `Seguidores.app` y `seguidores-cli` para equipos Intel.
- `Linux-x86_64`: `seguidores-gui` y `seguidores` dentro de un `.tar.gz`.

Cada archivo incluye un `.sha256` para comprobar su integridad. Windows SmartScreen y macOS
Gatekeeper pueden advertir durante la primera apertura porque todavía no se usan certificados
comerciales. La aplicación de macOS recibe una firma ad hoc; las instrucciones exactas están en el
`LEEME.md` de cada paquete.

También se puede instalar desde el código fuente.

## Requisitos e instalación desde el código

- Python 3.11 o posterior.
- Git.
- Una cuenta de Instagram propia con acceso legítimo.

La interfaz usa Tkinter, incluido normalmente con Python en Windows y macOS. En algunas
distribuciones Linux hay que instalarlo por separado; por ejemplo, en Debian/Ubuntu:

```bash
sudo apt install python3-tk libnotify-bin
```

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

## Interfaz gráfica y configuración inicial

Abrí la interfaz desde el entorno virtual:

```bash
seguidores setup
# Equivalente, y sin consola en Windows:
seguidores-gui
```

La ventana tiene cuatro secciones:

1. **Cuentas:** permite agregar varias cuentas, importar una sesión activa desde el navegador,
   ingresar un `sessionid` manualmente, iniciar sesión con contraseña y 2FA, consultar el estado
   de la cookie e importar una descarga JSON oficial.
2. **Notificaciones:** activa el popup, configura Telegram y envía un mensaje de prueba. El token se
   guarda en el almacén seguro del sistema.
3. **Automatización:** define la hora e instala el scheduler correcto para Windows, macOS o Linux.
   En el chequeo manual permite omitir el cooldown una sola vez, con una confirmación de riesgo; las
   ejecuciones automáticas siempre respetan la protección.
4. **Resultados:** muestra el reporte del último chequeo manual o importación.

Las consultas a Instagram, Telegram y al scheduler se ejecutan fuera del hilo de la ventana para que
la interfaz siga respondiendo. La contraseña y el código 2FA sólo viven durante el inicio de sesión y
no se escriben en la configuración.

La interfaz no se abre automáticamente al instalar. También se puede usar el flujo de terminal:

```bash
seguidores setup --terminal
seguidores init
seguidores account add personal --username MI_USUARIO
seguidores auth login personal
seguidores schedule install --time 09:00
seguidores run
```

La contraseña de Instagram se solicita de forma interactiva y no se guarda. Instaloader conserva
una cookie de sesión en el directorio local de la aplicación para las ejecuciones futuras. Tratá ese
archivo como una credencial.

Instagram puede devolver una autenticación parcial sin un `sessionid` válido. En ese caso, iniciá
sesión normalmente en `instagram.com` desde Chrome, Edge o Firefox y usá **Importar sesión del
navegador**. La aplicación valida la cookie antes de guardarla y no importa cookies de otros sitios.

También podés usar **Ingresar sessionid manualmente** y pegar el valor puro o
`sessionid=VALOR`. El campo está enmascarado, el valor se valida inmediatamente y nunca aparece en
logs ni diagnósticos. En consola se solicita de forma oculta, sin pasarlo como argumento:

```bash
seguidores auth import-sessionid personal
```

Un `sessionid` concede acceso a la cuenta igual que una contraseña: no lo compartas ni lo pegues en
comandos, archivos de configuración o capturas de pantalla.

Para varias cuentas:

```bash
seguidores account add trabajo --username CUENTA_TRABAJO --login-username CUENTA_TRABAJO
seguidores auth login trabajo
seguidores auth import-browser trabajo --browser edge
seguidores auth import-sessionid trabajo
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

Cuando Telegram está habilitado, una ejecución programada que termina con error envía una alerta
con la hora, la cuenta o etapa afectada y un resumen sanitizado. Los chequeos manuales no generan
esta alarma. Si el propio envío a Telegram falla, se registra en `logs/seguidores.log`; no es posible
avisar por Telegram que Telegram está caído.

Cuando un reporte supera el límite de un mensaje de Telegram, se adjunta completo como
`seguidores-reporte.txt`. El documento contiene todas las listas de usuarios y el mensaje incluye un
caption con la cuenta y la fecha del chequeo. Los reportes breves continúan enviándose como texto.

```bash
seguidores telegram disable
seguidores telegram disable --forget-token
seguidores popup disable
```

## Jo Bot: control desde Telegram

Jo Bot es el modo servidor basado en `python-telegram-bot`. Permanece ejecutándose con *long
polling*, programa el chequeo diario con `JobQueue` y permite configurar cuentas, cargar un
`sessionid`, iniciar chequeos y cambiar el horario desde un chat privado.

```powershell
# Preparación única
python -m pip install -e ".[bot]"

# Iniciar Jo Bot
jobot
```

`jobot` carga automáticamente `apps/jo-bot/.env.local`, reutiliza el token guardado en el almacén
seguro de Windows y permanece activo hasta presionar `Ctrl+C`.

`JO_BOT_ADMIN_USER_IDS` admite cualquier cantidad de IDs separados por coma. Los comandos
administrativos sólo responden a esos usuarios. `/start`, `/help` y `/debug` son públicos en chats
privados, grupos y canales.
`/debug` muestra el `Update` JSON sin notificar al administrador y lo adjunta como `.txt` si resulta
demasiado largo. Los chequeos manuales responden a quien los solicitó y los automáticos se envían al
primer ID configurado.

La guía completa para la prueba local y la instalación como servicio en una VM está en
[apps/jo-bot/docs/GOOGLE-CLOUD.md](apps/jo-bot/docs/GOOGLE-CLOUD.md).

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

## Diagnósticos HTTP

Cuando una operación HTTP falla, la pestaña **Resultados** y el log muestran:

- método y URL solicitada;
- headers y body de la request;
- estado, headers y body de la response;
- tipo y mensaje de la excepción original.

Los diagnósticos ocultan automáticamente contraseñas, cookies, `sessionid`, tokens, valores CSRF y
cabeceras de autorización. Si el error sucede antes de enviar una request, se indica explícitamente
que no hubo respuesta HTTP.

Ante una response `401`, `403` o `429`, la aplicación activa un cooldown persistente para la cuenta
usada al iniciar sesión. Durante ese período el chequeo manual y el scheduler se detienen antes de
enviar otra request. Para `429`, los dos primeros rechazos consecutivos esperan 2 horas; el tercero y
los siguientes esperan 24 horas. Los `401` y `403` esperan inicialmente 24 horas y escalan hasta un
máximo de 7 días. Cambiar de estado HTTP o pasar 30 días sin rechazos reinicia el contador. Una
sesión del navegador importada y validada, o un chequeo posterior exitoso, limpia el contador.
Varias cuentas locales que compartan el mismo `--login-username` comparten también el cooldown.

## Limitación importante de Instagram

La API oficial de Instagram no ofrece a este tipo de aplicación una lista completa de seguidores y
seguidos. El modo automático usa [Instaloader](https://instaloader.github.io/) con una sesión del
propio usuario. Es una integración no oficial y puede dejar de funcionar, recibir límites de tasa o
pedir una verificación adicional cuando Instagram cambie sus endpoints. El colector está aislado del
resto del programa para poder reemplazarlo sin perder el historial.

Instagram retiró en junio de 2026 la consulta GraphQL que Instaloader 4.15.1 usaba para localizar un
perfil. Desde la versión 0.2.5, el programa resuelve el perfil mediante `web_profile_info`, sin enviar
esa consulta obsoleta. Las consultas paginadas de seguidores y seguidos siguen a cargo de
Instaloader; cualquier rechazo queda registrado y activa el cooldown antes de un nuevo intento.

Usalo sólo con cuentas propias, con una frecuencia razonable y respetando las condiciones de
Instagram. El cooldown reduce reintentos riesgosos, pero no puede garantizar que Instagram no
aplique desafíos, bloqueos ni autenticación de dos factores.

## Desarrollo

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest --cov=seguidores --cov=seguidores_desktop --cov=jo_bot
```

Para generar el paquete autónomo del sistema actual:

```bash
python -m pip install -e ".[build-app]"
python apps/desktop/packaging/build.py
```

En Windows, el flujo recomendado para construir y probar sin intervención de Codex es:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build-windows.ps1" -Extract
```

El script reutiliza `.venv-build`, instala las dependencias, ejecuta Ruff y pytest, construye ambos
ejecutables, valida el SHA-256 y descomprime el resultado en `release\test-current`. En ejecuciones
posteriores se puede agregar `-SkipInstall` para evitar reinstalar dependencias; `-SkipTests` existe
para pruebas rápidas, pero no debe usarse al preparar una Release.

Para que, sólo después de completar correctamente todas esas validaciones, también prepare un
commit y suba la rama actual a `origin`, agregá `-PushCode`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build-windows.ps1" -Extract -PushCode
```

El mensaje automático es `update Seguidores to VERSION`. Se puede reemplazar agregando
`-CommitMessage "mensaje del commit"`. `-PushCode` incluye archivos nuevos mediante `git add --all`,
por lo que conviene revisar `git status` antes de ejecutarlo si el directorio contiene otros cambios.

Cada ejecución guarda su salida completa en `%TEMP%\Seguidores-build\build-latest.log`. Si algún
paso falla, también crea `%TEMP%\Seguidores-build\PROMPT-build-latest.txt`: adjuntá ambos archivos
en el chat de Codex para que pueda reconstruir el error sin depender de una captura parcial de la
terminal. Al iniciar una nueva ejecución, el script elimina ambos diagnósticos anteriores para que
no se acumulen archivos. Los paquetes de versiones anteriores dentro de `release` se conservan y no
bloquean un build nuevo. Antes de construir, el script cierra cualquier `seguidores.exe` o
`seguidores-gui.exe` iniciado desde una carpeta de este repositorio; primero solicita un cierre
normal y sólo fuerza la finalización si el proceso sigue activo. No cierra instalaciones ubicadas
fuera del proyecto.

PyInstaller no compila para otros sistemas desde uno solo. El workflow `package` construye y prueba
los cuatro paquetes en runners nativos; al publicar un tag `v*`, los adjunta automáticamente a un
GitHub Release.

## Licencia

MIT. Consultá [LICENSE](LICENSE).
