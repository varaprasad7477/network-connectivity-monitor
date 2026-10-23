"""DNS and TCP connectivity checks with SQLite history; Python 3.10+, no pip installs."""
import argparse
from contextlib import closing
import csv
import html
import json
import math
from pathlib import Path
import socket
import sqlite3
import time
from datetime import datetime, timezone


def classify(dns_ok, tcp_ok, connect_ms, slow_ms):
    if not dns_ok:
        return 'DNS_ERROR'
    if not tcp_ok:
        return 'TCP_ERROR'
    return 'SLOW' if connect_ms > slow_ms else 'UP'


def check_target(host, port, timeout=2.0, slow_ms=100.0):
    """Resolve once, then time a TCP handshake to the returned address (not ICMP)."""
    row = dict(timestamp=datetime.now(timezone.utc).isoformat(timespec='seconds'),
               host=host, port=port, address='', dns_ms=None, connect_ms=None,
               status='DNS_ERROR', detail='')
    start = time.perf_counter()
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        row['dns_ms'] = round((time.perf_counter() - start) * 1000, 3)
    except OSError as exc:
        row['detail'] = str(exc)
        return row
    # A bounded TCP attempt per address, using the total configured connection budget.
    deadline = time.perf_counter() + timeout
    row['status'] = 'TCP_ERROR'
    for family, kind, proto, _, address in addresses:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            break
        row['address'] = address[0]
        try:
            with socket.socket(family, kind, proto) as connection:
                connection.settimeout(remaining)
                start = time.perf_counter()
                connection.connect(address)
                row['connect_ms'] = round((time.perf_counter() - start) * 1000, 3)
                row['status'] = classify(True, True, row['connect_ms'], slow_ms)
                row['detail'] = 'TCP connection accepted'
                return row
        except OSError as exc:
            row['detail'] = str(exc)
    return row


def validate(rows):
    for row in rows:
        if row['status'] not in {'UP', 'SLOW', 'DNS_ERROR', 'TCP_ERROR'}:
            raise ValueError('Unknown check status')
        if not row['host'] or not isinstance(row['port'], int) or not 1 <= row['port'] <= 65535:
            raise ValueError('Host and port must be valid')
        for name in ('dns_ms', 'connect_ms'):
            value = row[name]
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError('Timings must be finite and non-negative')
        if row['status'] in {'UP', 'SLOW'} and row['connect_ms'] is None:
            raise ValueError('A successful connection needs a timing')


def summarize(rows):
    total = len(rows)
    reachable = sum(row['status'] in {'UP', 'SLOW'} for row in rows)
    timings = [row['connect_ms'] for row in rows if row['connect_ms'] is not None]
    return dict(checks=total, reachable=reachable,
                reachability_pct=100 * reachable / total if total else None,
                failures=total - reachable,
                average_connect_ms=sum(timings) / len(timings) if timings else None)


