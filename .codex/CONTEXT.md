# Seguidores de Instagram - Contexto del proyecto

## Descripcion general

Aplicacion local multiplataforma para comparar exportaciones JSON oficiales de seguidores y seguidos, mantener historial SQLite y ofrecer GUI y Jo Bot.

## Arquitectura y estado verificado (2026-10-23)

- Raiz del proyecto: `.`. Usar rutas relativas o variables; no versionar rutas absolutas del perfil ni correos personales.
- Stack: Python >=3.11; Python local de desarrollo verificado: 3.13.2.
- `packages/core/src/seguidores`: importacion de exportaciones oficiales, modelos, configuracion, SQLite, informes y notificaciones.
- `apps/desktop/src/seguidores_desktop`: GUI Tk. El WIP 0.4.1 dirige `python -m seguidores_desktop` a la GUI, elimina CLI/console_entry y empaqueta solo la GUI.
- `apps/jo-bot/src/jo_bot`: bot independiente; conserva entradas `jo-bot` y `jobot`. No implica que el servicio remoto este actualizado ni que su host este confirmado.
- `apps/desktop/packaging`: packaging de escritorio; PyInstaller y herramientas de plataforma se simulan en las regresiones locales.
- `pyproject.toml`: version, dependencias y entry points; `packages/core/tests`, `apps/desktop/tests`, `apps/jo-bot/tests`: pruebas.
- Rama local: `codex/gui-setup`; origin verificado: `https://github.com/ldebortoli/instagram-follower-tracker.git`; default branch remota: `main`.
- Fuente WIP y candidato aislado: 0.4.1. La instalacion habitual del producto en `.venv-build` sigue en 0.4.0; no se ha promovido 0.4.1 ni reconstruido EXE.
- Seguridad adoptada en `.venv-build`: pip 26.2.2/certifi 2026.10.19 y anyio 4.14.2/urllib3 independiente 2.8.0. Python y los otros paquetes se preservaron. urllib3 vendorizado por pip sigue 2.7.0; queda para una futura actualizacion oficial de pip, sin parche manual ni afirmacion de seguridad total.

## Validacion local y aislamiento

- Lint comprobado: `.venv-build\Scripts\ruff.exe check --no-cache .`.
- Candidato 0.4.1: `%LOCALAPPDATA%\Temp\Seguidores-gui041-20261023\venv`; wheel y recibos en la misma raiz temporal.
- Se instalo el wheel Python con pip offline y `--no-deps`, solo en ese candidato; `pip check` aprobo. No equivale a una compilacion de ejecutables.
- Suite sobre el producto instalado y con efectos externos simulados: 138 passed, 0 skipped en 4.81 s. Incluye GUI real aislada con tres pestanas, perfiles e importacion de uno/dos JSON sinteticos. Una unica raiz Tk por sesion y una ventana Toplevel por prueba evitan recrear interpretes Tk; no se usan cuentas, datos personales ni el mainloop de la app real.
- Cobertura de sentencias: 100% (1230/1230), exigida con `--cov-fail-under=100`; mismos 19 archivos y denominador del baseline, sin omits/pragmas nuevos. La cobertura de ramas no se midio. No equivale a validar binarios o servicios remotos.
- Las unidades asincronas puras de Jo Bot se evaluan sin event loop y rechazan suspensiones inesperadas: `asyncio.run` en este runtime se bloqueo en el socketpair interno de Windows. No se ejecuta el bot real.
- `conftest.py` y el runner aislado bloquean o simulan efectos externos. Las pruebas de popup, Telegram, keyring, tareas y workers usan dobles; nunca abrir cuentas ni relajar permisos para aprobar pruebas. Tests adicionales cubren errores de importacion/configuracion, rollback SQLite, limpieza legacy sintetica y contratos del bot.
- Generacion completa de binarios: solo por pedido expreso y siguiendo AGENTS.md. El script con `-PushCode` tambien prepara un commit y hace push; no usarlo como una comprobacion inocua.

## Convenciones estables

- Leer las cinco memorias en el orden indicado por AGENTS.md y procesar la cola sin duplicar tareas. `Procesadas` significa incorporadas a BACKLOG, no terminadas.
- Preservar WIP ajeno y registrar su procedencia como desconocida cuando no pueda atribuirse.
- Ejecutar validaciones locales y hacer push solo cuando corresponda y este autorizado. Despues de un push, no esperar, consultar, sondear ni monitorear CI remota salvo pedido explicito en la solicitud actual. Se puede informar un resultado ya disponible sin esperarlo.
- Auditar secretos sin mostrar valores; no reescribir historial ni reemplazar remotos por la politica de privacidad. No modificar `user.name`. La identidad noreply exacta y protecciones remotas deben verificarse antes de marcarse como completadas.
- Esta memoria es del proyecto. No actualizar memorias globales por este lote.

## Integracion autorizada en curso (2026-10-23)

- El usuario acepto integrar todo el conjunto de 19 commits historicos y WIP GUI-only 0.4.1 hacia main. Tambien autorizo actualizar estas cuatro memorias y configurar el noreply exacto unicamente en este repositorio. La configuracion local se verifico; identidad global, user.name y demas ajustes permanecen iguales.
- main/origin/main: 33ef90a7bced71df45af4f464187538af7fcddc7. Rama codex/gui-setup/HEAD: 2b5f77ccacba7cf1052cb2b13ee37c65d893b7d2; main es ancestro, 0/19. Falta comprometer la seleccion explicita y avanzar main por fast-forward al nuevo tip, no solo al tip 0.4.0.
- Backups y recibos: `%LOCALAPPDATA%\Temp\Seguidores-integration-main-20261023`; 62 archivos y tres ausencias, indice, parches y bundle completo verificado. Seleccion explicita de 31 entradas, sin git add --all.
- Candidato nuevo separado: Python 3.13.2, producto instalado 0.4.1 y 41 dependencias habituales conservadas. Wheel SHA-256 1800c273a9a7e1168f0a0c1ddac404ec6b12f5f33edb0edb125c0f4526c940c2. Payload, tres launchers y pip check aprobados; 138 pruebas sin skips, 1230/1230 sentencias en 19 archivos y 12 regresiones de seguridad/compatibilidad. Es el arbol propuesto, aun sin merge.
- La instalacion habitual sigue con metadata de producto 0.4.0 y los EXE existentes no se actualizaron. GUI, migraciones y limpieza legacy solo se prueban con fixtures; no operar cuentas, bot real, tareas/sesiones/datos personales ni VPS.
- Al cerrar, subir al origin verificado los cambios aprobados y comprobar el SHA remoto. La comprobacion puntual de CI de este cierre fue solicitada expresamente; no implica monitoreo posterior recurrente. No crear tags, releases ni deploys.
