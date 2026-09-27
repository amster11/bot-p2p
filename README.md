# P2P-Hunter-AI

Telegram-бот — сканер P2P и крипто-арбитражных связок между биржами. Бот только анализирует и присылает уведомления: не торгует и денег не держит.

Техзадание: [docs/TZ.md](docs/TZ.md).

## Статус

Этап 1, каркас. Готовы расчёт маршрутов, фильтры и модули бирж (Bybit, MEXC, Bitget).
Ещё не сделаны: планировщик, база, Telegram, ИИ-разбор, подписки.

| Биржа | Стакан | Сети | P2P |
|---|---|---|---|
| Bybit | ✅ публично | ✅ нужен ключ | ✅ неофициальный эндпоинт, проверить на VPS |
| MEXC | ✅ публично | ✅ нужен ключ | ⏳ предстоит разобрать |
| Bitget | ✅ публично | ✅ публично | ⏳ предстоит разобрать |

## Запуск

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                              # вписать ключи (только чтение!)
cp config/config.example.yaml config/config.yaml  # пороги, суммы, комиссии
pytest                                            # тесты расчёта (без сети)
python -m p2phunter.probe                         # проверить доступ к биржам
```

## Устройство

```
src/p2phunter/
  models.py       структуры данных (стакан, P2P-объявление, сеть, маршрут)
  calc.py         расчёт чистой прибыли — только формулы
  filters.py      отсев ненадёжных продавцов и цен не в рынке
  config.py       конфиг (config/config.yaml) и секреты (.env)
  probe.py        диагностика доступа к биржам
  exchanges/
    base.py       единый интерфейс биржи
    bybit.py  mexc.py  bitget.py
```

## Как добавить биржу

1. Создать `src/p2phunter/exchanges/<name>.py` с классом-наследником `ExchangeAdapter`, реализовать `fetch_order_book`, `fetch_networks`, `fetch_p2p_ads`.
2. Зарегистрировать класс в `exchanges/__init__.py` (`ADAPTERS`).
3. Добавить секцию биржи в `config/config.yaml` и ключи в `.env`.
4. Если биржа называет сети по-своему — дописать названия в `network_aliases`.
5. Запустить `python -m p2phunter.probe` и убедиться, что все три блока отвечают.

## Если биржа сломалась

P2P-эндпоинты неофициальные и могут поменяться. Порядок действий: запустить `probe`, открыть P2P-страницу биржи в браузере, в DevTools → Network найти запрос со списком объявлений, сравнить его адрес, параметры и поля ответа с кодом в `exchanges/<name>.py`, поправить.

## Установка на VPS

Скрипт `deploy/install.sh` (запуск от root, можно повторять — он же обновляет код):
создаёт пользователя `p2pbot`, кладёт код в `/opt/p2p-bot`, ставит свой venv, создаёт `.env` с правами 600
и запускает диагностику бирж. Системные пакеты не ставит, nginx, firewall и SSH не трогает, портов не открывает.

Репозиторий приватный, поэтому при первом запуске скрипт создаёт deploy key и просит добавить его
в GitHub (Settings → Deploy keys, только чтение), после чего скрипт запускается ещё раз.

Запуск одной командой из Windows (cmd или PowerShell), из папки, где лежит `install.sh`:

```
cmd /c "ssh -i %USERPROFILE%\.ssh\vps_claude -o IdentitiesOnly=yes root@<IP> bash -s < install.sh"
```

systemd-сервис `p2p-bot` (MemoryMax=400M, CPUQuota=50%, Restart=always, от пользователя p2pbot)
ставится флагом `--service`, когда в коде появится сам бот: `bash /opt/p2p-bot/deploy/install.sh --service`.
