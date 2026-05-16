#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import configparser
import os


def main():
    module = AnsibleModule(
        argument_spec=dict(
            file_path=dict(type='str', required=False),
            content=dict(type='str', required=False),
        ),
        mutually_exclusive=[['file_path', 'content']],
        required_one_of=[['file_path', 'content']],
    )

    file_path = module.params['file_path']
    content = module.params['content']

    try:
        if content:
            config_content = content
        else:
            if not os.path.exists(file_path):
                module.fail_json(msg=f"Файл не найден: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                config_content = f.read()
    except Exception as e:
        module.fail_json(msg=f"Ошибка чтения конфигурации: {str(e)}")

    # Подготовка: делаем секции [Peer] уникальными
    lines = config_content.splitlines()
    peer_count = 0
    modified_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith('[peer]'):
            peer_count += 1
            # Сохраняем оригинальные отступы/пробелы
            prefix = line[:line.find('[')]
            modified_lines.append(f"{prefix}[Peer_{peer_count}]")
        else:
            modified_lines.append(line)

    modified_config = '\n'.join(modified_lines)

    # ConfigParser
    config = configparser.ConfigParser(
        allow_no_value=True,
        inline_comment_prefixes=('#', ';'),
        strict=False,
        delimiters=('=',)
    )
    # Важно: сохраняем оригинальный регистр ключей
    config.optionxform = lambda option: option

    try:
        config.read_string(modified_config)
    except Exception as e:
        module.fail_json(msg=f"Ошибка парсинга конфига: {str(e)}")

    parsed_data = {
        'interface': {},
        'peers': []
    }

    # === Interface ===
    if config.has_section('Interface'):
        for key, value in config.items('Interface'):
            if value is None:
                parsed_data['interface'][key] = None
                continue

            # Убираем inline-комментарии
            clean_value = value.split('#', 1)[0].split(';', 1)[0].strip()
            # Разбиваем по запятым
            values = [v.strip() for v in clean_value.split(',') if v.strip()]
            parsed_data['interface'][key] = values[0] if len(values) == 1 else values

    # === Peers ===
    for i in range(1, peer_count + 1):
        section = f'Peer_{i}'
        if config.has_section(section):
            peer_data = {}
            for key, value in config.items(section):
                if value is None:
                    peer_data[key] = None
                    continue
                clean_value = value.split('#', 1)[0].split(';', 1)[0].strip()
                values = [v.strip() for v in clean_value.split(',') if v.strip()]
                peer_data[key] = values[0] if len(values) == 1 else values
            parsed_data['peers'].append(peer_data)

    module.exit_json(
        changed=False,
        parsed_config=parsed_data,
        peer_count=peer_count
    )


if __name__ == '__main__':
    main()
