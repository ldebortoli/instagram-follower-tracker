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
- Rama local: `main`; origin verificado: `https://github.com/ldebortoli/instagram-follower-tracker.git`; default branch remota: `main`.
- Fuente integrada y candidato editable: 0.4.1. GUI habitual congelada en dist/release: 0.4.1, reconstruida y adoptada localmente bajo autorizacion expresa posterior. `.venv-build` conserva metadata 0.4.0 y fuente editable 0.4.1: el intento de adopcion fue bloqueado por el guard local y revertido byte por byte; ver A-041 y cierre actual.
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

## Integracion local completada (2026-10-23)

- El usuario acepto integrar todo el conjunto de 19 commits historicos y WIP GUI-only 0.4.1 hacia main. Tambien autorizo actualizar estas cuatro memorias y configurar el noreply exacto unicamente en este repositorio. La configuracion local se verifico; identidad global, user.name y demas ajustes permanecen iguales.
- Commit funcional 527923f353fdf67655abd2667308804ae5c0016e: incorpora la seleccion de 31 rutas GUI-only 0.4.1, docs y regresiones. main avanzo por fast-forward desde 33ef90a7bced71df45af4f464187538af7fcddc7, incluyendo los 19 commits historicos mas ese commit. El checkout original quedo en main; un checkout temporal limpio permitio conservar sus bytes y ya fue retirado. El cierre restante modifica solo estas cuatro memorias; tips finales y SHA remoto en el recibo de entrega.
- Backups y recibos: `%LOCALAPPDATA%\Temp\Seguidores-integration-main-20261023`; 62 archivos y tres ausencias, indice, parches y bundle completo verificado. Seleccion explicita de 31 entradas, sin git add --all.
- Candidato nuevo separado: Python 3.13.2, producto instalado 0.4.1 y 41 dependencias habituales conservadas. Wheel SHA-256 1800c273a9a7e1168f0a0c1ddac404ec6b12f5f33edb0edb125c0f4526c940c2. Payload, tres launchers y pip check aprobados; 138 pruebas sin skips, 1230/1230 sentencias en 19 archivos y 12 regresiones de seguridad/compatibilidad. Los 42 archivos del snapshot coinciden con el commit integrado; la suite posterior al merge tambien aprobo 138 pruebas sin skips, 1230/1230 sentencias y otras 12 de seguridad.
- La instalacion habitual sigue con metadata de producto 0.4.0 y los EXE existentes no se actualizaron. GUI, migraciones y limpieza legacy solo se prueban con fixtures; no operar cuentas, bot real, tareas/sesiones/datos personales ni VPS.
- Al cerrar, subir al origin verificado los cambios aprobados y comprobar el SHA remoto. La comprobacion puntual de CI de este cierre fue solicitada expresamente; no implica monitoreo posterior recurrente. No crear tags, releases ni deploys.

- Convencion de cierre solicitada por el usuario: comprobar que los cambios aprobados se suban al repositorio correspondiente, verificando destino, audiencia y SHA remoto sin force. Un bloqueo de acceso o publicacion fuera de alcance debe informarse; no cambiar permisos/credenciales para resolverlo. Mantener la politica de CI sin monitoreo salvo pedido expreso.

## Portabilidad CI y rutas de uso (2026-10-23)

- La CI del cierre a85c59d fallo en cuatro casos Ubuntu/macOS: el mock suponia que ctypes.windll existia. Windows aprobo. Se reprodujeron localmente los cuatro fallos eliminando el atributo solo en el proceso de prueba; se corrigieron los dos mocks con raising=False y se dejo esa ausencia como fixture permanente. La ruta DPI de GUI tambien usa plataforma y funcion falsas explicitas. Produccion intacta; 138 passed sin skips y cobertura 1230/1230, mismos 19 archivos sin exclusiones, Ruff aprobado.
- Evidencia del arreglo: `%LOCALAPPDATA%\Temp\Seguidores-ci-portability-20261023`. Se usa un runtime candidato anterior solo en lectura, con escrituras confinadas a esta carpeta. El resultado CI remoto nuevo se consulta una vez y se registra en su recibo de entrega, sin monitoreo recurrente.
- Ruta habitual de desarrollo/build: `.venv-build`, Python 3.13.2, producto editable con tres rutas src. Metadata aun 0.4.0, fuente enlazada 0.4.1; conserva launcher seguidores.exe hacia cli.py ya eliminado. Se autoriza adopcion local 0.4.1 manteniendo modo editable y dependencias corregidas; falta preparar/validar candidato y rollback antes de modificarlo.
- Uso real confirmado por el usuario: seguidores-gui.exe de release o dist. Ambos standalone contienen core 0.4.0, verificado mediante lectura del archivo PyInstaller y constantes de bytecode, sin ejecutarlos. Actualizar Git o .venv-build no actualiza esos EXE; corresponde reconstruir para entregar 0.4.1, con ejecucion manual conforme AGENTS y sin inventar canal/publicacion.
- Exclusividad actual confirmada directamente: app y bot cerrados y permanecen asi hasta terminar la actualizacion. No consultar procesos por CIM ni alternativas, no cerrarlos desde Codex y no ejecutar migraciones con datos reales.

