#!/usr/bin/env bash
set -e

ROLE=roles/vless_masked
CLIENT_DIR=/opt/vless_masked/clients

echo "[+] Creating role structure..."
mkdir -p $ROLE/{tasks,templates,files,defaults,handlers}

################################
# defaults/main.yml
################################
cat > $ROLE/defaults/main.yml <<'EOF'
vless_masked_domain: ""
vless_masked_email: ""
vless_masked_singbox_port: 10000
vless_masked_client_dir: "/opt/vless_masked/clients"
vless_masked_clients:
  client1:
    uuid: null
    ws_path: null
    h2_path: null
    grpc_service: null
  client2:
    uuid: null
    ws_path: null
    h2_path: null
    grpc_service: null
  client3:
    uuid: null
    ws_path: null
    h2_path: null
    grpc_service: null
  client4:
    uuid: null
    ws_path: null
    h2_path: null
    grpc_service: null
  client5:
    uuid: null
    ws_path: null
    h2_path: null
    grpc_service: null
EOF

################################
# handlers/main.yml
################################
cat > $ROLE/handlers/main.yml <<'EOF'
---
- name: restart sing-box
  systemd:
    name: sing-box
    state: restarted
    enabled: yes
EOF

################################
# tasks/main.yml
################################
cat > $ROLE/tasks/main.yml <<'EOF'
- name: Include tasks for server setup
  include_tasks: server_setup.yml

- name: Include tasks for client provisioning
  include_tasks: generate_clients.yml
EOF

################################
# tasks/server_setup.yml
################################
cat > $ROLE/tasks/server_setup.yml <<'EOF'
- name: Install packages
  apt:
    name:
      - nginx-extras
      - certbot
      - python3-certbot-nginx
      - curl
    update_cache: yes

- name: Install sing-box
  shell: curl -fsSL https://sing-box.app/deb-install.sh | bash
  args:
    creates: /usr/bin/sing-box

- name: Create fake site dir
  file:
    path: /var/www/fake
    state: directory

- name: Deploy fake site
  copy:
    src: index.html
    dest: /var/www/fake/index.html

- name: Obtain TLS cert
  shell: certbot --nginx -n --agree-tos -m {{ vless_masked_email }} -d {{ vless_masked_domain }}
  args:
    creates: "/etc/letsencrypt/live/{{ vless_masked_domain }}"

- name: Configure nginx
  template:
    src: nginx.conf.j2
    dest: /etc/nginx/sites-enabled/{{ vless_masked_domain }}

- name: Remove default nginx site
  file:
    path: /etc/nginx/sites-enabled/default
    state: absent

- name: Reload nginx
  systemd:
    name: nginx
    state: reloaded
EOF

################################
# tasks/generate_clients.yml
################################
cat > $ROLE/tasks/generate_clients.yml <<'EOF'
- name: Assert required variables
  assert:
    that:
      - vless_masked_domain is string
      - vless_masked_domain | length > 0
      - vless_masked_email is string
      - vless_masked_email | length > 0
    fail_msg: "vless_masked_domain and vless_masked_email must be set"

- name: Ensure client config dir exists
  file:
    path: "{{ vless_masked_client_dir }}"
    state: directory
    mode: "0755"

- name: Generate missing client parameters
  set_fact:
    vless_masked_clients: >-
      {{
        vless_masked_clients | dict2items
        | map('combine',
            {
              'value': (
                item.value | default({})
                | combine({
                    'uuid': (lookup('password','/dev/null length=32 chars=hex') if (item.value.uuid is not defined or item.value.uuid == None) else item.value.uuid),
                    'ws_path': ("/ws-" + lookup('password','/dev/null length=10 chars=hex') if (item.value.ws_path is not defined or item.value.ws_path == None) else item.value.ws_path),
                    'h2_path': ("/h2-" + lookup('password','/dev/null length=10 chars=hex') if (item.value.h2_path is not defined or item.value.h2_path == None) else item.value.h2_path),
                    'grpc_service': ("grpc-" + lookup('password','/dev/null length=10 chars=hex') if (item.value.grpc_service is not defined or item.value.grpc_service == None) else item.value.grpc_service)
                  })
              )
            }) | items2dict
      }}
  loop: "{{ vless_masked_clients | dict2items }}"
  loop_control:
    loop_var: item

- name: Generate client configs for each client
  template:
    src: client.json.j2
    dest: "{{ vless_masked_client_dir }}/{{ item.key }}.json"
    mode: "0644"
  loop: "{{ vless_masked_clients | dict2items }}"
  loop_control:
    loop_var: item
  vars:
    client_uuid: "{{ item.value.uuid }}"
    client_ws_path: "{{ item.value.ws_path }}"
    client_h2_path: "{{ item.value.h2_path }}"
    client_grpc_service: "{{ item.value.grpc_service }}"

- name: Generate sing-box server config with all clients
  template:
    src: singbox_multi_clients.json.j2
    dest: /etc/sing-box/config.json
  notify:
    - restart sing-box
EOF

