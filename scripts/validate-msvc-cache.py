import re
import sys


def validate(commands):
    compiles = [line for line in commands.splitlines() if re.search(r'(?:^|\s)[/-]c(?:\s|$)', line)]
    if not compiles:
        raise RuntimeError('No MSVC compilation commands were generated')
    for line in compiles:
        if re.search(r'(?:^|\s)[/-](?:Fp|Yc|Yu|Zi|ZI)', line):
            raise RuntimeError('Generated MSVC flags prevent object caching')
    if not any(re.search(r'(?:^|\s)[/-]Z7(?:\s|$)', line) for line in compiles):
        raise RuntimeError('MSVC embedded debug information /Z7 is missing')
    print(f'Validated {len(compiles)} MSVC commands: embedded debug information, no PCH flags.')


if __name__ == '__main__':
    validate(sys.stdin.read())