## Entrega local GUI 0.4.1 y bloqueo Python (2026-10-23)

- CI del fix portable ea049ebf22dbba294791bb652f8dfc0a11a5c2aa aprobada: run [39977697405](https://github.com/ldebortoli/instagram-follower-tracker/actions/runs/39977697405), completed/success en una lectura puntual. No monitoreo recurrente.
- Usuario confirmo app y bot cerrados durante la actualizacion y uso habitual de seguidores-gui.exe desde release/dist. Autorizacion expresa posterior permite este build/adopcion local, sin wrapper ni publicacion externa; supera el hold manual anterior solo para este lote.
- Candidato editable separado: producto 0.4.1, 41 dependencias habituales conservadas sin otras instalaciones en su site-packages; 138 passed, cero skips, 1230/1230 sentencias en 19 archivos, 12 regresiones de seguridad y pip check aprobados. Herramientas de backend solo temporales, wheels oficiales con hashes verificados.
- PyInstaller 6.21.0 existente genero la GUI en una copia temporal de fuente ea049eb. PE AMD64, version 0.4.1 y self-test de SQLite en memoria/Tcl/keyring nulo aprobados. El entorno minimo omitio la variable de arquitectura al nombrar el ZIP; se corrigio solo el empaquetado usando la maquina AMD64 del PE, sin repetir compilacion ni cambiar produccion.
- GUI adoptada en `dist/standalone/seguidores-gui.exe`, `release/test-current/Seguidores-0.4.0-Windows-x86_64/seguidores-gui.exe` (ruta compatible conservada, contiene 0.4.1) y `release/test-current/Seguidores-0.4.1-Windows-x86_64/seguidores-gui.exe`. Las tres copias coinciden por SHA-256 510f212c63701843e49d6366686cf6b7d2d838483e30a737d3422749d9daeb65 y pasan --version/self-test con HOME sintetico, sin inicializar datos.
- ZIP local nuevo: `release/Seguidores-0.4.1-Windows-x86_64.zip`, SHA-256 4c8811807ef807ce8b966c91c9fb89bf1983a2e2f431bdd8e20eb88634177d2d; checksum verificado. Solo GUI, LEEME y LICENSE. Las dos CLI standalone 0.4.0 se trasladaron al rollback verificado; no son datos/sesiones. ZIP 0.4.0 historico preservado intacto.
- Archivo congelado inspeccionado: no contiene CLI, bot, pip, certifi, anyio, urllib3, httpx ni instaloader; no incorpora bundles cacert. Los fixes del entorno Python se conservan, sin atribuirlos a dependencias ausentes del EXE ni afirmar seguridad total.
- A-041 BLOCKED: native pip offline construyo el editable 0.4.1 pero el guard efimero local rechazo una operacion sobre el directorio padre site-packages, fuera de su allowlist de archivos de producto. No fue denegacion de auto-review. Se detuvo el instalador y no se reintento por otra ruta ni se relajaron controles. La lectura posterior de ensure_dir confirma un intento makedirs sobre directorio existente; no se adopto una excepcion automaticamente.
- Antes de restaurar se probo que el unico delta eran los 13 archivos propios retirados. Se devolvieron mediante renombres exactos y se verificaron los 8507 hashes del entorno contra el baseline. Metadata habitual vuelve a 0.4.0, fuente editable sigue 0.4.1 y launcher CLI antiguo vuelve al estado previo; no declarar adopcion Python completa. Los 41 paquetes, fixes de seguridad y Python global se preservan; pip check vuelve a aprobar. Vendor urllib3 de pip continua 2.7.0 para actualizacion oficial futura.
- Backups, candidato, build, pruebas, logs y rollback: `%LOCALAPPDATA%\Temp\Seguidores-product041-adoption-20261023`. `rollback.py` es dry-run por defecto, restaura solo binarios con --apply tras verificar que no hubo deriva; el entorno Python ya esta restaurado. No se ejecutaron datos/migraciones reales, sesiones, cuentas, scheduler, notificaciones ni VPS. La limpieza legacy que conserva el producto solo se ejercito con fixtures, no con datos del usuario.
