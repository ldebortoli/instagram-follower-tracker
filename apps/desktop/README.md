# Aplicaciones de escritorio

- `src/seguidores_desktop`: GUI y CLI para importar exportaciones JSON.
- `packaging`: entradas y armado de ejecutables con PyInstaller.
- `scripts`: automatización del build de Windows.
- `tests`: pruebas específicas de escritorio.

Desde la raíz:

```powershell
seguidores-gui
seguidores import-json --help
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build-windows.ps1" -Extract -PushCode
```

No se instala ninguna tarea programada. La primera ejecución 0.4.x intenta retirar el scheduler y
las sesiones que hubiera creado una versión anterior.
