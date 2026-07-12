#!/usr/bin/env python3
"""
orchestrator.py — Multi-agent controller with HTTP API and parallel dispatch.

Extends listener.py with:
  - HTTP REST API on --api-port (default 8888)
  - Parallel broadcast across all or tagged agents
  - Per-task parallel execution (different commands to different agents)
  - Agent tagging for grouping

Run:
    python3 orchestrator.py --secret "yourpassword" --port 4444 --api-port 8888

HTTP API:
    GET  /agents                    — list connected agents
    GET  /health                    — liveness check
    POST /agents/{id}/shell         — run cmd on specific agent  body: {cmd}
    POST /agents/{id}/pine          — run Pine Script on agent   body: {script, provider?, symbol, timeframe?, limit?}
    POST /agents/{id}/tag           — add tags to agent          body: {tags:[]}
    POST /broadcast                 — same cmd to all agents     body: {cmd, tags?:[]}
    POST /parallel                  — different cmds in parallel body: {tasks:[{agent_id,cmd}]}
    POST /queue                     — run now, or hold for next reconnect  body: {hostname, cmd}
    GET  /jobs                      — list all jobs (queued/running/done)
    GET  /jobs/{id}                 — get one job's status/result
    GET  /queue/{hostname}          — list jobs still pending for a hostname
"""

import ssl
import socket
import threading
import json
import struct
import os
import sys
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse


# ── Framing ───────────────────────────────────────────────────────────────────

def _recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def send_msg(sock, obj):
    raw = json.dumps(obj).encode()
    sock.sendall(struct.pack('>I', len(raw)) + raw)


def recv_msg(sock):
    hdr = _recv_exact(sock, 4)
    if not hdr:
        return None
    (length,) = struct.unpack('>I', hdr)
    raw = _recv_exact(sock, length)
    return json.loads(raw) if raw else None


def send_raw(sock, data: bytes):
    sock.sendall(struct.pack('>I', len(data)) + data)


def recv_raw(sock):
    hdr = _recv_exact(sock, 4)
    if not hdr:
        return None
    (length,) = struct.unpack('>I', hdr)
    return _recv_exact(sock, length)


# ── AgentSession ──────────────────────────────────────────────────────────────

class AgentSession:
    def __init__(self, sock, addr, agent_id, info):
        self.sock = sock
        self.addr = addr
        self.id = agent_id
        self.info = info
        self.connected_at = datetime.now()
        self.tags: set[str] = set()
        self._lock = threading.Lock()
        self.alive = True

    def shell(self, cmd: str) -> dict:
        with self._lock:
            try:
                send_msg(self.sock, {'type': 'shell', 'cmd': cmd})
                result = recv_msg(self.sock)
                return result or {'error': 'no response'}
            except Exception as e:
                self.alive = False
                return {'error': str(e)}

    def pine(self, cfg: dict) -> dict:
        with self._lock:
            try:
                send_msg(self.sock, {'type': 'pine', **cfg})
                result = recv_msg(self.sock)
                return result or {'error': 'no response'}
            except Exception as e:
                self.alive = False
                return {'error': str(e)}

    def upload(self, local_path: str, remote_path: str) -> dict:
        with open(local_path, 'rb') as f:
            data = f.read()
        with self._lock:
            try:
                send_msg(self.sock, {'type': 'upload', 'path': remote_path})
                send_raw(self.sock, data)
                return recv_msg(self.sock) or {'error': 'no response'}
            except Exception as e:
                self.alive = False
                return {'error': str(e)}

    def download(self, remote_path: str, local_path: str) -> dict:
        with self._lock:
            try:
                send_msg(self.sock, {'type': 'download', 'path': remote_path})
                meta = recv_msg(self.sock)
                if not meta or meta.get('type') != 'file':
                    return meta or {'error': 'unexpected response'}
                data = recv_raw(self.sock)
            except Exception as e:
                self.alive = False
                return {'error': str(e)}

        if data is None:
            return {'error': 'transfer interrupted'}
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        with open(local_path, 'wb') as f:
            f.write(data)
        return {'ok': True, 'bytes': len(data), 'saved': local_path}

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'ip': self.addr[0],
            'port': self.addr[1],
            'hostname': self.info.get('hostname', '?'),
            'user': self.info.get('user', '?'),
            'os': self.info.get('os', '?'),
            'cwd': self.info.get('cwd', '?'),
            'tags': sorted(self.tags),
            'connected_at': self.connected_at.isoformat(),
            'alive': self.alive,
        }

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


