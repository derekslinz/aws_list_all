import json
import os

from .listing import Listing


def _iter_json_files(directory):
    for name in sorted(os.listdir(directory)):
        if not name.endswith('.json'):
            continue
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            yield path


def _load_listing(path):
    with open(path, 'rb') as infile:
        data = json.load(infile)
    if isinstance(data, dict) and 'service' in data and 'operation' in data:
        return Listing.from_json(data)
    return None


def build_report(directory):
    entries = []
    for path in _iter_json_files(directory):
        listing = _load_listing(path)
        if listing is None:
            continue
        resources = listing.resources
        for resource_type, items in resources.items():
            entries.append({
                'service': listing.service,
                'region': listing.region,
                'operation': listing.operation,
                'resource_type': resource_type,
                'count': len(items),
                'file': os.path.basename(path),
            })
    return entries


def _summarize(entries):
    total = sum(item['count'] for item in entries)
    services = {}
    for item in entries:
        services.setdefault(item['service'], 0)
        services[item['service']] += item['count']
    summary = {
        'total_resources': total,
        'services': dict(sorted(services.items(), key=lambda x: x[0])),
        'files': len(set(item['file'] for item in entries)),
        'entries': len(entries),
    }
    return summary


def _format_text(entries):
    lines = []
    lines.append('service\tregion\toperation\tresource_type\tcount')
    for item in sorted(entries, key=lambda x: (x['service'], x['region'] or '', x['operation'], x['resource_type'])):
        lines.append(
            '{}\t{}\t{}\t{}\t{}'.format(
                item['service'], item['region'], item['operation'], item['resource_type'], item['count']
            )
        )
    summary = _summarize(entries)
    lines.append('')
    lines.append('total_resources\t{}'.format(summary['total_resources']))
    lines.append('files\t{}'.format(summary['files']))
    lines.append('entries\t{}'.format(summary['entries']))
    for service, count in summary['services'].items():
        lines.append('service:{}\t{}'.format(service, count))
    return '\n'.join(lines)


def _format_csv(entries):
    lines = ['service,region,operation,resource_type,count,file']
    for item in sorted(entries, key=lambda x: (x['service'], x['region'] or '', x['operation'], x['resource_type'])):
        lines.append(
            '{},{},{},{},{},{}'.format(
                item['service'],
                item['region'],
                item['operation'],
                item['resource_type'],
                item['count'],
                item['file'],
            )
        )
    return '\n'.join(lines)


def _format_json(entries):
    return json.dumps({
        'entries': entries,
        'summary': _summarize(entries),
    }, indent=2, sort_keys=True)


def write_report(directory, report_format='text', output=None):
    entries = build_report(directory)
    if report_format == 'json':
        content = _format_json(entries)
    elif report_format == 'csv':
        content = _format_csv(entries)
    else:
        content = _format_text(entries)
    if output:
        with open(output, 'w') as outfile:
            outfile.write(content)
    else:
        print(content)
