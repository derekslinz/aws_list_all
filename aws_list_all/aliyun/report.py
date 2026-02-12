import json
import os
from datetime import datetime
from string import Template

from .listing import AliyunListing
from .service_names import ALIYUN_SERVICE_NAMES

try:
    from aws_list_all.listing import Listing as AwsListing
except Exception:  # pylint: disable=broad-except
    AwsListing = None


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
    if isinstance(data, dict) and 'resource_type' in data:
        return 'aliyun', AliyunListing.from_json(data)
    if AwsListing is not None and isinstance(data, dict) and 'service' in data and 'operation' in data:
        return 'aws', AwsListing.from_json(data)
    return None, None


def build_report(directory):
    entries = []
    for path in _iter_json_files(directory):
        kind, listing = _load_listing(path)
        if listing is None:
            continue
        if kind == 'aliyun':
            resources = listing.resources
            iteration_counts = getattr(listing, 'iteration_counts', None)
            if iteration_counts:
                for label, count in iteration_counts.items():
                    for resource_type in resources.keys():
                        entries.append({
                          'service': listing.service,
                          'service_label': ALIYUN_SERVICE_NAMES.get(listing.service, listing.service),
                          'region': listing.region,
                          'operation': listing.operation,
                          'iterated': label,
                          'resource_type': resource_type,
                          'count': count,
                          'file': os.path.basename(path),
                        })
            else:
              for resource_type, items in resources.items():
                entries.append({
                  'service': listing.service,
                  'service_label': ALIYUN_SERVICE_NAMES.get(listing.service, listing.service),
                  'region': listing.region,
                  'operation': listing.operation,
                  'iterated': '',
                  'resource_type': resource_type,
                  'count': len(items),
                  'file': os.path.basename(path),
                })
        elif kind == 'aws':
          resources = listing.resources
          for resource_type, items in resources.items():
            entries.append({
              'service': listing.service,
              'service_label': listing.service,
              'region': listing.region,
              'operation': listing.operation,
              'iterated': '',
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
    lines.append('service\tregion\toperation\titerated\tresource_type\tcount')
    for item in sorted(entries, key=lambda x: (x['service'], x['region'] or '', x['operation'], x['resource_type'])):
        lines.append(
            '{}\t{}\t{}\t{}\t{}\t{}'.format(
                item['service'],
                item['region'],
                item['operation'],
                item.get('iterated') or '',
                item['resource_type'],
                item['count'],
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
    lines = ['service,region,operation,iterated,resource_type,count,file']
    for item in sorted(entries, key=lambda x: (x['service'], x['region'] or '', x['operation'], x['resource_type'])):
        lines.append(
            '{},{},{},{},{},{},{}'.format(
                item['service'],
                item['region'],
                item['operation'],
                item.get('iterated') or '',
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


def write_report(directory, report_format='html', output=None):
    entries = build_report(directory)
    if output and output.endswith(".html") and report_format != "html":
        report_format = "html"
    if report_format == 'html':
        content = _format_html(entries, title="Aliyun Resource Report")
    elif report_format == 'json':
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


def _format_html(entries, title="Report"):
    summary = _summarize(entries)
    data_json = json.dumps(entries, separators=(",", ":"))
    summary_json = json.dumps(summary, separators=(",", ":"))
    template = Template("""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>$TITLE</title>
  <style>
    :root {
      --bg: #0f172a;
      --panel: #111827;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --accent: $ACCENT;
      --border: #1f2937;
      --panel-2: #0b1222;
      --chip: #0b1f2f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      background: radial-gradient(1200px 600px at 10% 10%, #13293d 0%, #0f172a 55%, #0b1020 100%);
      color: var(--text);
      line-height: 1.45;
    }
    .wrap {
      max-width: 1200px;
      margin: 0 auto;
    }
    .controls {
      display: grid;
      grid-template-columns: 1.2fr 1fr 1fr auto;
      gap: 12px;
      padding: 16px 24px 0;
      align-items: center;
    }
    .controls input, .controls select {
      width: 100%;
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: var(--panel);
      color: var(--text);
      font-size: 12px;
    }
    .controls button {
      background: var(--panel);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 10px 12px;
      border-radius: 10px;
      font-size: 12px;
      cursor: pointer;
    }
    header {
      padding: 32px 24px 16px;
      border-bottom: 1px solid var(--border);
    }
    h1 {
      margin: 0 0 8px;
      font-size: 24px;
    }
    .sub {
      color: var(--muted);
      font-size: 13px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      padding: 16px 24px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
    }
    .card h2 {
      margin: 0 0 8px;
      font-size: 14px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: .08em;
    }
    .card .big {
      font-size: 28px;
      font-weight: 700;
      color: var(--accent);
    }
    .section {
      padding: 8px 24px 24px;
    }
    details {
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 12px;
      background: #0d1426;
    }
    details summary {
      cursor: pointer;
      font-weight: 600;
      color: var(--text);
      outline: none;
    }
    details + details {
      margin-top: 10px;
    }
    .stack {
      display: grid;
      gap: 10px;
      margin-top: 10px;
    }
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 6px 12px;
      margin-top: 10px;
    }
    .node {
      color: var(--muted);
    }
    .leaf {
      color: var(--text);
    }
    .pill {
      background: var(--chip);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 11px;
      color: var(--accent);
      margin-left: 8px;
    }
    .clickable {
      cursor: pointer;
    }
    .bar-chart {
      display: grid;
      gap: 8px;
    }
    .bar {
      display: grid;
      grid-template-columns: 120px 1fr 50px;
      gap: 12px;
      align-items: center;
      font-size: 12px;
    }
    .bar .track {
      background: var(--panel-2);
      border-radius: 999px;
      height: 10px;
      position: relative;
      overflow: hidden;
    }
    .bar .fill {
      background: var(--accent);
      height: 100%;
      border-radius: 999px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      overflow: hidden;
      table-layout: fixed;
    }
    th, td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      font-size: 12px;
      text-align: left;
      vertical-align: top;
      word-break: break-word;
    }
    th {
      background: #0b1222;
      color: var(--muted);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: .06em;
      position: sticky;
      top: 0;
      z-index: 1;
    }
    tr:nth-child(even) td {
      background: #0d1426;
    }
    .num {
      text-align: right;
      font-variant-numeric: tabular-nums;
    }
    .two-col {
      display: grid;
      grid-template-columns: 1fr 2fr;
      gap: 16px;
    }
    @media (max-width: 900px) {
      .two-col { grid-template-columns: 1fr; }
      .controls { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="wrap">
  <header>
    <h1>$TITLE</h1>
    <div class="sub">Generated at $GENERATED · <span id="filteredMeta"></span></div>
  </header>
  <div class="controls">
    <input id="searchInput" placeholder="Search service, region, operation, iterated, type, file..." />
    <select id="serviceFilter"></select>
    <select id="regionFilter"></select>
    <div style="display:flex; gap:8px; justify-content:flex-end;">
      <button id="resetFilters">Reset</button>
      <button id="expandAll">Expand</button>
      <button id="collapseAll">Collapse</button>
    </div>
  </div>
  <div class="grid">
    <div class="card"><h2>Total Resources</h2><div class="big" id="totalResources">$TOTAL</div></div>
    <div class="card"><h2>Services</h2><div class="big" id="totalServices">$SERVICES</div></div>
    <div class="card"><h2>Files</h2><div class="big" id="totalFiles">$FILES</div></div>
    <div class="card"><h2>Entries</h2><div class="big" id="totalEntries">$ENTRIES</div></div>
  </div>
  <div class="section two-col">
    <div>
      <h2>Resources by Service</h2>
      <div class="bar-chart" id="serviceChart"></div>
    </div>
    <div>
      <h2>Hierarchy</h2>
      <div class="stack" id="hierarchy"></div>
    </div>
  </div>
  <div class="section">
    <h2>Details</h2>
    <div style="overflow:auto; max-height: 60vh;">
    <table>
      <thead>
        <tr>
          <th>Service</th><th>Region</th><th>Operation</th><th>Iterated</th><th>Type</th><th class="num">Count</th><th>File</th>
        </tr>
      </thead>
      <tbody id="detailBody"></tbody>
    </table>
    </div>
  </div>
  </div>
  <script>
    const entries = $ENTRIES_JSON;
    const summary = $SUMMARY_JSON;

    const SERVICE_LABELS = {};
    entries.forEach(e => { SERVICE_LABELS[e.service] = e.service_label || e.service; });

    const serviceFilter = document.getElementById('serviceFilter');
    const regionFilter = document.getElementById('regionFilter');
    const searchInput = document.getElementById('searchInput');
    const detailBody = document.getElementById('detailBody');
    const hierarchyEl = document.getElementById('hierarchy');
    const serviceChart = document.getElementById('serviceChart');

    function uniqueValues(key) {
      const set = new Set(entries.map(e => e[key] || 'global'));
      return Array.from(set).sort();
    }

    function buildSelect(select, values, label) {
      select.innerHTML = '';
      const optAll = document.createElement('option');
      optAll.value = '';
      optAll.textContent = 'All ' + label;
      select.appendChild(optAll);
      values.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v;
        select.appendChild(opt);
      });
    }

    function buildHierarchy(data) {
      const tree = {};
      data.forEach(item => {
        const region = item.region || 'global';
        const iter = item.iterated || 'all';
        tree[item.service] = tree[item.service] || {};
        tree[item.service][region] = tree[item.service][region] || {};
        tree[item.service][region][item.operation] = tree[item.service][region][item.operation] || {};
        tree[item.service][region][item.operation][iter] = tree[item.service][region][item.operation][iter] || {};
        tree[item.service][region][item.operation][iter][item.resource_type] =
          (tree[item.service][region][item.operation][iter][item.resource_type] || 0) + item.count;
      });
      return tree;
    }

    function createDetailRow(item) {
      const tr = document.createElement('tr');
      tr.dataset.service = item.service;
      tr.dataset.region = item.region || 'global';
      tr.dataset.operation = item.operation;
      tr.dataset.iterated = item.iterated || '';
      tr.dataset.type = item.resource_type;
      tr.dataset.file = item.file;
      tr.innerHTML = `
        <td>$${item.service_label}</td>
        <td>$${item.region || 'global'}</td>
        <td>$${item.operation}</td>
        <td>$${item.iterated || ''}</td>
        <td>$${item.resource_type}</td>
        <td class="num">$${item.count}</td>
        <td>$${item.file}</td>
      `;
      return tr;
    }

    function renderDetails(data) {
      detailBody.innerHTML = '';
      data.forEach(item => detailBody.appendChild(createDetailRow(item)));
    }

    function renderChart(data) {
      const totals = {};
      data.forEach(item => {
        totals[item.service] = (totals[item.service] || 0) + item.count;
      });
      const sorted = Object.entries(totals).sort((a, b) => b[1] - a[1]);
      const max = sorted.length ? sorted[0][1] : 1;
      serviceChart.innerHTML = '';
        sorted.forEach(([service, count]) => {
        const row = document.createElement('div');
        row.className = 'bar';
        row.innerHTML = `
          <div>$${SERVICE_LABELS[service] || service}</div>
          <div class="track"><div class="fill" style="width:$${(count / max) * 100}%"></div></div>
          <div class="num">$${count}</div>
        `;
        serviceChart.appendChild(row);
      });
    }

    function renderHierarchy(data) {
      const tree = buildHierarchy(data);
      hierarchyEl.innerHTML = '';
      Object.keys(tree).sort().forEach(service => {
        const serviceNode = document.createElement('details');
        serviceNode.open = true;
        const serviceTotal = data.filter(d => d.service === service).reduce((a, b) => a + b.count, 0);
        serviceNode.innerHTML = `<summary class="clickable" data-service="$${service}">$${SERVICE_LABELS[service] || service}<span class="pill">$${serviceTotal}</span></summary>`;
        const serviceStack = document.createElement('div');
        serviceStack.className = 'stack';
        Object.keys(tree[service]).sort().forEach(region => {
          const regionNode = document.createElement('details');
          regionNode.innerHTML = `<summary class="clickable" data-service="$${service}" data-region="$${region}">$${region}</summary>`;
          const regionStack = document.createElement('div');
          regionStack.className = 'stack';
          Object.keys(tree[service][region]).sort().forEach(operation => {
            const opNode = document.createElement('details');
            opNode.innerHTML = `<summary class="clickable" data-service="$${service}" data-region="$${region}" data-operation="$${operation}">$${operation}</summary>`;
            const opStack = document.createElement('div');
            opStack.className = 'stack';
            const iterKeys = Object.keys(tree[service][region][operation]).sort();
            if (iterKeys.length === 1 && iterKeys[0] === 'all') {
              const grid = document.createElement('div');
              grid.className = 'grid-2';
              Object.keys(tree[service][region][operation].all).sort().forEach(type => {
                const count = tree[service][region][operation].all[type];
                const label = document.createElement('div');
                label.className = 'node leaf clickable';
                label.dataset.service = service;
                label.dataset.region = region;
                label.dataset.operation = operation;
                label.dataset.type = type;
                label.textContent = type;
                const num = document.createElement('div');
                num.className = 'num';
                num.textContent = count;
                grid.appendChild(label);
                grid.appendChild(num);
              });
              opStack.appendChild(grid);
            } else {
              iterKeys.forEach(iter => {
                const iterNode = document.createElement('details');
                iterNode.innerHTML = `<summary class="clickable" data-service="$${service}" data-region="$${region}" data-operation="$${operation}" data-iterated="$${iter}">$${iter}</summary>`;
                const grid = document.createElement('div');
                grid.className = 'grid-2';
                Object.keys(tree[service][region][operation][iter]).sort().forEach(type => {
                  const count = tree[service][region][operation][iter][type];
                  const label = document.createElement('div');
                  label.className = 'node leaf clickable';
                  label.dataset.service = service;
                  label.dataset.region = region;
                  label.dataset.operation = operation;
                  label.dataset.iterated = iter;
                  label.dataset.type = type;
                  label.textContent = type;
                  const num = document.createElement('div');
                  num.className = 'num';
                  num.textContent = count;
                  grid.appendChild(label);
                  grid.appendChild(num);
                });
                iterNode.appendChild(grid);
                opStack.appendChild(iterNode);
              });
            }
            opNode.appendChild(opStack);
            regionStack.appendChild(opNode);
          });
          regionNode.appendChild(regionStack);
          serviceStack.appendChild(regionNode);
        });
        serviceNode.appendChild(serviceStack);
        hierarchyEl.appendChild(serviceNode);
      });
    }

    function filterData() {
      const svc = serviceFilter.value;
      const region = regionFilter.value;
      const q = searchInput.value.toLowerCase().trim();
      return entries.filter(e => {
        const r = e.region || 'global';
        if (svc && e.service !== svc) return false;
        if (region && r !== region) return false;
        if (q) {
          const hay = `$${e.service} $${r} $${e.operation} $${e.iterated || ''} $${e.resource_type} $${e.file}`.toLowerCase();
          if (!hay.includes(q)) return false;
        }
        return true;
      });
    }

    function updateSummary(data) {
      const totalResources = data.reduce((a, b) => a + b.count, 0);
      const services = new Set(data.map(d => d.service)).size;
      const files = new Set(data.map(d => d.file)).size;
      document.getElementById('totalResources').textContent = totalResources;
      document.getElementById('totalServices').textContent = services;
      document.getElementById('totalFiles').textContent = files;
      document.getElementById('totalEntries').textContent = data.length;
      document.getElementById('filteredMeta').textContent = `$${data.length} rows shown`;
    }

    function applyFilters() {
      const data = filterData();
      renderDetails(data);
      renderChart(data);
      renderHierarchy(data);
      updateSummary(data);
    }

    function setFilters(dataset) {
      if (dataset.service) serviceFilter.value = dataset.service;
      if (dataset.region) regionFilter.value = dataset.region;
      if (dataset.operation) searchInput.value = dataset.operation;
      if (dataset.iterated) searchInput.value = dataset.iterated;
      if (dataset.type) searchInput.value = dataset.type;
      applyFilters();
    }

    buildSelect(serviceFilter, uniqueValues('service'), 'Services');
    buildSelect(regionFilter, uniqueValues('region'), 'Regions');
    renderDetails(entries);
    renderChart(entries);
    renderHierarchy(entries);
    updateSummary(entries);

    serviceFilter.addEventListener('change', applyFilters);
    regionFilter.addEventListener('change', applyFilters);
    searchInput.addEventListener('input', applyFilters);

    document.getElementById('resetFilters').addEventListener('click', () => {
      serviceFilter.value = '';
      regionFilter.value = '';
      searchInput.value = '';
      applyFilters();
    });
    document.getElementById('expandAll').addEventListener('click', () => {
      document.querySelectorAll('details').forEach(d => d.open = true);
    });
    document.getElementById('collapseAll').addEventListener('click', () => {
      document.querySelectorAll('details').forEach(d => d.open = false);
    });
    hierarchyEl.addEventListener('click', (e) => {
      const target = e.target.closest('.clickable');
      if (!target || !hierarchyEl.contains(target)) return;
      if (target.tagName.toLowerCase() === 'summary') {
        setFilters(target.dataset);
      } else if (target.classList.contains('leaf')) {
        setFilters(target.dataset);
      }
    });
  </script>
</body>
</html>""")
    return template.substitute(
        TITLE=title,
        GENERATED=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        TOTAL=summary["total_resources"],
        SERVICES=len(summary["services"]),
        FILES=summary["files"],
        ENTRIES=summary["entries"],
        ENTRIES_JSON=data_json,
        SUMMARY_JSON=summary_json,
        ACCENT="#34d399",
    )