################################
# templates/client.json.j2
################################
cat > $ROLE/templates/client.json.j2 <<'EOF'
{
  "log": { "level": "info" },
  "inbounds": [
    { "type": "socks", "listen": "127.0.0.1", "listen_port": 1080 }
  ],
  "outbounds": [
    {
      "tag": "ws",
      "type": "vless",
      "server": "{{ vless_masked_domain }}",
      "server_port": 443,
      "uuid": "{{ client_uuid }}",
      "tls": { "enabled": true, "server_name": "{{ vless_masked_domain }}" },
      "transport": { "type": "ws", "path": "{{ client_ws_path }}" }
    },
    {
      "tag": "h2",
      "type": "vless",
      "server": "{{ vless_masked_domain }}",
      "server_port": 443,
      "uuid": "{{ client_uuid }}",
      "tls": { "enabled": true, "server_name": "{{ vless_masked_domain }}" },
      "transport": { "type": "http", "path": "{{ client_h2_path }}" }
    },
    {
      "tag": "grpc",
      "type": "vless",
      "server": "{{ vless_masked_domain }}",
      "server_port": 443,
      "uuid": "{{ client_uuid }}",
      "tls": { "enabled": true, "server_name": "{{ vless_masked_domain }}" },
      "transport": { "type": "grpc", "service_name": "{{ client_grpc_service }}" }
    },
    {
      "type": "urltest",
      "tag": "auto",
      "outbounds": [ "ws", "h2", "grpc" ],
      "url": "https://www.gstatic.com/generate_204",
      "interval": "30s",
      "tolerance": 100
    },
    { "type": "direct", "tag": "direct" }
  ],
  "route": { "final": "auto" }
}
EOF

################################
# templates/singbox_multi_clients.json.j2
################################
cat > $ROLE/templates/singbox_multi_clients.json.j2 <<'EOF'
{
  "log": { "level": "info" },
  "inbounds": [
  {% for item in vless_masked_clients | dict2items %}
    {
      "type": "vless",
      "listen": "0.0.0.0",
      "listen_port": {{ vless_masked_singbox_port }},
      "users": [ { "uuid": "{{ item.value.uuid }}" } ],
      "transport": { "type": "ws", "path": "{{ item.value.ws_path }}" }
    },
    {
      "type": "vless",
      "listen": "0.0.0.0",
      "listen_port": {{ vless_masked_singbox_port | int + 1 }},
      "users": [ { "uuid": "{{ item.value.uuid }}" } ],
      "transport": { "type": "http", "path": "{{ item.value.h2_path }}" }
    },
    {
      "type": "vless",
      "listen": "0.0.0.0",
      "listen_port": {{ vless_masked_singbox_port | int + 2 }},
      "users": [ { "uuid": "{{ item.value.uuid }}" } ],
      "transport": { "type": "grpc", "service_name": "{{ item.value.grpc_service }}" }
    }{% if not loop.last %},{% endif %}
  {% endfor %}
  ],
  "outbounds": [ { "type": "direct" } ]
}
EOF

################################
# templates/nginx.conf.j2
################################
cat > $ROLE/templates/nginx.conf.j2 <<'EOF'
server {
    listen 443 ssl http2;
    server_name {{ vless_masked_domain }};

    ssl_certificate     /etc/letsencrypt/live/{{ vless_masked_domain }}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{{ vless_masked_domain }}/privkey.pem;

    root /var/www/fake;
    index index.html;

    location / { try_files $uri $uri/ =404; }

    location /ws- { proxy_pass http://127.0.0.1:{{ vless_masked_singbox_port }}; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; proxy_set_header Host $host; }
    location /h2- { proxy_pass http://127.0.0.1:{{ vless_masked_singbox_port | int + 1 }}; proxy_http_version 2; proxy_set_header Host $host; }
    location /grpc- { grpc_pass grpc://127.0.0.1:{{ vless_masked_singbox_port | int + 2 }}; grpc_set_header Host $host; }

    location /api/trace {
        default_type application/json;
        content_by_lua_block {
            local cjson = require "cjson"
            local data = {
                ip = ngx.var.remote_addr,
                port = ngx.var.remote_port,
                scheme = ngx.var.scheme,
                http_version = ngx.req.http_version(),
                tls = ngx.var.https == "on",
                user_agent = ngx.var.http_user_agent,
                server_name = ngx.var.server_name,
                request_time = ngx.var.request_time,
                time = ngx.time()
            }
            ngx.say(cjson.encode(data))
        }
    }
}
EOF

################################
# files/index.html
################################
cat > $ROLE/files/index.html <<'EOF'
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Browser diagnostics</title>
<style>
body { font-family: monospace; background: #0b1020; color: #e5e5e5; padding: 20px; }
h1 { color: #7aa2f7; }
pre { background: #111827; padding: 15px; border-radius: 8px; overflow-x: auto; }
</style>
</head>
<body>
<h1>Browser diagnostics</h1>
<p>This page displays basic information about your browser and environment.</p>
<pre id="out">Loading...</pre>
<script>
function getData() {
  return {
    userAgent: navigator.userAgent,
    language: navigator.language,
    languages: navigator.languages,
    platform: navigator.platform,
    hardwareConcurrency: navigator.hardwareConcurrency,
    deviceMemory: navigator.deviceMemory || null,
    cookieEnabled: navigator.cookieEnabled,
    doNotTrack: navigator.doNotTrack,
    screen: { width: screen.width, height: screen.height, colorDepth: screen.colorDepth, pixelRatio: window.devicePixelRatio },
    viewport: { width: window.innerWidth, height: window.innerHeight },
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    timestamp: new Date().toISOString()
  };
}
document.getElementById("out").textContent = JSON.stringify(getData(), null, 2);
</script>
</body>
</html>
EOF

echo "[+] Role vless_masked with flexible auto-provisioning created."
echo "Client configs will be in $CLIENT_DIR/clientN.json"
