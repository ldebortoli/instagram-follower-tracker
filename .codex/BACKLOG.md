# TODO

No hay pedidos de integracion pendientes de clasificar; I-001 esta en IN PROGRESS.

# IN PROGRESS

- [P1][I-001][2026-10-23] Integrar a main los 19 commits historicos y WIP GUI-only 0.4.1. Alcance e identidad noreply local aprobados; configuracion local verificada sin cambiar nombre/global. Backups y seleccion explicita de 31 entradas en `%LOCALAPPDATA%\Temp\Seguidores-integration-main-20261023`. Candidato aprobado: 138 pruebas sin skips, cobertura 1230/1230 y 12 regresiones de seguridad; pip check correcto. Pendiente commit seleccionado, fast-forward, regresiones sobre resultado integrado y push seguro con comprobacion SHA remoto/CI puntual. No git add --all, tags, releases, EXE ni datos reales.

# BLOCKED

- [P1][Q-001][2026-08-20] Proteccion y privacidad GitHub: avance local parcial, protecciones remotas pendientes. Auditoria estatica acotada anterior de 56 archivos y 214 blobs de hasta 2 MB sin patrones detectados; no prueba ausencia de secretos arbitrarios/ofuscados. Cuenta verificada por lectura autorizada: ldebortoli, ID 18238415. El usuario suministro y autorizo expresamente el noreply exacto; user.email local ya se verifico, con user.name/global sin cambios. Restan Secret Scanning/Push Protection: metadata autorizada no expone su estado y este lote no autoriza modificar ajustes. No inventar estado, reescribir historial, cambiar remotos ni marcar Q-001 DONE. USER_QUEUE conserva su nota historica de procesamiento; este backlog describe el estado actual.

# DONE

- [2026-07-10] Inicializar la memoria persistente del proyecto.
- [2026-10-23][M-001] Validar CONTEXT con arquitectura, rutas relativas, comandos comprobados, estados de entornos y limites reales.
- [2026-10-23][Q-002][2026-08-20] Incorporar la politica de CI sin seguimiento remoto automatico a CONTEXT y DECISIONS D-002. No se consulto ni espero CI remota ni se hizo push en este lote.
- [2026-10-23][T-041] Extender regresiones GUI-only: versiones/metadata 0.4.1, entrada GUI, ausencia de CLI/launcher viejo, packaging y humo con mocks, migracion GUI, texto de notificaciones e aislamiento de red/keyring/procesos/tareas/notificaciones. Validacion del producto instalado en candidato: 138 passed, 0 skipped; cobertura de sentencias 100% y Ruff aprobado. Esto no completa I-001 ni V-001.
- [2026-10-23][C-041] Instalar el wheel Python 0.4.1 solo en candidato temporal aislado con herramientas de build de fuentes oficiales y hashes verificados; pip check aprobo. No se altero la instalacion habitual del producto ni se construyeron EXE de distribucion.
- [2026-10-23][V-001] Cerrar cobertura de sentencias 100% (1230/1230, 19 archivos, --cov-fail-under=100) y comprobacion grafica aislada. Suite 138 passed, cero skips; GUI con raiz Tk unica/Toplevel por prueba. No se excluyo codigo ni se modifico produccion para aprobar. Recibos coverage-gate-final-result.json y coverage-completion/coverage-final.json en la raiz temporal.
