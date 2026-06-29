# Instrucciones de trabajo del repositorio

- Después de cambios que ameriten un nuevo ejecutable, no ejecutes automáticamente PyInstaller ni
  `packaging/build.py` desde Codex, salvo que el usuario lo pida expresamente.
- Entregá al usuario este comando para su terminal PowerShell y esperá su resultado:

  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\build-windows.ps1" -Extract`

- El script ejecuta lint, tests, build, smoke tests, checksum y extracción sin consumir tokens de
  Codex.
- Codex sí puede ejecutar comprobaciones rápidas y focalizadas durante el desarrollo. La generación
  completa de binarios queda a cargo del usuario.
