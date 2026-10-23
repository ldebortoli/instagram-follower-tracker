# TODO

No hay pedidos locales de integracion pendientes de clasificar. A-041 y E-041 completadas localmente; Q-001 sigue parcial por protecciones remotas no verificadas.

# IN PROGRESS

No hay operaciones de adopcion activas. A-041 y E-041 completadas; cierre documental local sin publicar por el limite vigente.


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

- [2026-10-23][CI-001] Corregir portabilidad de mocks ctypes.windll en dos archivos de pruebas. Cuatro fallos reproducidos con atributo ausente, luego 138 passed sin skips, cobertura 1230/1230 en 19 archivos y Ruff aprobado; sin cambios de produccion. Fix ea049ebf22dbba294791bb652f8dfc0a11a5c2aa verificado en origin/main; run 39977697405 completed/success en una consulta puntual, sin monitoreo posterior.

- [2026-10-23][E-041] Reconstruir y adoptar GUI standalone 0.4.1 bajo autorizacion expresa posterior, sin wrapper ni publicacion externa. PE AMD64, ZIP/checksum y payload GUI-only verificados; las dos rutas habituales y la nueva carpeta release 0.4.1 pasan version/self-test con HOME sintetico y no crean datos. SHA EXE 510f212c63701843e49d6366686cf6b7d2d838483e30a737d3422749d9daeb65. Dos CLI standalone antiguas trasladadas al rollback, ZIP historico intacto. Baseline/backups/rollback.py y recibos en Seguidores-product041-adoption-20261023. No equivale a completar A-041 ni actualizar servicios remotos.

- [2026-10-23][A-041] Completar instalacion editable habitual 0.4.1 tras corregir el falso positivo del guard bajo autorizacion posterior. Candidato con transaccion completa y rollback exacto de 8505 archivos; habitual adoptado una sola vez con wheel SHA 4ccafe51b8b2a30860c82077e3b9c5adc1ab9acfa4f781069e1ac72cd3369a85, 3 launchers correctos, fuente/metadata 0.4.1 y sin CLI obsoleta. Ambos gates: 138 passed, cero skips, cobertura 1230/1230, 12 regresiones y pip check; guard 66 passed/72 sentencias al 100%. Habitual 8506 archivos, 8494 ajenos identicos, 41 dependencias/EXE/candidatos previos preservados; rollback habitual verificado en modo seco. Evidencia en Seguidores-041-final-20261023. No cuentas/datos reales/VPS/CI/publicaciones. Commit documental local pendiente de publicacion por el coordinador.
