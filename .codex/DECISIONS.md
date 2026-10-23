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
