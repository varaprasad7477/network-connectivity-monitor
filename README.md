# Network Connectivity Monitor

**Python + SQLite | Networking, SQL, reporting, software testing**

Checks whether a host name resolves and whether a chosen TCP port accepts a connection. Stores each observation in SQLite and exports an HTML report, CSV, and JSON summary. Uses only the Python standard library.

## Offline demonstration

Open PowerShell in this project folder:

```powershell
python monitor.py --demo --out output
Start-Process output/report.html
```

Expected: **5 simulated checks, 3 reachable, 2 failures, 60% reachability**. One reachable connection is slow. Average successful TCP connection time is approximately **61.67 ms**.

## Live demonstration on your own machine

In one PowerShell window, start a local service bound only to your computer:

```powershell
python -m http.server 8000 --bind 127.0.0.1
```

In a second window, from this project folder:

```powershell
python monitor.py --host localhost --port 8000 --count 3 --out live-output
```

Stop the server using Ctrl+C, then run the same check again. The report should change from reachable to TCP_ERROR. You can inspect the SQLite history to see earlier observations. Demo and live modes are stored in the `mode` column; summaries cover only the current run.

To check an external service you are allowed to contact, supply its host and known port. This is a single-service check, not a port scanner. A failed TCP connection can mean a closed service port, firewall, timeout, or other connection issue; it does not prove the host is completely offline.

## What to explain

1. **DNS:** converts a host name into addresses; `getaddrinfo()` uses the OS resolver.
2. **TCP:** tries a connection to the resolved address and chosen port; sockets close after each check.
3. **Timing:** `perf_counter()` measures connection setup time in milliseconds. DNS is timed separately.
4. **SQL:** stores observations with parameterized inserts.
5. **Status:** failed resolution = DNS_ERROR; no connection = TCP_ERROR; successful connection above threshold = SLOW; otherwise UP.

```sql
SELECT host, status, COUNT(*) AS checks
FROM checks
WHERE mode = 'live'
GROUP BY host, status;
```

**Important distinction:** failed checks are not packet loss. Check reachability is not long-term service availability. The configured timeout bounds TCP connection attempts; OS DNS resolution has its own timeout behavior.

## Configuration

`--port` defaults to 443, `--count` to 3, `--interval` to 1 second, `--timeout` to 2 seconds, and `--slow-ms` to 100 ms. Count is limited to 100. `--slow-ms` is an example learning threshold, not a telecom SLA. Demo rows are explicitly simulated and do not contact their sample hostnames.


## Practice assignment and tests

Read [ASSIGNMENT.md](ASSIGNMENT.md) for the demonstration and exercises.

```powershell
python -m unittest discover -s tests -v
```

This is an educational personal project. AI assistance was used in preparing the initial implementation. Practise the code and demonstrations before presenting it in an interview. Simulated data is explicitly labeled in reports.

References: [Python sockets](https://docs.python.org/3/library/socket.html), [SQLite](https://docs.python.org/3/library/sqlite3.html), [unittest](https://docs.python.org/3/library/unittest.html).
