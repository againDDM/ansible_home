# Ansible Role: proxy_masked

Ansible-роль для развертывания высокопроизводительного, защищенного и замаскированного прокси-сервера на базе **Nginx** и **Sing-box**.

Роль реализует мультиплексирование трафика на 443 порту по SNI, поддерживает протоколы VLESS (WebSocket) и NaïveProxy, разворачивает сайт-заглушку для маскировки, а также позволяет маршрутизировать часть трафика клиентов через сеть **Cloudflare WARP**.

## 🛠 Архитектура решения

1. **Фронтенд (Nginx Stream):** Принимает весь входящий трафик на порту `443`. С помощью модуля `ssl_preread` анализирует SNI (имя домена) до терминации TLS и распределяет запросы:
* Домен NaïveProxy $\rightarrow$ отправляется напрямую в Sing-box на порт Naïve.
* Домен TrustTunnel $\rightarrow$ отправляется на порт TrustTunnel.
* Домен VLESS $\rightarrow$ отправляется на локальный HTTPS-сервер Nginx.


2. **Терминатор TLS и Маскировка (Nginx HTTP):** Принимает трафик для VLESS-домена, терминирует TLS (сертификаты Let's Encrypt) и выполняет роль прокси:
* Корень `/` $\rightarrow$ проксирует на сайт-заглушку (`proxy_masked_screen_site`) для прохождения проверок цензорами.
* Путь `ws_path` $\rightarrow$ проксирует WebSocket-соединение VLESS в Sing-box (выход в интернет напрямую).
* Путь `ws_warp_path` $\rightarrow$ проксирует WebSocket-соединение VLESS в Sing-box (выход в интернет через WARP).


3. **Бэкенд (Sing-box):** Обрабатывает прокси-протоколы и маршрутизирует трафик наружу:
* Трафик с inbound-интерфейса `vless-warp` заворачивается в endpoint `wireguard` (Cloudflare WARP через утилиту `wgcf`).
* Остальной трафик уходит напрямую в сеть (`direct`).

---

## ⚙️ Основные переменные (`defaults/main.yml`)

Перед запуском роли необходимо обязательно определить следующие переменные (например, в `host_vars` или `group_vars`):

| Переменная | Описание | Пример |
| --- | --- | --- |
| `proxy_masked_vless_domain` | Основной домен для VLESS (обязательный) | `"vless.yourdomain.com"` |
| `proxy_masked_naive_domain` | Домен для NaïveProxy (опционально) | `"naive.yourdomain.com"` |
| `proxy_masked_trust_domain` | Домен для TrustTunnel (опционально) | `"trust.yourdomain.com"` |
| `proxy_masked_email` | Email для регистрации SSL в Let's Encrypt | `"admin@yourdomain.com"` |
| `proxy_masked_singbox_vless_ws_path` | Секретный путь для VLESS (напрямую) | `"/api/v3/stream/direct-ws"` |
| `proxy_masked_singbox_vless_ws_warp_path` | Секретный путь для VLESS (через WARP) | `"/api/v3/stream/warp-ws"` |
| `proxy_masked_screen_site` | Сайт, который увидят посторонние на корневом `/` | `"[http://127.0.0.1:9001](http://127.0.0.1:9001)"` (или внешний URL) |
| `proxy_masked_clients` | Словарь пользователей (UUID/пароли генерируются сами) | `{ "user1": {}, "user2": {} }` |

---

## 🚀 Использование (Пример Playbook)

1. Определите ваши переменные в файле `group_vars/all.yml`:

```yaml
# Домены бесплатно можно зарегистрировать на duckdns.org, но лучше купить по-нормальному.
proxy_masked_vless_domain: "cdn.mycoolproxy.xyz" # по этому домену будет идти трафик на vless
proxy_masked_naive_domain: "web.mycoolproxy.xyz" # по этому домену будет идти трафик на naive (ещё не работает)
proxy_masked_trust_domain: "www.mycoolproxy.xyz" # по этому домену будет идти трафик на trust tunnel (ещё не работает)
proxy_masked_email: "my-email@gmail.com" # email для lets encrypt

# Пути должны быть длиннее 10 символов и начинаться с /
proxy_masked_singbox_vless_ws_path: "/shm/stream/secure/direct"
proxy_masked_singbox_vless_ws_warp_path: "/shm/stream/secure/warp"

proxy_masked_screen_site: "https://html5up.net" # Любой сайт для маскировки
# Лучше развернуть что-то локальное, например minio/seafile/nextcloud/jenkins/gitea/...
# В идеале здесь должен быть сайт, которым пользуются люди.

# Список клиентов. Каждый будет допущен на сервер и ему будет сгенерирован конфиг.
proxy_masked_clients:
  alex_phone:
    uuid: null      # Будет сгенерирован автоматически, но можно и задать
    password: null  # Будет сгенерирован автоматически, но можно и задать
  home_router:
    uuid: 979696db-512f-11f1-8a1d-525400a5372a  # Будет взятo именно это значение
    password: VPm92CS+qYeNd+1nYNhDDgucZMA=      # Будет взятo именно это значение
...
```

2. Создайте файл плейбука `deploy_proxy.yml`:

```yaml
---
- name: Deploy Anti-Censorship Proxy Infrastructure
  hosts: proxy_servers
  become: yes
  roles:
    - proxy_masked

```

3. Запустите деплой:

```bash
ansible-playbook -i inventory.yaml deploy_proxy.yml

```

## 📋 Результаты работы роли

После успешного выполнения плейбука:

1. На целевом сервере в директории `/opt/proxy_masked/state/masked_clients.json` сохранится сгенерированное состояние пользователей.
2. В директории `/opt/proxy_masked/clients/` для каждого клиента сгенерируется готовый JSON-конфиг (например, `alex_phone.json`), который можно сразу импортировать в десктопный или мобильный клиент **Sing-box**. У каждого клиента в конфиге будет два inbound-профиля: для обычного интернета и для работы через WARP.

---

## ✨ Особенности роли

* **Единый порт 443:** Полное сокрытие прокси-сервисов за легитимными веб-сайтами.
* **Идемпотентность и постоянное состояние:** Кастомный модуль `masked_clients_state` автоматически генерирует UUID и пароли для клиентов при первом запуске и сохраняет их в JSON-файл состояния. При повторных запусках учетные данные не сбрасываются.
* **Автоматический WARP:** Кастомный модуль `warp_config_parse` на лету регистрирует аккаунт Cloudflare WARP, генерирует WireGuard-конфиг и парсит его параметры для бесшовной интеграции в конфигурацию Sing-box.
* **Автоматический SSL:** Самостоятельный выпуск и обновление сертификатов Let's Encrypt через Certbot (Webroot-метод).

---

## 📂 Структура роли

```text
proxy_masked/
├── defaults/
│   └── main.yml                  # Переменные по умолчанию (порты, пути, версии)
├── files/
│   ├── default.conf              # Базовый HTTP-конфиг Nginx (порт 80)
│   ├── mime.types                # Стандартные типы файлов для Nginx
│   └── modules.conf              # Подключение Stream-модулей Nginx
├── handlers/
│   └── main.yml                  # Хэндлеры перезапуска служб (Nginx, Sing-box)
├── library/
│   ├── masked_clients_state.py   # Модуль управления пользователями и UUID
│   └── warp_config_parse.py      # Модуль парсинга WireGuard-конфигурации WARP
├── tasks/
│   ├── main.yml                  # Главный диспетчер задач
│   ├── warp.yml                  # Установка и настройка Cloudflare WARP/WGCF
│   ├── server_setup.yml          # Установка пакетов, Nginx и выпуск SSL
│   └── generate_clients.yml      # Генерация клиентских и серверных конфигов
├── templates/
│   ├── client.json.j2            # Шаблон клиентского конфига для Sing-box
│   ├── nginx-stream.conf.j2      # Шаблон SNI-мультиплексора Nginx
│   ├── nginx-vless.conf.j2       # Шаблон HTTPS-хоста Nginx с WebSocket-путями
│   └── singbox_multi_clients.json.j2 # Шаблон главного конфига Sing-box
└── vars/
    └── main.yml                  # Внутренние константы путей WGCF

```
