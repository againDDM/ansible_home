local ok, cjson = pcall(require, "cjson")
if not ok then
    ngx.status = 500
    ngx.say('{"error":"cjson module not found"}')
    return
end

local info = {}

-- === IP и соединение ===
info.ip = {
    remote_addr = ngx.var.remote_addr,
    remote_port = tonumber(ngx.var.remote_port),
    local_addr  = ngx.var.server_addr,
    local_port  = tonumber(ngx.var.server_port),
}

-- BINARY -> HEX
local bin_addr = ngx.var.binary_remote_addr
if bin_addr then
    info.ip.binary_remote_addr_hex = (bin_addr:gsub('.', function(c)
        return string.format('%02X', string.byte(c))
    end))
end

info.connection = {
    id = tonumber(ngx.var.connection),
    requests = tonumber(ngx.var.connection_requests)
}

-- === HTTP ===
info.http = {
    method = ngx.req.get_method(),
    uri = ngx.var.request_uri,
    args = ngx.req.get_uri_args(),
    headers = ngx.req.get_headers()
}

-- POST данные
if ngx.var.request_method == "POST" then
    ngx.req.read_body()
    local post_args, err = ngx.req.get_post_args()
    if not err then
        info.http.post_args = post_args
    end
end

-- === TLS info ===
info.tls = {
    protocol = ngx.var.ssl_protocol or "",
    cipher   = ngx.var.ssl_cipher or "",
    alpn     = ngx.var.ssl_alpn_protocol or "",
    sni      = ngx.var.ssl_server_name or "",
    client_dn = ngx.var.ssl_client_s_dn or "",
    client_verify = ngx.var.ssl_client_verify or "",
    ocsp = ngx.var.ssl_ocsp_response or ""
}

-- Преобразуем строку шифров в массив
local ssl_ciphers_str = ngx.var.ssl_ciphers or ""
info.tls.ciphers = {}
if ssl_ciphers_str ~= "" then
    -- Разделяем строку по двоеточиям
    for cipher in ssl_ciphers_str:gmatch("[^:]+") do
        -- Убираем возможные пробелы в начале и конце
        local trimmed_cipher = cipher:match("^%s*(.-)%s*$")
        if trimmed_cipher ~= "" then
            table.insert(info.tls.ciphers, trimmed_cipher)
        end
    end
end

-- === TCP info ===
info.tcp = {
    tcp_nodelay = ngx.var.tcp_nodelay or "",
    ssl_handshake_time = ngx.var.ssl_handshake_time or ""
}

-- === User-agent отдельно ===
info.user_agent = ngx.var.http_user_agent or ""

-- === Отдаём JSON ===
ngx.header.content_type = "application/json; charset=utf-8"
local ok, json = pcall(cjson.encode, info)
if ok then
    ngx.say(json)
else
    ngx.say('{"error":"failed to encode JSON"}')
end
