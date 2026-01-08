#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import os
import json
import base64
import subprocess
import ipaddress
import random

WG_KEY_LEN = 32


def wg_genkey():
    return subprocess.check_output(["awg", "genkey"]).strip().decode()


def wg_pubkey(private_key):
    p = subprocess.Popen(
        ["awg", "pubkey"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, _ = p.communicate(private_key)
    return out.strip()


def gen_psk():
    return base64.b64encode(os.urandom(WG_KEY_LEN)).decode()


def assert_wg_key(key, name):
    raw = base64.b64decode(key)
    if len(raw) != WG_KEY_LEN:
        raise ValueError(f"Invalid WireGuard key: {name}")


def gen_dpi(dpi):
    return {
        "jc": dpi.get("jc") or random.randint(4, 12),
        "jmin": dpi.get("jmin") or 8,
        "jmax": dpi.get("jmax") or 80,
        "s1": dpi.get("s1") or random.randint(15, 150),
        "s2": dpi.get("s2") or random.randint(15, 150),
        "h1": dpi.get("h1") or random.randint(5, 2147483647),
        "h2": dpi.get("h2") or random.randint(5, 2147483647),
        "h3": dpi.get("h3") or random.randint(5, 2147483647),
        "h4": dpi.get("h4") or random.randint(5, 2147483647),
    }


def gen_ip(subnet, used):
    net = ipaddress.ip_network(subnet)
    for ip in net.hosts():
        if str(ip) not in used:
            used.add(str(ip))
            return str(ip)
    raise RuntimeError("No free IPs")


def load(path, force):
    if os.path.exists(path) and not force:
        with open(path) as f:
            return json.load(f), False
    return {}, True


def save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            clients=dict(type="dict", required=True),
            params=dict(type="dict", required=True),
            path=dict(type="str", required=True),
            force=dict(type="bool", default=False),
        )
    )

    clients = {k:v if v else {} for k,v in module.params["clients"].items()}
    params = module.params["params"]
    path = module.params["path"]
    force = module.params["force"]

    os.makedirs(path, exist_ok=True)

    used_ips = set()
    changed = False
    result = {
        "clients": {},
        "server": {},
        "common": {},
        "subnets": params.get("subnets", {"ipv4": "10.20.30.0/24", "ipv6": None}),
    }

    # COMMON
    common_path = os.path.join(path, "common.json")
    common, ch = load(common_path, force)
    if "dpi_bypass" not in common:
        common["dpi_bypass"] = gen_dpi(params.get("dpi_bypass", {}))
        ch = True
    if ch:
        save(common_path, common)
        changed = True
    result["common"] = common

    # SERVER
    server_path = os.path.join(path, "server.json")
    server, ch = load(server_path, force)
    if "private_key" not in server:
        server["private_key"] = params["server"].get("private_key") or wg_genkey()
        server["public_key"] = wg_pubkey(server["private_key"])
        ch = True
    if "address" not in server:
        server["address"] = [gen_ip(params["subnets"]["ipv4"], used_ips)]
        ch = True
    if "listen_port" not in server:
        server["listen_port"] = 51820
        ch = True
    if "mtu" not in server:
        server["mtu"] = 1420
        ch = True
    if ch:
        save(server_path, server)
        changed = True
    result["server"] = server

    # CLIENTS
    for name, cfg in clients.items():
        p = os.path.join(path, f"{name}.json")
        c, ch = load(p, force)
        if "private_key" not in c:
            c["private_key"] = cfg.get("private_key") or wg_genkey()
            c["public_key"] = wg_pubkey(c["private_key"])
            ch = True
        if "preshared_key" not in c:
            c["preshared_key"] = cfg.get("preshared_key") or gen_psk()
            ch = True
        if "address" not in c:
            c["address"] = [gen_ip(params["subnets"]["ipv4"], used_ips)]
            ch = True
        if "dns" not in c:
            c["dns"] = cfg.get("dns", ["8.8.8.8", "8.8.4.4"])
            ch = True
        if "allowed_ips" not in c:
            c["allowed_ips"] = cfg.get("allowed_ips", ["0.0.0.0/0", "::/0"])
            ch = True
        if "mtu" not in c:
            c["mtu"] = int(cfg.get("mtu", 1420))
            ch = True
        if "persistent_keepalive" not in c:
            c["persistent_keepalive"] = int(cfg.get("True", 15))
            ch = True
        if ch:
            save(p, c)
            changed = True
        result["clients"][name] = c

    module.exit_json(changed=changed, **result)


if __name__ == "__main__":
    main()