# ── Orchestrator ──────────────────────────────────────────────────────────────

class Orchestrator:
    def __init__(self, secret, port, certfile, keyfile, api_port):
        self.secret = secret
        self.port = port
        self.certfile = certfile
        self.keyfile = keyfile
        self.api_port = api_port
        self.agents: dict[int, AgentSession] = {}
        self._next_id = 1
        self._lock = threading.Lock()

        # Queued jobs, keyed by hostname since agent ids are reassigned on
        # every reconnect and can't be used to target an offline machine.
        self.jobs: dict[int, dict] = {}
        self.pending_by_host: dict[str, list[int]] = {}
        self._next_job_id = 1
        self._job_lock = threading.Lock()

    # ── Agent access ──────────────────────────────────────────────────────────

    def _live_agents(self, tags: list | None = None) -> list[AgentSession]:
        with self._lock:
            sessions = list(self.agents.values())
        if tags:
            sessions = [s for s in sessions if s.tags.issuperset(tags)]
        return [s for s in sessions if s.alive]

    def _find_by_hostname(self, hostname: str) -> AgentSession | None:
        with self._lock:
            for s in self.agents.values():
                if s.alive and s.info.get('hostname') == hostname:
                    return s
        return None

    def _drop(self, session: AgentSession):
        with self._lock:
            self.agents.pop(session.id, None)
        session.close()

    # ── Job queue ─────────────────────────────────────────────────────────────

    def queue_job(self, hostname: str, cmd: str) -> dict:
        with self._job_lock:
            jid = self._next_job_id
            self._next_job_id += 1
            job = {
                'id': jid,
                'hostname': hostname,
                'cmd': cmd,
                'status': 'queued',
                'result': None,
                'created_at': datetime.now().isoformat(),
                'completed_at': None,
            }
            self.jobs[jid] = job

        session = self._find_by_hostname(hostname)
        if session:
            self._run_job(job, session)
        else:
            with self._job_lock:
                self.pending_by_host.setdefault(hostname, []).append(jid)
        return job

    def _run_job(self, job: dict, session: AgentSession):
        job['status'] = 'running'
        result = session.shell(job['cmd'])
        job['result'] = result
        job['status'] = 'done'
        job['completed_at'] = datetime.now().isoformat()
        if not session.alive:
            self._drop(session)

    def drain_queue(self, session: AgentSession):
        """Run any jobs queued for this hostname now that it's back online."""
        hostname = session.info.get('hostname')
        with self._job_lock:
            job_ids = self.pending_by_host.pop(hostname, [])
        for jid in job_ids:
            job = self.jobs.get(jid)
            if job:
                self._run_job(job, session)

    # ── Parallel dispatch ─────────────────────────────────────────────────────

    def broadcast(self, cmd: str, tags: list | None = None) -> list[dict]:
        sessions = self._live_agents(tags)
        if not sessions:
            return []
        results = []
        with ThreadPoolExecutor(max_workers=min(len(sessions), 64)) as pool:
            future_map = {pool.submit(s.shell, cmd): s for s in sessions}
            for future, session in future_map.items():
                r = future.result()
                results.append({'agent': session.to_dict(), 'result': r})
                if not session.alive:
                    self._drop(session)
        return results

    def parallel(self, tasks: list[dict]) -> list[dict]:
        results = []
        valid: list[tuple[AgentSession, str]] = []

        with self._lock:
            for task in tasks:
                aid = task.get('agent_id')
                session = self.agents.get(aid)
                if session and session.alive:
                    valid.append((session, task.get('cmd', '')))
                else:
                    results.append({'agent_id': aid, 'error': 'agent not found or offline'})

        if not valid:
            return results

        with ThreadPoolExecutor(max_workers=min(len(valid), 64)) as pool:
            future_map = {pool.submit(s.shell, cmd): s for s, cmd in valid}
            for future, session in future_map.items():
                r = future.result()
                results.append({'agent': session.to_dict(), 'result': r})
                if not session.alive:
                    self._drop(session)
        return results

    # ── TLS accept loop ───────────────────────────────────────────────────────

    def _tls_ctx(self):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(self.certfile, self.keyfile)
        return ctx

    def _accept_loop(self, srv, tls):
        while True:
            try:
                raw_sock, addr = srv.accept()
                threading.Thread(
                    target=self._handshake,
                    args=(tls, raw_sock, addr),
                    daemon=True,
                ).start()
            except Exception as e:
                print(f'[!] Accept error: {e}')

    def _handshake(self, tls, raw_sock, addr):
        try:
            sock = tls.wrap_socket(raw_sock, server_side=True)
        except ssl.SSLError as e:
            print(f'[!] TLS failed from {addr}: {e}')
            raw_sock.close()
            return

        msg = recv_msg(sock)
        if not msg or msg.get('secret') != self.secret:
            send_msg(sock, {'type': 'auth', 'ok': False})
            sock.close()
            return

        send_msg(sock, {'type': 'auth', 'ok': True})

        with self._lock:
            aid = self._next_id
            self._next_id += 1
            session = AgentSession(sock, addr, aid, msg.get('info', {}))
            self.agents[aid] = session

        info = session.info
        print(
            f'\n[+] Agent {aid} connected  '
            f'{info.get("user","?")}@{info.get("hostname","?")}  '
            f'{addr[0]}  {info.get("os","?")}'
        )
        print('orchestrator> ', end='', flush=True)

        threading.Thread(target=self.drain_queue, args=(session,), daemon=True).start()

    # ── HTTP API ──────────────────────────────────────────────────────────────

    def _start_api(self):
        orch = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass

            def _send(self, code: int, data):
                body = json.dumps(data, default=str).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _body(self) -> dict:
                n = int(self.headers.get('Content-Length', 0))
                return json.loads(self.rfile.read(n)) if n else {}

            def do_GET(self):
                path = urlparse(self.path).path
                if path == '/agents':
                    agents = orch._live_agents()
                    self._send(200, {'agents': [a.to_dict() for a in agents]})
                elif path == '/health':
                    self._send(200, {'ok': True, 'agents': len(orch.agents)})
                elif path == '/jobs':
                    with orch._job_lock:
                        jobs = list(orch.jobs.values())
                    self._send(200, {'jobs': jobs})
                elif path.startswith('/jobs/'):
                    try:
                        jid = int(path.rsplit('/', 1)[-1])
                    except ValueError:
                        return self._send(400, {'error': 'invalid id'})
                    with orch._job_lock:
                        job = orch.jobs.get(jid)
                    if not job:
                        return self._send(404, {'error': 'job not found'})
                    self._send(200, job)
                elif path.startswith('/queue/'):
                    hostname = path[len('/queue/'):]
                    with orch._job_lock:
                        job_ids = orch.pending_by_host.get(hostname, [])
                        jobs = [orch.jobs[jid] for jid in job_ids if jid in orch.jobs]
                    self._send(200, {'hostname': hostname, 'pending': jobs})
                else:
                    self._send(404, {'error': 'not found'})

            def do_POST(self):
                path = urlparse(self.path).path
                body = self._body()
                parts = path.strip('/').split('/')

                # /agents/{id}/shell
                if len(parts) == 3 and parts[0] == 'agents' and parts[2] == 'shell':
                    try:
                        aid = int(parts[1])
                    except ValueError:
                        return self._send(400, {'error': 'invalid id'})
                    with orch._lock:
                        session = orch.agents.get(aid)
                    if not session or not session.alive:
                        return self._send(404, {'error': 'agent not found'})
                    cmd = body.get('cmd', '')
                    if not cmd:
                        return self._send(400, {'error': 'cmd required'})
                    result = session.shell(cmd)
                    if not session.alive:
                        orch._drop(session)
                    self._send(200, {'agent': session.to_dict(), 'result': result})

                # /agents/{id}/pine
                elif len(parts) == 3 and parts[0] == 'agents' and parts[2] == 'pine':
                    try:
                        aid = int(parts[1])
                    except ValueError:
                        return self._send(400, {'error': 'invalid id'})
                    with orch._lock:
                        session = orch.agents.get(aid)
                    if not session or not session.alive:
                        return self._send(404, {'error': 'agent not found'})
                    if not body.get('script') or not body.get('symbol'):
                        return self._send(400, {'error': 'script and symbol required'})
                    result = session.pine(body)
                    if not session.alive:
                        orch._drop(session)
                    self._send(200, {'agent': session.to_dict(), 'result': result})

                # /agents/{id}/tag
                elif len(parts) == 3 and parts[0] == 'agents' and parts[2] == 'tag':
                    try:
                        aid = int(parts[1])
                    except ValueError:
                        return self._send(400, {'error': 'invalid id'})
                    with orch._lock:
                        session = orch.agents.get(aid)
                    if not session:
                        return self._send(404, {'error': 'agent not found'})
                    session.tags.update(body.get('tags', []))
                    self._send(200, {'agent': session.to_dict()})

                # /broadcast
                elif path == '/broadcast':
                    cmd = body.get('cmd', '')
                    if not cmd:
                        return self._send(400, {'error': 'cmd required'})
                    results = orch.broadcast(cmd, body.get('tags'))
                    self._send(200, {'results': results, 'count': len(results)})

                # /parallel
                elif path == '/parallel':
                    tasks = body.get('tasks', [])
                    if not tasks:
                        return self._send(400, {'error': 'tasks required'})
                    results = orch.parallel(tasks)
                    self._send(200, {'results': results})

                # /queue — run now if the host is online, else hold until it reconnects
                elif path == '/queue':
                    hostname = body.get('hostname', '')
                    cmd = body.get('cmd', '')
                    if not hostname or not cmd:
                        return self._send(400, {'error': 'hostname and cmd required'})
                    job = orch.queue_job(hostname, cmd)
                    self._send(200, job)

                else:
                    self._send(404, {'error': 'not found'})

        server = HTTPServer(('127.0.0.1', self.api_port), Handler)
        print(f'[*] HTTP API on 127.0.0.1:{self.api_port}')
        server.serve_forever()

    # ── Interactive CLI ───────────────────────────────────────────────────────

    def _cli(self):
        print('Commands: list | use <id> | broadcast <cmd> | tag <id> <label> | exit\n')
        while True:
            try:
                line = input('orchestrator> ').strip()
            except (EOFError, KeyboardInterrupt):
                print('\n[*] Bye')
                sys.exit(0)

            if not line:
                continue

            parts = line.split(None, 1)
            verb = parts[0].lower()

            if verb == 'list':
                with self._lock:
                    snapshot = list(self.agents.values())
                if not snapshot:
                    print('  (no agents connected)')
                for s in snapshot:
                    status = 'alive' if s.alive else 'dead'
                    tags = f'  [{",".join(sorted(s.tags))}]' if s.tags else ''
                    print(
                        f'  [{s.id}]  {s.addr[0]}'
                        f'  {s.info.get("user","?")}@{s.info.get("hostname","?")}'
                        f'  {s.info.get("os","?")}  {status}{tags}'
                    )

            elif verb == 'use':
                try:
                    aid = int(parts[1])
                except (ValueError, IndexError):
                    print('usage: use <id>')
                    continue
                with self._lock:
                    session = self.agents.get(aid)
                if not session:
                    print(f'[!] No agent {aid}')
                    continue
                self._agent_repl(session)

            elif verb == 'broadcast':
                if len(parts) < 2:
                    print('usage: broadcast <cmd>')
                    continue
                results = self.broadcast(parts[1])
                if not results:
                    print('  (no live agents)')
                for item in results:
                    a = item['agent']
                    r = item['result']
                    print(f'\n  [{a["id"]}] {a["ip"]}  {a["user"]}@{a["hostname"]}')
                    if r.get('stdout'):
                        print(r['stdout'], end='')
                    if r.get('stderr'):
                        print('[stderr]', r['stderr'], end='')
                    if r.get('error'):
                        print(f'  [!] {r["error"]}')

            elif verb == 'tag':
                rest = (parts[1].split() if len(parts) > 1 else [])
                if len(rest) < 2:
                    print('usage: tag <id> <label>')
                    continue
                try:
                    aid = int(rest[0])
                except ValueError:
                    print('[!] id must be a number')
                    continue
                with self._lock:
                    session = self.agents.get(aid)
                if not session:
                    print(f'[!] No agent {aid}')
                    continue
                session.tags.add(rest[1])
                print(f'[+] Agent {aid} tags: {sorted(session.tags)}')

            elif verb in ('exit', 'quit'):
                sys.exit(0)

            else:
                print('Commands: list | use <id> | broadcast <cmd> | tag <id> <label> | exit')

    def _agent_repl(self, s: AgentSession):
        print(f'[*] Attached to agent {s.id} ({s.addr[0]})')
        print('    shell <cmd> | upload <local> <remote> | download <remote> <local> | back\n')
        while True:
            try:
                line = input(f'agent[{s.id}]> ').strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not line:
                continue
            parts = line.split(None, 1)
            verb = parts[0].lower()

            if verb == 'back':
                return

            elif verb == 'shell':
                if len(parts) < 2:
                    print('usage: shell <command>')
                    continue
                r = s.shell(parts[1])
                if not s.alive:
                    print('[!] Agent disconnected')
                    self._drop(s)
                    return
                if r.get('stdout'):
                    print(r['stdout'], end='')
                if r.get('stderr'):
                    sys.stderr.write(r['stderr'])
                if r.get('error'):
                    print(f'[!] {r["error"]}')

            elif verb == 'upload':
                paths = (parts[1].split(None, 1) if len(parts) > 1 else [])
                if len(paths) < 2:
                    print('usage: upload <local> <remote>')
                    continue
                if not os.path.isfile(paths[0]):
                    print(f'[!] Not found: {paths[0]}')
                    continue
                print(s.upload(paths[0], paths[1]))

            elif verb == 'download':
                paths = (parts[1].split(None, 1) if len(parts) > 1 else [])
                if len(paths) < 2:
                    print('usage: download <remote> <local>')
                    continue
                print(s.download(paths[0], paths[1]))

            else:
                print('shell | upload | download | back')

    # ── Start ─────────────────────────────────────────────────────────────────

    def start(self, headless: bool = False):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(('0.0.0.0', self.port))
        srv.listen(50)
        print(f'[*] Agent listener  0.0.0.0:{self.port}')

        tls = self._tls_ctx()
        threading.Thread(target=self._accept_loop, args=(srv, tls), daemon=True).start()
        threading.Thread(target=self._start_api, daemon=True).start()

        if headless:
            print('[*] Headless mode — use HTTP API or Ctrl-C to stop')
            threading.Event().wait()   # block main thread without a CLI
        else:
            self._cli()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='Multi-agent orchestrator')
    ap.add_argument('--secret',   required=True,  help='Shared auth password')
    ap.add_argument('--port',     type=int, default=4444, help='Agent listener port')
    ap.add_argument('--api-port', type=int, default=8888, help='HTTP API port')
    ap.add_argument('--cert',     default='server.crt')
    ap.add_argument('--key',      default='server.key')
    ap.add_argument('--headless', action='store_true', help='No interactive CLI (API-only mode)')
    args = ap.parse_args()

    Orchestrator(args.secret, args.port, args.cert, args.key, args.api_port).start(args.headless)


if __name__ == '__main__':
    main()
