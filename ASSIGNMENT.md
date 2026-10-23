# Assignment: Network Connectivity Monitor

## Goal
Explain how DNS resolution and TCP connections help check a selected network service.

## Technology
Python 3.10+, SQLite. No pip installation required.

## Tasks
1. Run `python monitor.py --demo --out output` and open `output/report.html`.
2. Explain the five simulated checks: three reachable, two failed, and 60% check reachability. Explain why SLOW is still reachable.
3. Start `python -m http.server 8000 --bind 127.0.0.1` in another terminal. Run `python monitor.py --host localhost --port 8000 --count 3 --out live-output`.
4. Stop the server and repeat the check. Compare the two runs using the SQLite history.
5. Run `python monitor.py --demo --slow-ms 200 --out changed-output`. Explain why the slow warning changes.
6. Run `python -m unittest discover -s tests -v`.

## Show in your demonstration
- Source code: DNS lookup, TCP socket, timing, status classification, and SQL insert.
- Generated CSV, HTML, JSON, and SQLite output.
- One successful connection and one failed connection on your machine.
- One small change you made yourself, with before/after output.

## Explain these points
- DNS maps names to addresses; TCP connects to a chosen service port.
- TCP connection time is different from application response time and ICMP round-trip time.
- Failed connection checks are not packet loss and do not prove that the whole host is down.
- The TCP timeout does not bound the operating system's DNS lookup time.

## Validation note
The eight monitor tests include two live loopback tests. In the original managed environment, six passed and two were skipped because outgoing TCP connections were denied. Run them on your own machine before claiming a successful live demonstration.
