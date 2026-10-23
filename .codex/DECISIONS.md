# Decisiones tecnicas

No borrar decisiones anteriores. Si una decision cambia, agregar una nueva entrada que indique cual reemplaza.

## D-001 - Memoria persistente del proyecto

- Estado: vigente.
- Fecha: 2026-07-10.
- Decision: usar `.codex/` como fuente de verdad entre sesiones, modelos y agentes.
- Motivo: continuidad independiente del historial del chat.

## D-002 - Validacion local y CI sin seguimiento automatico

- Estado: vigente.
- Fecha: 2026-10-23; pedido Q-002 recibido el 2026-08-20.
- Decision: ejecutar las validaciones locales y hacer push cuando corresponda y este autorizado. No esperar, mirar, sondear ni monitorear GitHub Actions u otra CI remota despues del push salvo pedido explicito en la solicitud actual. Un resultado ya disponible puede informarse sin esperarlo.
- Motivo: respetar la politica solicitada sin consumir tiempo esperando CI. Los workflows existentes pueden continuar ejecutandose.

## D-003 - Privacidad y evidencia antes de cambios remotos

- Estado: vigente; aplicacion parcial de Q-001, con bloqueos en BACKLOG.
- Fecha: 2026-10-23; pedido Q-001 recibido el 2026-08-20.
- Decision: usar rutas relativas, variables o placeholders y no incluir correos personales en archivos versionados. Auditar sin exponer valores. Conservar historial, remotos y `user.name`. No inferir que Secret Scanning o Push Protection estan habilitados si la lectura no expone esos campos; no inventar un correo noreply a partir de un identificador de cuenta.
- Motivo: registrar solo hechos verificados. Este lote no autoriza escribir git config ni ajustes GitHub.

## D-004 - Preservacion e integracion GUI-only 0.4.1

- Estado: vigente para el lote local; merge y commit pendientes de confirmacion del coordinador.
- Fecha: 2026-10-23.
- Decision: mantener la intencion del WIP GUI-only 0.4.1, extender pruebas con efectos externos simulados y validar la instalacion en un candidato aislado. No reemplazar la instalacion habitual ni construir/publicar EXE.
- Motivo: los 15 WIP preexistentes incluyen una cola y 14 cambios coherentes de producto; no se atribuyen automaticamente al usuario. La integracion propuesta hacia main tambien incluye 19 commits historicos y requiere decidir ese alcance.

## D-005 - Integracion completa e identidad local autorizadas

- Estado: vigente; reemplaza el hold funcional de D-004 y la prohibicion de configurar exclusivamente user.email local de D-003.
- Fecha: 2026-10-23.
- Decision: integrar los 19 commits historicos y WIP GUI-only 0.4.1 hacia main, con seleccion explicita, commit y fast-forward. El usuario autorizo el noreply exacto en la configuracion local; conservar user.name, identidad global, remotos y demas ajustes.
- Evidencia: autorizacion especifica del usuario transmitida por dot (Sentinel_a09a030c6aac819197b69cdc2e7cc3c6) y confirmacion directa de actualizar cuatro memorias. La escritura documental antes denegada no se ejecuto; solo se presenta un nuevo intento al revisor con esta evidencia.
- Limites: sin purgar sesiones, tareas, configuracion o datos reales; sin promover producto, construir EXE, publicar releases ni operar VPS. Mantener fixes de dependencias y vendor pip intactos. Protecciones GitHub aun no verificadas; no cambiar permisos ni credenciales.
- Cierre autorizado: push normal del resultado aprobado al origin verificado, sin force, tags ni wrapper PushCode; comprobar SHA remoto y una vez el estado CI del commit. La politica D-002 sigue vigente para ejecuciones futuras sin pedido explicito de CI.

## D-006 - Integracion local validada y entrega remota acotada

- Estado: implementada para I-001; D-005 conserva los limites de autorizacion.
- Fecha: 2026-10-23.
- Resultado: commit funcional 527923f353fdf67655abd2667308804ae5c0016e y fast-forward de main desde 33ef90a7bced71df45af4f464187538af7fcddc7. Integra los 19 commits historicos y WIP 0.4.1 completo, sin conflictos ni descarte de archivos. El cierre documental no cambia codigo.
- Validacion posterior: snapshot de 42 archivos identico al commit integrado; 138 pruebas sin skips, cobertura de sentencias 1230/1230 en 19 archivos, 12 regresiones de seguridad/compatibilidad y Ruff aprobados. GUI, migracion y limpieza legacy solo con fixtures/mocks; no datos reales ni app/bot real.
- Identidad: noreply local autorizado, autor y committer comprobados con la identidad canonica de Git. user.name/global no cambiaron; Git normaliza el nombre al crear identidades, por lo que no se compara su valor crudo directamente con el nombre del commit.
- Entrega: main del origin publico verificado. No tags ni releases; push de main solo activa tests. SHA remoto y CI puntual se registran en el recibo externo de cierre. No hacer monitoreo recurrente ni cambiar credenciales/permisos. Secret Scanning/Push Protection siguen sin evidencia suficiente y Q-001 permanece parcial.

## D-007 - Mocks Windows portables sin acceso nativo

- Fecha: 2026-10-23. Estado: implementada localmente y validada; CI remota por recibo.
- Decision: las unidades de notificaciones y acciones GUI eliminan windll mediante fixture reversible y recrean solo dobles con monkeypatch raising=False, tambien en Linux/macOS. Simular sys.platform y DPI explicitamente en la unidad GUI para cubrir el mismo camino en cada host.
- Motivo: reproduccion segura de los cuatro AttributeError observados en CI a85c59d. No se omiten pruebas, no se baja cobertura y no se cambia produccion para satisfacerlas. Gate local 138 passed, cero skips y 100% de 1230 sentencias.
- Adopcion de producto: Git ya cerrado no equivale a instalacion habitual/EXE actualizados. Conservar modo editable de .venv-build y los fixes de seguridad; usuario confirmo exclusividad vigente. La reconstruccion de EXE usada realmente queda sujeta al flujo manual de AGENTS y canal verificado, sin publicaciones automaticas.
