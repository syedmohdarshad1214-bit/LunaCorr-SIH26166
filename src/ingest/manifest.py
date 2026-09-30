"""Validate the real-product inventory and file identities; never infer readiness."""

import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def local_path(root, value):
    """Resolve only portable, contained project-relative paths, including symlinks."""
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('File path must be a nonempty portable relative path')
    candidate = Path(value)
    if candidate.is_absolute() or '..' in candidate.parts:
        raise ValueError(f'Path must stay under application root: {value}')
    result = (root / candidate).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes application root: {value}')
    return result


def validate_inventory(records, root=ROOT):
    root = Path(root).resolve()
    schema = json.loads((ROOT / 'data/manifests/products.schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    errors = [f'{list(e.path)}: {e.message}' for e in Draft202012Validator(schema).iter_errors(records)]
    if errors:
        return errors
    seen = set()
    for record in records:
        product = record['product_id']
        if product in seen:
            errors.append(f'{product}: duplicate product_id')
        seen.add(product)
        pending = [k for k, v in record.items() if v is None]
        if pending and not record['notes'].strip():
            errors.append(f'{product}: pending fields require explanatory notes: {pending}')
        files = {record[k] for k in ('xml_file', 'browse_file', 'science_file') if record[k] is not None}
        if record['footprint'] is not None:
            source_xml = record['footprint']['source_xml']
            files.add(source_xml)
            if source_xml != record['xml_file']:
                errors.append(f'{product}: footprint source_xml must identify this product XML')
        hashes = record['checksum']
        for filename in files:
            if filename not in hashes:
                errors.append(f'{product}: acquired file lacks SHA-256: {filename}')
        for filename, expected in hashes.items():
            try:
                path = local_path(root, filename)
                if not path.is_file():
                    raise ValueError(f'Acquired file not found: {filename}')
                if sha256_file(path) != expected:
                    raise ValueError(f'SHA-256 mismatch: {filename}')
            except (ValueError, OSError) as exc:
                errors.append(f'{product}: {exc}')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'data/manifests/products.json')
    args = parser.parse_args()
    try:
        records = json.loads(args.manifest.read_text())
        errors = validate_inventory(records)
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
        records = []
    if errors:
        print(json.dumps({'status': 'INVALID', 'errors': errors}, indent=2))
        return 2
    print(json.dumps({
        'status': 'EMPTY' if not records else 'VALID_INVENTORY',
        'product_count': len(records),
        'science_download_authorized': False,
        'note': 'Inventory validity is not overlap or browse verification.',
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
