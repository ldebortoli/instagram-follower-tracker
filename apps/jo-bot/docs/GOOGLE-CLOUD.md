# Jo Bot: prueba local y Google Cloud

Jo Bot usa `python-telegram-bot` con *long polling*. No necesita una URL pública, un dominio ni abrir
puertos HTTP. Sólo una instancia del bot debe estar ejecutándose a la vez: dos procesos usando el
mismo token compiten por las actualizaciones de Telegram.

## Probarlo en esta PC

El archivo local `apps/jo-bot/.env.local` contiene los IDs autorizados y está ignorado por Git. El
token no se copia allí: Jo Bot reutiliza la credencial que la aplicación de escritorio guardó en el
almacén seguro de Windows.

Desde PowerShell, en la raíz del proyecto, la preparación se hace una sola vez:

```powershell
python -m pip install -e ".[bot]"
```

Después, el comando local completo es:

```powershell
jobot
```

`jobot` carga `apps/jo-bot/.env.local` automáticamente y queda activo hasta presionar `Ctrl+C`. Como
alternativa, el script explícito continúa disponible:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\apps\jo-bot\scripts\run-local.ps1"
```

La terminal debe quedar abierta durante esta prueba. `Ctrl+C` detiene el bot. Si no hubiera un token
guardado, se configura sin mostrarlo en pantalla con:

```powershell
seguidores telegram configure --chat-id 267832653
```

## Usuarios y comandos

`JO_BOT_ADMIN_USER_IDS` acepta cualquier cantidad de IDs separados por coma. Todos tienen permisos
administrativos completos. El primero recibe los reportes programados y los errores automáticos.

Los comandos de configuración y chequeo sólo funcionan en chat privado y sólo para esos IDs.
`/start`, `/help` y `/debug` son públicos en chats privados, grupos y canales. `/debug` devuelve en el
mismo chat el JSON del `Update` recibido por Telegram, incluyendo el `user_id`; no notifica al
administrador ni concede permisos. Si la respuesta es extensa, se envía como archivo `.txt`.

Para autorizar usuarios adicionales:

1. La otra persona abre el bot, o lo usa en un grupo, y envía `/debug`.
2. Esa persona copia el valor `user.id` de la respuesta y se lo pasa al administrador.
3. Se edita `apps/jo-bot/.env.local`:

   ```text
   JO_BOT_ADMIN_USER_IDS=267832653,793942836,OTRO_ID
   ```

4. Se reinicia Jo Bot.

Comandos disponibles:

```text
/account ALIAS USUARIO [LOGIN]
/remove ALIAS
/accounts
/session ALIAS
/check [ALIAS]
/schedule HH:MM
/schedule_off
/status
/debug
/cancel
/help
```

Un `/check` manual envía el reporte completo al usuario autorizado que hizo el pedido. Los chequeos
programados se envían al primer ID. Los reportes largos se adjuntan como `.txt` con un caption.

## Antes de crear la cuenta de Google

La prueba gratuita de Google Cloud ofrece USD 300 por 90 días, exige un medio de pago válido y no
cobra mientras la cuenta siga siendo de prueba. No hay que pulsar **Activar** o **Upgrade**: esa
acción convierte la cuenta a facturación paga. Si no se actualiza, al vencer el plazo o agotarse el
crédito Google detiene los recursos.

La capa gratuita permanente incluye una VM `e2-micro` en `us-central1`, `us-east1` o `us-west1`,
pero una IPv4 externa en uso se factura actualmente a USD 0,005 por hora salvo una hora gratuita al
mes. Por eso este instructivo garantiza costo de bolsillo cero sólo durante la prueba gratuita. Antes
de que termine, hay que eliminar la VM o revisar conmigo una variante IPv6 sin costo.

Fuentes oficiales:

- [Programa gratuito de Google Cloud](https://cloud.google.com/free/docs/free-cloud-features)
- [Precios de red e IP externas](https://cloud.google.com/vpc/network-pricing)
- [Presupuestos y alertas](https://cloud.google.com/billing/docs/how-to/budgets)

Un presupuesto envía alertas, pero no es un límite duro de gasto. Para esta primera prueba, la
protección efectiva es no actualizar la cuenta gratuita a paga.

## Crear la VM en Google Cloud

Cuando quieras hacerlo, podemos recorrer estos pasos juntos mirando cada pantalla.

1. Entrar a [Google Cloud Console](https://console.cloud.google.com/) y elegir **Comenzar gratis**.
   Registrar un medio de pago válido. Una retención temporal de verificación no es un cobro.
2. Confirmar en **Facturación > Descripción general** que diga **Free trial account**. No pulsar
   **Activate**, **Upgrade** ni **Actualizar**.
3. Crear un proyecto llamado `jo-bot`.
4. Abrir **Compute Engine > Instancias de VM** y habilitar la API cuando Google lo solicite.
5. Elegir **Crear instancia** con estos valores:
   - Nombre: `jo-bot`
   - Región: `us-central1`
   - Zona: cualquiera de `us-central1`
   - Serie: `E2`
   - Tipo de máquina: `e2-micro`
   - Sistema: Debian 12, x86/64
   - Disco: estándar persistente, 10 GB
   - Firewall: no habilitar tráfico HTTP ni HTTPS
6. Crear la VM y usar el botón **SSH** de la consola.

## Descargar e instalar Jo Bot en la VM

En la terminal SSH:

```bash
sudo apt-get update
sudo apt-get install -y git gh
gh auth login
```

Elegir `GitHub.com`, protocolo `HTTPS` y autenticación desde navegador. Después:

```bash
gh repo clone ldebortoli/instagram-follower-tracker
cd instagram-follower-tracker
sudo bash apps/jo-bot/deploy/install.sh
```

El instalador crea un usuario Linux restringido, un entorno virtual en `/opt/jo-bot`, los datos
privados en `/var/lib/jo-bot` y el servicio `systemd`. Todavía no lo inicia.

## Configurar token e IDs en el servidor

1. En Telegram, abrir `@BotFather`, crear el bot con `/newbot` y copiar el token.
2. En la VM:

   ```bash
   sudo nano /etc/jo-bot.env
   ```

3. Reemplazar `PEGAR_TOKEN_DE_BOTFATHER`, conservar el primer ID y guardar con `Ctrl+O`, Enter,
   `Ctrl+X`.
4. Iniciar el servicio:

   ```bash
   sudo systemctl enable --now jo-bot
   sudo systemctl status jo-bot --no-pager
   ```

5. En Telegram, enviar `/status`. Para agregar el segundo usuario, usar `/debug`, editar la lista y
   reiniciar:

   ```bash
   sudo nano /etc/jo-bot.env
   sudo systemctl restart jo-bot
   ```

El archivo `/etc/jo-bot.env` sólo es legible por `root` y el usuario del servicio. No pegar el token
ni el `sessionid` en GitHub, capturas o este chat.

## Configurar Instagram desde Telegram

Ejemplo para una cuenta observada con la misma cuenta de inicio de sesión:

```text
/account personal USUARIO_INSTAGRAM
/session personal
```

Después de `/session personal`, enviar únicamente el `sessionid`. El bot intenta borrar ese mensaje,
lo valida con Instagram y guarda la sesión con permisos privados. Telegram no ofrece cifrado de
extremo a extremo para bots; usar sólo el chat privado y revocar la sesión desde Instagram si el
token se expone.

Para observar una cuenta distinta a la usada para iniciar sesión:

```text
/account trabajo CUENTA_OBSERVADA CUENTA_QUE_INICIO_SESION
/session trabajo
```

Luego probar:

```text
/check personal
/schedule 09:00
/status
```

## Operación y actualización

Ver logs en vivo:

```bash
sudo journalctl -u jo-bot -f
```

Actualizar después de publicar cambios en GitHub:

```bash
cd ~/instagram-follower-tracker
git pull
sudo bash apps/jo-bot/deploy/install.sh --restart
```

Detener temporalmente:

```bash
sudo systemctl stop jo-bot
```

Evitar cualquier continuidad al finalizar la prueba gratuita:

1. Ir a **Facturación** y comprobar días/crédito restantes.
2. Antes del vencimiento, detener y eliminar la VM desde Compute Engine.
3. Confirmar que no queden discos ni direcciones IP reservadas.
