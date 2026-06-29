# Seguidores 0.2.5 — paquete autónomo

Este paquete incluye Python y las dependencias necesarias. No hace falta instalar Python ni abrir el
repositorio.

## Windows

- Abrí `seguidores-gui.exe` con doble clic.
- Usá `seguidores.exe` desde PowerShell o CMD para acceder a la consola.
- Windows puede mostrar SmartScreen porque el ejecutable todavía no posee una firma comercial.

## macOS

- Abrí `Seguidores.app`.
- El archivo `seguidores-cli` ofrece la interfaz de consola desde Terminal.
- La aplicación tiene una firma ad hoc, no una firma notarizada de Apple. En la primera apertura
  puede ser necesario hacer Control-clic, elegir **Abrir** y confirmar.

## Linux

- Ejecutá `./seguidores-gui` para la interfaz o `./seguidores` para la consola.
- Si el explorador quitó el permiso, ejecutá `chmod +x seguidores seguidores-gui`.
- El paquete x86_64 se genera sobre Ubuntu 22.04 y requiere una distribución con glibc compatible.
  Los popups también requieren `notify-send`.

## Automatización y datos

La tarea diaria se instala para el usuario actual desde la pestaña **Automatización**. Si movés la
aplicación o el ejecutable después de instalarla, eliminá la tarea antes de moverlo y volvé a
instalarla desde la nueva ubicación.

Las contraseñas de Instagram no se guardan. Las cookies de sesión, la configuración, el historial y
los logs se almacenan en el perfil del usuario, no dentro de esta carpeta.

La forma recomendada de autenticación es **Importar sesión del navegador** después de iniciar sesión
en `instagram.com`. Los diagnósticos muestran request y response, pero ocultan cookies, tokens,
contraseñas, cabeceras de autorización y valores CSRF.

Como alternativa, **Ingresar sessionid manualmente** acepta el valor de esa cookie en un campo
enmascarado, lo valida contra Instagram y recién entonces guarda la sesión local. El `sessionid` debe
tratarse como una contraseña.

Si Instagram responde `401`, `403` o `429`, se activa un cooldown persistente de 24 horas que
crece ante rechazos consecutivos hasta un máximo de 7 días. Ni el chequeo manual ni la tarea diaria
envían requests durante ese período. Importar y validar una sesión activa permite recuperarse.

Con Telegram habilitado, cualquier error de una ejecución programada envía además una alerta
sanitizada al chat configurado. Si Telegram no está disponible, el fallo de notificación queda en
`logs/seguidores.log`.
