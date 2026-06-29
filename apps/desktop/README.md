# Aplicaciones de escritorio

Esta carpeta contiene exclusivamente las interfaces instalables de Seguidores:

- `src/seguidores_desktop`: CLI, GUI y schedulers de Windows, macOS y Linux.
- `packaging`: entradas y armado de ejecutables con PyInstaller.
- `scripts`: automatización del build de Windows.
- `tests`: pruebas específicas de la aplicación de escritorio.

La lógica de Instagram y persistencia vive en `packages/core`. Jo Bot no se importa desde esta
aplicación.

Desde la raíz del repositorio:

```powershell
seguidores setup
seguidores-gui
```

El wrapper estable para construir Windows sigue siendo:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build-windows.ps1" -Extract -PushCode
```
