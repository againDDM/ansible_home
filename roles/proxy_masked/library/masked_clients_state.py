#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import os
import json
import uuid
import secrets

DOCUMENTATION = r"""
---
module: masked_clients_state
short_description: Manage UUID and password for masked clients with persistent state
description:
  - Ensures that each masked client has a UUID and password.
  - Stores generated values in a state file to provide idempotency.
  - If force is true, ignores stored values and regenerates or uses explicitly provided ones.
options:
  clients:
    description:
      - Dictionary of clients with their current configuration.
      - Each value is a dict that may contain 'uuid' and 'password'.
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
- name: Ensure masked clients have UUID and password
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
  description: Updated clients dictionary with filled uuid and password.
  returned: success
  type: dict
"""


def generate_uuid():
    """Generate a random UUID string."""
    return str(uuid.uuid4())


def generate_password():
    """Generate a secure random password."""
    return secrets.token_urlsafe()


def main():
    module = AnsibleModule(
        argument_spec=dict(
            clients=dict(type="dict", required=True),
            state_file=dict(
                type="path", default="/opt/proxy_masked/state/masked_clients.json"
            ),
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
        input_password = client_data.get("password")

        saved_uuid = saved.get("uuid")
        saved_password = saved.get("password")

        if force:
            final_uuid = input_uuid if input_uuid is not None else generate_uuid()
            final_password = (
                input_password if input_password is not None else generate_password()
            )
        else:
            if saved_uuid is not None:
                final_uuid = saved_uuid
            elif input_uuid is not None:
                final_uuid = input_uuid
            else:
                final_uuid = generate_uuid()

            if saved_password is not None:
                final_password = saved_password
            elif input_password is not None:
                final_password = input_password
            else:
                final_password = generate_password()

        if final_uuid != saved_uuid or final_password != saved_password:
            changed = True

        new_client["uuid"] = final_uuid
        new_client["password"] = final_password
        new_client["name"] = client_name

        result_clients[client_name] = new_client
        new_state[client_name] = {
            "uuid": final_uuid,
            "password": final_password,
            "name": client_name,
        }

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
