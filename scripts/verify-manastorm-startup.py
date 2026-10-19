import argparse
import re
from pathlib import Path


def verify(config, logs):
    values = re.findall(r'(?mi)^\s*Manastorm\.Enable\s*=\s*([^\r\n#]+)', config)
    value = values[-1].strip().lower() if values else '1'
    if value in ('0', 'false', 'no'):
        return False
    if value not in ('1', 'true', 'yes'):
        raise RuntimeError('Unrecognized Manastorm.Enable setting')
    if 'Shared Manastorm backend initialized.' not in logs:
        raise RuntimeError('Worldserver started without initializing the enabled Manastorm backend')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--core', required=True, type=Path)
    parser.add_argument('--tree', required=True, type=Path)
    parser.add_argument('--logs', required=True, type=Path)
    args = parser.parse_args()
    if (args.core / 'modules/mod-manastorm-endless').is_dir():
        config = args.tree / 'Core/configs/modules/manastorm-endless.conf.dist'
        text = '\n'.join(p.read_text(encoding='utf-8', errors='replace') for p in args.logs.glob('*.log'))
        enabled = verify(config.read_text(encoding='utf-8-sig'), text)
        print('Manastorm backend initialized' if enabled else 'Manastorm explicitly disabled')
    else:
        print('This core does not include Manastorm')
