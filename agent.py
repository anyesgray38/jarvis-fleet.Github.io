#!/usr/bin/env python3
"""
agent.py — Remote agent that calls back to the controller.

How to run (on the remote machine):
    python3 agent.py --host CONTROLLER_IP --secret "your-random-secret" --cert server.crt

What it does:
    1. Connects to the controller over TLS (using server.crt to verify it's really yours).
    2. Sends the shared secret to prove its identity.
    3. Waits for commands: shell execution, file upload, file download.
    4. Automatically reconnects if the controller restarts or the connection drops.
"""

import ssl
import socket
import subprocess
import json
import struct
import os
import platform
import argparse
import time


# ──────────────────────────────────────────────────────────────────────────────
# FRAMING (same helpers as listener.py — both sides must speak the same protocol)
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# SYSTEM INFO: what we tell the controller about ourselves on connect
# ──────────────────────────────────────────────────────────────────────────────

def get_info():
    return {
        'hostname': platform.node(),
        'os':       platform.system(),                          # Linux / Windows / Darwin
        'user':     os.getenv('USER') or os.getenv('USERNAME', 'unknown'),
        'cwd':      os.getcwd(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# COMMAND HANDLERS: one function per command type the controller can send
# ──────────────────────────────────────────────────────────────────────────────

def handle_shell(sock, msg):
    """
    Run a shell command and send back stdout + stderr.
    We use subprocess.run() with shell=True so the agent can handle pipes,
    wildcards, and any other shell syntax.
    """
    cmd = msg.get('cmd', '')
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,    # capture both stdout and stderr
            text=True,              # decode bytes to string automatically
            timeout=60,             # kill the process if it runs > 60 seconds
        )
        send_msg(sock, {
            'type':       'shell_result',
            'stdout':     result.stdout,
            'stderr':     result.stderr,
            'returncode': result.returncode,
        })
    except subprocess.TimeoutExpired:
        send_msg(sock, {'type': 'shell_result', 'stdout': '', 'stderr': '', 'error': 'timeout (60s)'})
    except Exception as e:
        send_msg(sock, {'type': 'shell_result', 'stdout': '', 'stderr': '', 'error': str(e)})


def handle_pine(sock, msg):
    """
    Run a Pine Script snippet through pine_runner.mjs (Node + PineTS) and
    send back the computed plot data. Requires Node.js and `npm install`
    to have been run in the agent's directory (see package.json).
    """
    cfg = {
        'script':    msg.get('script', ''),
        'provider':  msg.get('provider', 'Binance'),
        'symbol':    msg.get('symbol', ''),
        'timeframe': msg.get('timeframe', '1h'),
        'limit':     msg.get('limit', 100),
    }
    runner = msg.get('runner_path') or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'pine_runner.mjs'
    )
    try:
        result = subprocess.run(
            ['node', runner],
            input=json.dumps(cfg),
            capture_output=True,
            text=True,
            timeout=60,
        )
        try:
            payload = json.loads(result.stdout) if result.stdout else {}
        except json.JSONDecodeError:
            payload = {}
        send_msg(sock, {
            'type':   'pine_result',
            'ok':     payload.get('ok', False),
            'plots':  payload.get('plots'),
            'error':  payload.get('error') or (result.stderr or None),
        })
    except subprocess.TimeoutExpired:
        send_msg(sock, {'type': 'pine_result', 'ok': False, 'error': 'timeout (60s)'})
    except Exception as e:
        send_msg(sock, {'type': 'pine_result', 'ok': False, 'error': str(e)})


def handle_upload(sock, msg):
    """
    Receive a file from the controller and save it to disk.
    The controller sends: a JSON message with the destination path,
    then a raw blob with the file contents.
    """
    path = msg.get('path', '')
    data = recv_raw(sock)           # receive the actual file bytes

    if data is None:
        send_msg(sock, {'type': 'upload_result', 'ok': False, 'error': 'transfer interrupted'})
        return

    try:
        # Create parent directories if they don't exist
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)

        with open(path, 'wb') as f:
            f.write(data)

        send_msg(sock, {'type': 'upload_result', 'ok': True, 'bytes': len(data), 'path': path})
    except Exception as e:
        send_msg(sock, {'type': 'upload_result', 'ok': False, 'error': str(e)})


