# Pendientes

No hay pedidos nuevos sin incorporar al backlog.

# Procesadas

`Procesadas` significa incorporadas a BACKLOG.md, no completadas.

- [2026-08-20] Aplicar la politica global de proteccion y privacidad GitHub sin interrumpir el trabajo actual: para cada remoto GitHub de este proyecto, auditar secretos y habilitar/verificar Secret Scanning y Push Protection cuando GitHub lo admita; configurar `user.email` local con el correo `noreply` de la cuenta autenticada sin cambiar `user.name`; evitar en archivos versionados rutas absolutas del perfil de Windows y correos personales, usando rutas relativas, variables o placeholders; no reescribir historial ni crear/reemplazar remotos solo por esta tarea. Registrar y validar el resultado o el bloqueo exacto.
  - Backlog: Q-001. Estado: parcial y bloqueado por configuracion noreply y protecciones remotas no verificadas/autorizadas en este lote.

- [2026-08-20] Adoptar la política global de CI: ejecutar validaciones locales y hacer push cuando corresponda, pero no esperar, mirar, sondear ni monitorear GitHub Actions u otra CI remota después del push salvo que el usuario lo pida explícitamente en la solicitud actual. Registrar esta convención estable en la memoria del proyecto; si el resultado de CI ya está disponible puede informarse, sin gastar tiempo ni tokens esperándolo.
  - Backlog: Q-002. Estado: DONE; convencion registrada en CONTEXT y DECISIONS D-002. No se hizo push ni seguimiento remoto de CI.
