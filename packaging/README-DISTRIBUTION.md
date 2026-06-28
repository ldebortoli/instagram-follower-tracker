# Seguidores 0.2.0 — paquete autónomo

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