def save_history(path, rows, mode):
    """Store only this run's checks with parameterized SQL. Demo/live stay separate."""
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('''CREATE TABLE IF NOT EXISTS checks (
            id INTEGER PRIMARY KEY, mode TEXT, timestamp TEXT, host TEXT, port INTEGER,
            address TEXT, dns_ms REAL, connect_ms REAL, status TEXT, detail TEXT)''')
        db.executemany('''INSERT INTO checks
            (mode,timestamp,host,port,address,dns_ms,connect_ms,status,detail)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            [(mode, *(r[k] for k in ('timestamp','host','port','address','dns_ms',
                                     'connect_ms','status','detail'))) for r in rows])


def write_outputs(rows, directory, mode, slow_ms):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    validate(rows)
    summary = summarize(rows)
    with (directory / 'checks.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]) if rows else
                                ['timestamp','host','port','status'])
        writer.writeheader()
        writer.writerows(rows)
    (directory / 'summary.json').write_text(
        json.dumps(dict(mode=mode, slow_threshold_ms=slow_ms, **summary), indent=2), encoding='utf-8')
    save_history(directory / 'history.sqlite', rows, mode)
    esc = lambda value: html.escape(str(value))
    cells = ''.join('<tr>' + ''.join('<td>' + esc(r.get(k) if r.get(k) is not None else 'N/A') + '</td>'
                    for k in ('timestamp','host','port','dns_ms','connect_ms','status')) + '</tr>' for r in rows)
    percent = f"{summary['reachability_pct']:.1f}%" if summary['checks'] else 'N/A'
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Network Connectivity Monitor</title><style>
    body{{font:16px system-ui;margin:40px auto;padding:0 22px;max-width:1100px;color:#182d3b;background:#f4f7fa}}
    h1{{font-size:32px}}.cards{{display:flex;flex-wrap:wrap;gap:16px}}.card{{background:white;padding:20px;border:1px solid #dbe4eb;border-radius:10px;min-width:150px}}
    strong{{display:block;font-size:26px}}table{{border-collapse:collapse;background:white;width:100%;margin-top:22px}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #dbe4eb}}.table{{overflow:auto}}.note{{padding:14px;background:#fff4da;border-radius:8px}}
    </style><h1>Network Connectivity Monitor</h1><p class="note">{esc(mode.upper())} DATA | TCP connection checks; not mobile-network coverage or ICMP packet loss.</p>
    <div class="cards"><div class="card">Checks<strong>{summary['checks']}</strong></div>
    <div class="card">Reachable<strong>{percent}</strong></div><div class="card">Failed checks<strong>{summary['failures']}</strong></div></div>
    <p>Slow TCP connection threshold: {slow_ms:g} ms. SLOW checks are reachable. All timestamps are UTC.</p>
    <div class="table"><table><thead><tr><th>Time</th><th>Host</th><th>Port</th><th>DNS ms</th><th>TCP ms</th><th>Status</th></tr></thead><tbody>{cells}</tbody></table></div>
    <p>DNS_ERROR: name resolution failed. TCP_ERROR: no connection was established; this alone does not prove the whole host is down.</p></html>'''
    (directory / 'report.html').write_text(page, encoding='utf-8')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--demo', action='store_true', help='Offline, explicitly simulated checks')
    source.add_argument('--host', help='A single host you choose to check')
    parser.add_argument('--port', type=int, default=443)
    parser.add_argument('--count', type=int, default=3)
    parser.add_argument('--interval', type=float, default=1)
    parser.add_argument('--timeout', type=float, default=2)
    parser.add_argument('--slow-ms', type=float, default=100)
    parser.add_argument('--out', default='output')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535 or not 1 <= args.count <= 100:
        parser.error('Port must be 1-65535 and count must be 1-100')
    if not all(math.isfinite(x) for x in (args.interval, args.timeout, args.slow_ms)) or args.timeout <= 0 or args.interval < 0 or args.slow_ms < 0:
        parser.error('Use finite, non-negative timing values and a positive timeout')
    if args.demo:
        rows = json.loads(Path(__file__).with_name('sample_checks.json').read_text(encoding='utf-8'))
        # Recompute successful states so custom slow thresholds remain consistent.
        for row in rows:
            if row['status'] in {'UP', 'SLOW'}:
                row['status'] = classify(True, True, row['connect_ms'], args.slow_ms)
        mode = 'simulated'
    else:
        rows = []
        for index in range(args.count):
            rows.append(check_target(args.host, args.port, args.timeout, args.slow_ms))
            if index < args.count - 1:
                time.sleep(args.interval)
        mode = 'live'
    try:
        summary = write_outputs(rows, args.out, mode, args.slow_ms)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f'Could not write report: {exc}\n')
    print(json.dumps(dict(mode=mode, **summary), indent=2))
    print(f'Report: {Path(args.out).resolve() / "report.html"}')


if __name__ == '__main__':
    main()
