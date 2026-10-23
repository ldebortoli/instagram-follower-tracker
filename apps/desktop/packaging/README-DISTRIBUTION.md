# Seguidores de Instagram

## Abrir

- Windows: doble clic en `seguidores-gui.exe`.
- macOS: abrí `Seguidores.app`.
- Linux: ejecutá `./seguidores-gui`.

## Importar

En **Importar JSON** configurá un nombre local y el usuario dueño del reporte. Después elegí:

- uno o más `followers_*.json` de Instagram;
- `following.json` de Instagram.

Presioná **Comparar y guardar captura**. No se solicita contraseña ni `sessionid`, no se consulta
Instagram y no se instala una tarea diaria.

Los reportes de Threads se rechazan con un mensaje explícito. Si tu archivo de seguidores contiene
enlaces a `threads.com`, volvé a solicitar o localizar la sección de seguidores de Instagram.

La configuración y el historial se guardan en los datos locales del usuario. Telegram es opcional;
los reportes largos se envían como `seguidores-reporte.txt` con un caption descriptivo.
