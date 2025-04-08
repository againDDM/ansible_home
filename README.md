# ansible_home

home ansible infrastructure

```sh
echo '<vault_pass_here>' > .vault_pass.txt
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ansible-galaxy install -r requirements.yml
```
