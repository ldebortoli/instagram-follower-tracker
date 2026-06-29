# Núcleo compartido

`src/seguidores` contiene la lógica reutilizada por las aplicaciones de escritorio y Jo Bot:

- autenticación y recopilación desde Instagram;
- cooldown de requests;
- configuración y rutas de datos;
- comparación, historial SQLite y reportes;
- notificaciones de resultados.

No contiene GUI, comandos de Telegram, schedulers del sistema ni código de empaquetado.
