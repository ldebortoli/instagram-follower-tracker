#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Ejecutá este instalador con sudo." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
APP_ROOT=/opt/jo-bot
DATA_ROOT=/var/lib/jo-bot
SERVICE_USER=jo-bot

apt-get update
apt-get install -y python3 python3-venv

if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd --system --home-dir "${DATA_ROOT}" --shell /usr/sbin/nologin "${SERVICE_USER}"
fi

install -d -m 0755 "${APP_ROOT}"
install -d -o "${SERVICE_USER}" -g "${SERVICE_USER}" -m 0700 "${DATA_ROOT}"

if [[ ! -x "${APP_ROOT}/venv/bin/python" ]]; then
  python3 -m venv "${APP_ROOT}/venv"
fi
"${APP_ROOT}/venv/bin/python" -m pip install --upgrade pip
"${APP_ROOT}/venv/bin/python" -m pip install "${ROOT}[bot]"

install -m 0644 \
  "${ROOT}/apps/jo-bot/deploy/jo-bot.service" /etc/systemd/system/jo-bot.service
if [[ ! -f /etc/jo-bot.env ]]; then
  install -o root -g "${SERVICE_USER}" -m 0640 \
    "${ROOT}/apps/jo-bot/deploy/jo-bot.env.example" /etc/jo-bot.env
fi

systemctl daemon-reload
echo "Jo Bot instalado. Editá /etc/jo-bot.env y después ejecutá:"
echo "  sudo systemctl enable --now jo-bot"

if [[ ${1:-} == "--restart" ]]; then
  systemctl restart jo-bot
  echo "Servicio reiniciado."
fi