def handle_download(sock, msg):
    """
    Read a local file and send it to the controller.
    We first send a JSON message with the file size so the controller knows
    how many bytes to expect, then send the raw file bytes.
    """
    path = msg.get('path', '')
    try:
        with open(path, 'rb') as f:
            data = f.read()

        # Tell the controller: "here comes a file, this many bytes"
        send_msg(sock, {
            'type': 'file',
            'name': os.path.basename(path),
            'size': len(data),
        })
        send_raw(sock, data)        # send the actual file bytes

    except FileNotFoundError:
        send_msg(sock, {'type': 'error', 'error': f'file not found: {path}'})
    except Exception as e:
        send_msg(sock, {'type': 'error', 'error': str(e)})


# Map message type → handler function
HANDLERS = {
    'shell':    handle_shell,
    'upload':   handle_upload,
    'download': handle_download,
    'pine':     handle_pine,
}


# ──────────────────────────────────────────────────────────────────────────────
# MAIN AGENT LOOP
# ──────────────────────────────────────────────────────────────────────────────

def run_agent(host, port, secret, certfile, reconnect_delay=10):
    """
    Connect to the controller. If the connection drops for any reason,
    wait reconnect_delay seconds and try again. This runs forever.
    """

    # Build a TLS client context.
    # CERT_REQUIRED means we MUST verify the server's certificate.
    # load_verify_locations() tells Python to trust exactly our server.crt.
    # This prevents connecting to a fake controller (man-in-the-middle attack).
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(certfile)
    ctx.check_hostname = False      # cert's CN won't match a raw IP address

    while True:
        try:
            # Step 1: create a plain TCP connection (timeout=10 is for connect only)
            raw_sock = socket.create_connection((host, port), timeout=10)
            raw_sock.settimeout(None)   # switch to blocking after handshake

            # Step 2: upgrade to TLS (wrap the TCP socket in encryption)
            sock = ctx.wrap_socket(raw_sock, server_hostname=host)

            # Step 3: authenticate — send secret + our system info
            send_msg(sock, {'secret': secret, 'info': get_info()})

            # Step 4: wait for the controller to accept or reject us
            resp = recv_msg(sock)
            if not resp or not resp.get('ok'):
                print('[!] Authentication rejected — wrong secret?')
                sock.close()
                time.sleep(reconnect_delay)
                continue

            print(f'[+] Connected to controller at {host}:{port}')

            # Step 5: command loop — wait for instructions
            while True:
                msg = recv_msg(sock)
                if msg is None:
                    print('[-] Controller disconnected')
                    break

                msg_type = msg.get('type')
                handler = HANDLERS.get(msg_type)

                if handler:
                    handler(sock, msg)
                else:
                    send_msg(sock, {'type': 'error', 'error': f'unknown command: {msg_type}'})

        except (ConnectionRefusedError, socket.timeout):
            print(f'[-] Cannot reach {host}:{port}, retrying in {reconnect_delay}s...')
        except ssl.SSLError as e:
            print(f'[!] TLS error — is server.crt the right file? ({e})')
        except Exception as e:
            print(f'[!] {e}')

        time.sleep(reconnect_delay)


# ──────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='Remote agent')
    ap.add_argument('--host',      required=True,  help='Controller IP address')
    ap.add_argument('--port',      type=int, default=4444)
    ap.add_argument('--secret',    required=True,  help='Shared password')
    ap.add_argument('--cert',      required=True,  help='Path to server.crt')
    ap.add_argument('--reconnect', type=int, default=10, help='Seconds between reconnect attempts')
    args = ap.parse_args()

    run_agent(args.host, args.port, args.secret, args.cert, args.reconnect)


if __name__ == '__main__':
    main()
