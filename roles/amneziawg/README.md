# Ansible role: `amneziawg`

Роль предназначена для **развёртывания и управления сервером AmneziaWG** (форк WireGuard с DPI-bypass), включая:

* установку и инициализацию конфигурации;
* генерацию ключей и адресов;
* генерацию конфигов сервера и клиентов;
* опциональный экспорт клиентских конфигов (ZIP + QR);
* запуск сервера через systemd.

Роль следует **Ansible best practices 2024+** и разделяет:

* *источник истины* (JSON-файлы);
* *рендеринг* конфигов (`template`);
* *lifecycle* сервиса (`systemd`).

---

## Требования

### ОС

* Debian 11+ (bullseye, bookworm, trixy)
* Ubuntu 20.04+ (focal, jammy, noble)

### Ansible

* Ansible **2.13+**

### Пакеты на сервере

* `amneziawg`
* `wg` (WireGuard tools)

### Пакеты на localhost (для экспорта, опционально)

* `qrencode`
* `zip`

---

## Структура роли

```
roles/amneziawg/
├── defaults/
│   └── main.yml          # Пользовательские входные переменные
├── vars/
│   └── main.yml          # Внутренние переменные роли
├── tasks/
│   └── main.yml          # Основная логика
├── handlers/
│   └── main.yml          # Restart сервиса
├── templates/
│   ├── amneziawg_server.conf.j2
│   └── amneziawg_client.conf.j2
├── library/
│   └── amneziawg_config.py  # Кастомный Ansible-модуль
└── meta/
    └── main.yml
```

---

## Основная концепция

Роль использует **кастомный Ansible-модуль `amneziawg_config`**, который:

* хранит состояние в `/etc/amnezia/amneziawg/*.json`;
* генерирует недостающие значения (ключи, IP, DPI-параметры);
* не перезаписывает существующие данные без `force=true`;
* возвращает актуальное состояние для последующего рендеринга.

JSON-файлы являются **единственным источником истины**.

---

## Переменные роли

### `amneziawg_clients`

Описание клиентов.

```yaml
amneziawg_clients:
  client-1:
    private_key: null           # string | null → автогенерация
    preshared_key: null         # string | null → автогенерация
    address: null               # list | string | null → автогенерация
    dns:
      - "8.8.8.8"
      - "8.8.4.4"
    mtu: 1420
    persistent_keepalive: 15
    allowed_ips:
      - "0.0.0.0/0"
      - "::/0"
```

---

### `amneziawg_params`

Глобальные параметры сервера и сети.

```yaml
amneziawg_params:
  subnets:
    ipv4: "10.20.30.0/24"
    ipv6: null

  server:
    private_key: null
    address: null
    endpoint: null
    listen_port: 51820
    mtu: 1420

  dpi_bypass:
    jc: null
    jmin: null
    jmax: null
    s1: null
    s2: null
    h1: null
    h2: null
    h3: null
    h4: null
```

> Все параметры, заданные как `null`, будут **сгенерированы автоматически** согласно рекомендациям AmneziaWG.

---

### Экспорт клиентских конфигов (опционально)

```yaml
amneziawg_export_clients: false
amneziawg_export_path: "./amneziawg-clients"
```

* По умолчанию **выключено**
* При включении:

  * конфиги клиентов скачиваются на localhost;
  * генерируются QR-коды;
  * создаётся ZIP-архив.

---

## Что делает роль

1. Проверяет, что ОС Debian-based
2. Генерирует JSON-конфигурацию:

   * `server.json`
   * `common.json`
   * `<client>.json`
3. Рендерит:

   * `/etc/amnezia/amneziawg/server.conf`
   * `/etc/amnezia/amneziawg/<client>.conf`
4. Запускает сервис:

   ```bash
   systemctl enable --now amneziawg@server
   ```
5. (Опционально) экспортирует конфиги клиентов

---

## Пример использования

```yaml
- hosts: vpn
  become: true
  roles:
    - amneziawg
```

---

## Идемпотентность и `force`

* При повторном запуске **ничего не меняется**
* Ключи, IP и DPI-параметры **не регенерируются**
* Для принудительной регенерации:

  ```yaml
  amneziawg_config:
    force: true
  ```

(параметр можно добавить в задачу роли при необходимости)

---

## Безопасность

* Конфиги создаются с правами `0600`
* Приватные ключи не выводятся в stdout
* Экспорт клиентов происходит **только при явном включении**

---

## Ограничения

* Поддерживается **один серверный интерфейс**
* Нет автоматической ротации ключей
* IPv6-адреса генерируются только при заданной подсети

---

## Идеи для дальнейшего развития

* Molecule-тесты
* Ротация ключей
* Поддержка нескольких интерфейсов
* Генерация конфигов для мобильных клиентов
* Ansible Collection

---

## Лицензия

MIT
