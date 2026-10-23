# TODO

No hay pedidos locales de integracion pendientes de clasificar.

# IN PROGRESS

- [P1][A-041][2026-10-23] Completar adopcion habitual local 0.4.1 manteniendo la instalacion editable de .venv-build. Usuario confirmo app/bot cerrados durante la actualizacion. Lectura: metadata 0.4.0, fuente editable 0.4.1 y launcher CLI obsoleto. Preparar candidato separado, backup/rollback de producto y launchers; instalar offline solo producto y conservar los 41 paquetes restantes. Sin datos/cuentas/migraciones reales ni inspeccion de procesos.
- [P1][E-041][2026-10-23] Entregar GUI 0.4.1 al uso real por EXE de release/dist. Artefactos actuales contienen 0.4.0 y siguen intactos. Corresponde nuevo build, pero Codex no ejecuta PyInstaller ni wrapper automaticamente; preparar comando manual de AGENTS despues de validar CI/adopcion. No publicar binarios sin destino verificado/autorizado.

# BLOCKED

- [P1][Q-001][2026-08-20] Proteccion y privacidad GitHub: avance local parcial, protecciones remotas pendientes. Auditoria estatica acotada anterior de 56 archivos y 214 blobs de hasta 2 MB sin patrones detectados; no prueba ausencia de secretos arbitrarios/ofuscados. Cuenta verificada por lectura autorizada: ldebortoli, ID 18238415. El usuario suministro y autorizo expresamente el noreply exacto; user.email local ya se verifico, con user.name/global sin cambios. Restan Secret Scanning/Push Protection: metadata autorizada no expone su estado y este lote no autoriza modificar ajustes. No inventar estado, reescribir historial, cambiar remotos ni marcar Q-001 DONE. USER_QUEUE conserva su nota historica de procesamiento; este backlog describe el estado actual.

# DONE

- [2026-07-10] Inicializar la memoria persistente del proyecto.
- [2026-10-23][M-001] Validar CONTEXT con arquitectura, rutas relativas, comandos comprobados, estados de entornos y limites reales.
- [2026-10-23][Q-002][2026-08-20] Incorporar la politica de CI sin seguimiento remoto automatico a CONTEXT y DECISIONS D-002. No se consulto ni espero CI remota ni se hizo push en este lote.
- [2026-10-23][T-041] Extender regresiones GUI-only: versiones/metadata 0.4.1, entrada GUI, ausencia de CLI/launcher viejo, packaging y humo con mocks, migracion GUI, texto de notificaciones e aislamiento de red/keyring/procesos/tareas/notificaciones. Validacion del producto instalado en candidato: 138 passed, 0 skipped; cobertura de sentencias 100% y Ruff aprobado. Esto no completa I-001 ni V-001.
- [2026-10-23][C-041] Instalar el wheel Python 0.4.1 solo en candidato temporal aislado con herramientas de build de fuentes oficiales y hashes verificados; pip check aprobo. No se altero la instalacion habitual del producto ni se construyeron EXE de distribucion.
- [2026-10-23][V-001] Cerrar cobertura de sentencias 100% (1230/1230, 19 archivos, --cov-fail-under=100) y comprobacion grafica aislada. Suite 138 passed, cero skips; GUI con raiz Tk unica/Toplevel por prueba. No se excluyo codigo ni se modifico produccion para aprobar. Recibos coverage-gate-final-result.json y coverage-completion/coverage-final.json en la raiz temporal.

- [2026-10-23][I-001] Integracion local completa a main de los 19 commits historicos y WIP GUI-only 0.4.1. Commit funcional 527923f353fdf67655abd2667308804ae5c0016e, fast-forward desde 33ef90a y checkout original en main; seleccion explicita de 31 rutas, tres eliminaciones preservadas y sin add --all. Gate posterior: 138 passed sin skips, 1230/1230 sentencias en 19 archivos, 12 regresiones de seguridad y Ruff aprobados. Identidad noreply solo local, nombre/global preservados. Entrega remota autorizada a main del origin verificado; SHA remoto y CI puntual constan en el recibo externo de cierre. Q-001 conserva su bloqueo remoto; no EXE, promociones ni datos reales.

- [2026-10-23][CI-001] Corregir portabilidad de mocks ctypes.windll en dos archivos de pruebas. Cuatro fallos reproducidos con atributo ausente, luego 138 passed sin skips, cobertura 1230/1230 en 19 archivos y Ruff aprobado; sin cambios de produccion. Commit/push y comprobacion CI puntual se documentan en el recibo externo del lote.
