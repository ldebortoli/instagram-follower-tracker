# Instrucciones de trabajo del repositorio

- Después de cambios que ameriten un nuevo ejecutable, no ejecutes automáticamente PyInstaller ni
  `apps/desktop/packaging/build.py` desde Codex, salvo que el usuario lo pida expresamente.
- Entregá al usuario este comando para su terminal PowerShell y esperá su resultado:

  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build-windows.ps1" -Extract -PushCode`

- El script ejecuta lint, tests, build, smoke tests, checksum y extracción sin consumir tokens de
  Codex. Con `-PushCode`, después de validar todo también crea el commit pendiente y sube la rama
  actual a `origin`.
- Codex sí puede ejecutar comprobaciones rápidas y focalizadas durante el desarrollo. La generación
  completa de binarios queda a cargo del usuario.
- Si el script falla, pedir `%TEMP%\Seguidores-build\PROMPT-build-latest.txt` y
  `%TEMP%\Seguidores-build\build-latest.log`; contienen el error completo y los parámetros de la
  ejecución. Una ejecución nueva reemplaza los dos archivos.
