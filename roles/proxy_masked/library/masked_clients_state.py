#!/usr/bin/python


from ansible.module_utils.basic import AnsibleModule
import os
import json
import uuid
import secrets

DOCUMENTATION = r"""
---
module: masked_clients_state
short_description: Manage UUID and WS path for masked clients with persistent state
description:
  - Ensures that each masked client has a UUID and WebSocket path.
  - Stores generated values in a state file to provide idempotency.
  - If force is true, ignores stored values and regenerates or uses explicitly provided ones.
options:
  clients:
    description:
      - Dictionary of clients with their current configuration.
      - Each value is a dict that may contain 'uuid' and/or 'ws_path'.
    required: true
    type: dict
  state_file:
    description:
      - Path to the JSON file where the state is stored.
    required: true
    type: path
  force:
    description:
      - If true, ignore saved state and regenerate missing values or use provided ones.
    required: false
    default: false
    type: bool
author:
  - Your Name
"""

EXAMPLES = r"""
- name: Ensure masked clients have UUID and WS path
  masked_clients_state:
    clients: "{{ proxy_masked_clients }}"
    state_file: "/etc/ansible/state/masked_clients.json"
    force: false
  register: result

- name: Update fact with new values
  set_fact:
    proxy_masked_clients: "{{ result.clients }}"
"""

RETURN = r"""
changed:
  description: Whether any value was changed.
  returned: always
  type: bool
clients:
  description: Updated clients dictionary with filled uuid and ws_path.
  returned: success
  type: dict
"""


def generate_uuid():
    """Generate a random 32-character hex string (UUID without hyphens)."""
    return str(uuid.uuid4())


def generate_ws_path():
    """Generate a WebSocket path like /ws-<10-hex-chars>."""
    return "/ws-" + secrets.token_urlsafe()


def main():
    module = AnsibleModule(
        argument_spec=dict(
            clients=dict(type="dict", required=True),
            state_file=dict(type="path", default="/var/lib/ansible/state/masked_clients.json"),
            force=dict(type="bool", default=False),
        ),
        supports_check_mode=False,
    )

    clients = module.params["clients"]
    state_file = module.params["state_file"]
    force = module.params["force"]

    state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            module.fail_json(msg=f"Failed to read state file {state_file}: {e}")

    new_state = {}
    result_clients = {}
    changed = False

    for client_name, client_data in clients.items():
        saved = state.get(client_name, {})

        new_client = client_data.copy()

        input_uuid = client_data.get("uuid")
        saved_uuid = saved.get("uuid")
        if force:
            if input_uuid is not None:
                final_uuid = input_uuid
            else:
                final_uuid = generate_uuid()
        else:
            if saved_uuid is not None:
                final_uuid = saved_uuid
            elif input_uuid is not None:
                final_uuid = input_uuid
            else:
                final_uuid = generate_uuid()

        if final_uuid != saved_uuid:
            changed = True
        new_client["uuid"] = final_uuid

        input_ws = client_data.get("ws_path")
        saved_ws = saved.get("ws_path")
        if force:
            if input_ws is not None:
                final_ws = input_ws
            else:
                final_ws = generate_ws_path()
        else:
            if saved_ws is not None:
                final_ws = saved_ws
            elif input_ws is not None:
                final_ws = input_ws
            else:
                final_ws = generate_ws_path()

        if final_ws != saved_ws:
            changed = True
        new_client["ws_path"] = final_ws

        result_clients[client_name] = new_client

        new_state[client_name] = {"uuid": final_uuid, "ws_path": final_ws}

    if new_state != state:
        changed = True
        try:

            state_dir = os.path.dirname(state_file)
            if state_dir and not os.path.exists(state_dir):
                os.makedirs(state_dir, mode=0o700)
            with open(state_file, "w") as f:
                json.dump(new_state, f, indent=2, sort_keys=True)
        except IOError as e:
            module.fail_json(msg=f"Failed to write state file {state_file}: {e}")

    module.exit_json(changed=changed, clients=result_clients)


if __name__ == "__main__":
    main()
