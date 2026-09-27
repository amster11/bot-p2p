#!/usr/bin/env bash
# Установка / обновление P2P-Hunter-AI на VPS. Запускать от root; можно повторять.
#
# Что делает: пользователь p2pbot, код в /opt/p2p-bot, свой venv, .env (600),
# прогон диагностики бирж. Системные пакеты НЕ ставит, nginx/firewall/SSH не трогает.
# systemd-сервис ставится только с флагом --service (когда в коде появится бот).
set -euo pipefail

APP=/opt/p2p-bot
USER_NAME=p2pbot
REPO=git@github.com:amster11/bot-p2p.git
BRANCH=${BRANCH:-claude/awesome-bell-8kkzk3}
KEY=$APP/.ssh/deploy_key
WITH_SERVICE=0
[[ "${1:-}" == "--service" ]] && WITH_SERVICE=1

say() { echo -e "\n=== $*"; }
as_bot() { sudo -u "$USER_NAME" -H "$@"; }

[[ $EUID -eq 0 ]] || { echo "Запускать от root"; exit 1; }

say "Проверка окружения"
PY=$(command -v python3.14 || command -v python3 || true)
[[ -n "$PY" ]] || { echo "Нет python3 — нужна установка системного пакета, остановился"; exit 1; }
command -v git >/dev/null || { echo "Нет git — нужна установка системного пакета, остановился"; exit 1; }
command -v sudo >/dev/null || { echo "Нет sudo — нужна установка системного пакета, остановился"; exit 1; }
echo "python: $PY ($($PY --version))"
TMPV=$(mktemp -d)
if ! $PY -m venv "$TMPV/v" >/dev/null 2>&1; then
  rm -rf "$TMPV"
  echo "python3 -m venv не работает: нужен системный пакет python3-venv (или python3.14-venv)."
  echo "Установка системных пакетов — только с согласия владельца сервера. Остановился."
  exit 1
fi
rm -rf "$TMPV"
free -m | awk 'NR==2{print "память: свободно " $7 " МБ"}'
df -h /opt | awk 'NR==2{print "диск /opt: свободно " $4}'

say "Пользователь и папка"
if ! id "$USER_NAME" >/dev/null 2>&1; then
  useradd --system --home-dir "$APP" --shell /usr/sbin/nologin "$USER_NAME"
  echo "создан пользователь $USER_NAME"
fi
mkdir -p "$APP/.ssh"
chown -R "$USER_NAME:$USER_NAME" "$APP"
chmod 700 "$APP/.ssh"

say "Ключ доступа к репозиторию (deploy key, только чтение)"
if [[ ! -f "$KEY" ]]; then
  as_bot ssh-keygen -q -t ed25519 -N "" -C "p2p-bot@$(hostname)" -f "$KEY"
fi
if ! as_bot env GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=$APP/.ssh/known_hosts" \
     git ls-remote "$REPO" >/dev/null 2>&1; then
  echo "GitHub пока не пускает этот ключ. Добавьте его в репозиторий:"
  echo "  GitHub → amster11/bot-p2p → Settings → Deploy keys → Add deploy key"
  echo "  Title: vps-p2p-bot, галочку 'Allow write access' НЕ ставить. Ключ:"
  echo
  cat "$KEY.pub"
  echo
  echo "После этого запустите установку ещё раз."
  exit 2
fi

say "Код (ветка $BRANCH)"
GITSSH="ssh -i $KEY -o IdentitiesOnly=yes -o UserKnownHostsFile=$APP/.ssh/known_hosts"
cd "$APP"
if [[ ! -d .git ]]; then
  as_bot git init -q
  as_bot git remote add origin "$REPO"
fi
as_bot env GIT_SSH_COMMAND="$GITSSH" git fetch -q origin "$BRANCH"
as_bot git checkout -q -B "$BRANCH" "origin/$BRANCH"
as_bot git log --oneline -1

say "venv и зависимости"
[[ -d .venv ]] || as_bot "$PY" -m venv .venv
as_bot .venv/bin/pip install -q --upgrade pip
as_bot .venv/bin/pip install -q -e ".[dev]"
as_bot .venv/bin/python -c "import p2phunter, aiogram, httpx, pydantic; print('зависимости ок')"

say "Конфиг и секреты"
if [[ ! -f .env ]]; then
  install -m 600 -o "$USER_NAME" -g "$USER_NAME" .env.example .env
  echo "создан .env (пустой шаблон) — заполните: nano $APP/.env"
fi
chmod 600 .env; chown "$USER_NAME:$USER_NAME" .env
if [[ ! -f config/config.yaml ]]; then
  as_bot cp config/config.example.yaml config/config.yaml
  echo "создан config/config.yaml из примера"
fi
ls -l .env config/config.yaml

say "Тесты"
as_bot .venv/bin/python -m pytest -q 2>&1 | tail -1 || true

if [[ $WITH_SERVICE -eq 1 ]]; then
  say "systemd-сервис p2p-bot"
  install -m 644 deploy/p2p-bot.service /etc/systemd/system/p2p-bot.service
  systemctl daemon-reload
  systemctl enable --now p2p-bot
  systemctl --no-pager status p2p-bot | head -5
fi

say "Диагностика бирж (полный вывод: $APP/probe.log)"
as_bot .venv/bin/python -m p2phunter.probe 2>&1 | as_bot tee "$APP/probe.log"
