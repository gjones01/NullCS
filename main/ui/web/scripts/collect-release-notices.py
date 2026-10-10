"""Collect upstream notices from the exact installed build inputs, without secrets."""
from importlib.metadata import distributions
from pathlib import Path
import json
import re
import shutil
import sys
import tomllib

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parents[2]
OUT = WEB / 'src-tauri/resources/legal'


def is_notice(path):
    return bool(re.match(r'^(licen[cs]e|copying|notice|copyright|authors)([._-]|$)', path.name, re.I))


def collect():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ('LICENSE', 'NOTICE.md'):
        shutil.copy2(ROOT / name, OUT / name)
    shutil.copy2(WEB / 'licenses/README.md', OUT / 'UPSTREAM-SOURCES.md')
    records = []

    def add(ecosystem, name, version, license_name, paths):
        slug = re.sub(r'[^A-Za-z0-9._-]', '_', f'{name}-{version}')
        target = OUT / ecosystem / slug
        copied = []
        for i, path in enumerate(sorted(set(paths))):
            if not path.is_file():
                continue
            target.mkdir(parents=True, exist_ok=True)
            dest = target / f'{i:03d}-{path.name}'
            shutil.copy2(path, dest)
            copied.append(dest.relative_to(OUT).as_posix())
        records.append(dict(ecosystem=ecosystem, name=name, version=version,
                            license=license_name, notices=copied))

    for dist in distributions():
        paths = [Path(dist.locate_file(f)) for f in (dist.files or []) if is_notice(Path(f))]
        fallback = WEB / 'licenses' / (dist.metadata['Name'].lower() + '-LICENSE.txt')
        if fallback.is_file():
            paths.append(fallback)
        add('python', dist.metadata['Name'], dist.version,
            dist.metadata.get('License-Expression') or dist.metadata.get('License') or '', paths)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file():
        raise SystemExit('CPython license missing')
    shutil.copy2(python_license, OUT / 'CPython-LICENSE.txt')

    lock = json.loads((WEB / 'package-lock.json').read_text(encoding='utf-8'))
    for relative, info in lock['packages'].items():
        if not relative:
            continue
        package = WEB / relative
        add('npm', relative.removeprefix('node_modules/'), info.get('version', ''),
            info.get('license', ''), [p for p in package.glob('*') if is_notice(p)])

    registry = Path.home() / '.cargo/registry/src'
    lock = tomllib.loads((WEB / 'src-tauri/Cargo.lock').read_text(encoding='utf-8'))
    for package in lock['package']:
        if not package.get('source', '').startswith('registry+'):
            continue
        candidates = list(registry.glob(f"*/{package['name']}-{package['version']}"))
        if not candidates:
            # Cross-platform lock entries need not be installed on this Windows runner.
            continue
        source = candidates[0]
        meta = tomllib.loads((source / 'Cargo.toml').read_text(encoding='utf-8'))['package']
        notices = [p for p in source.glob('*') if is_notice(p)]
        family = 'unic' if package['name'].startswith('unic-') else 'webview2' if package['name'].startswith('webview2-') else package['name']
        notices.extend((WEB / 'licenses').glob(f'{family}-LICENSE*.txt'))
        if meta.get('license-file'):
            notices.append(source / meta['license-file'])
        add('rust', package['name'], package['version'], meta.get('license', ''), notices)
    (OUT / 'inventory.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(f'Collected notices for {len(records)} dependency records')


if __name__ == '__main__':
    collect()
