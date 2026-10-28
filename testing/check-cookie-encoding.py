#!/usr/bin/env python3
"""Check real s3270 script-port clients and cookie encodings, using local sockets."""

import argparse
import contextlib
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest

IS_ZOS = sys.platform == 'zos'
COOKIE = 'Fixed-ASCII_cookie.123'
TIMEOUT = 10


def exchange(connection, command):
    connection.sendall(command.encode('ascii') + b'\n')
    response = b''
    while not response.endswith((b'\nok\n', b'\nerror\n')):
        chunk = connection.recv(4096)
        if not chunk:
            break
        response += chunk
    return response.decode('ascii', errors='backslashreplace')


def connect(port):
    return socket.create_connection(('127.0.0.1', port), timeout=TIMEOUT)


def tag_file(path, ccsid):
    if IS_ZOS:
        # Set binary first so writing fixtures never inherits text conversion.
        subprocess.run(['/bin/chtag', '-b', str(path)], check=True)
        if ccsid == 0:
            subprocess.run(['/bin/chtag', '-r', str(path)], check=True)
        elif ccsid not in (None, 65535):
            subprocess.run(['/bin/chtag', '-t', '-c', str(ccsid), str(path)], check=True)


def file_tag(path):
    if not IS_ZOS:
        return ''
    return subprocess.check_output(['/bin/chtag', '-p', str(path)], text=True)


class Emulator:
    def __init__(self, binary, cookie, environment):
        self.binary = binary
        self.cookie = cookie
        self.environment = environment

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix='c3270-script-test-')
        self.trace = Path(self.temp.name) / 'trace'
        self.stderr_path = Path(self.temp.name) / 'stderr'
        self.stderr = self.stderr_path.open('wb')
        self.process = subprocess.Popen(
            [str(self.binary), '-scriptport', '0', '-cookiefile', str(self.cookie),
             '-trace', '-tracefile', str(self.trace)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=self.stderr, env=self.environment)
        self.port = None
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                break
            if self.trace.exists():
                raw = self.trace.read_bytes()
                # Native z/OS diagnostics can be EBCDIC; the trace may be ASCII.
                trace = raw.decode('ascii', errors='replace')
                trace += '\n' + raw.decode('cp037', errors='replace')
                match = re.search(r'Listening for s3sock scripts on 127\.0\.0\.1:(\d+)', trace)
                if match:
                    self.port = int(match.group(1))
                    break
            time.sleep(.05)
        return self

    def __exit__(self, *_):
        try:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=TIMEOUT)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=TIMEOUT)
        finally:
            self.stderr.close()
            self.temp.cleanup()

    def diagnostic(self):
        raw = self.stderr_path.read_bytes()
        return raw.decode('cp037' if IS_ZOS else 'utf-8', errors='replace')


class CookieCase(unittest.TestCase):
    def __init__(self, server, client, mode, kind, tag, expected=True):
        super().__init__()
        self.server, self.client = server, client
        self.mode, self.kind, self.tag, self.expected = mode, kind, tag, expected

    def id(self):
        return f'cookie.{self.kind}.ccsid_{self.tag}.autocvt_{self.mode}'

    def shortDescription(self):
        return self.id()

    def runTest(self):
        if not IS_ZOS and self.tag not in (None, 819, 65535):
            self.skipTest('z/OS file tags required')
        env = dict(os.environ, _BPXK_AUTOCVT=self.mode)
        env.pop('X3270COOKIEFILE', None)
        with tempfile.TemporaryDirectory(prefix='c3270-cookie-test-') as td:
            path = Path(td) / 'cookie'
            original = None
            if self.kind != 'new':
                original = b'' if self.kind == 'empty' else COOKIE.encode(
                    'cp037' if self.kind == 'ebcdic' else 'ascii')
                if original:
                    # Space has the same encoding in 037 and 1047. Their newline
                    # mappings differ, so do not use cp037 to create a 1047 LF.
                    original += b'\x40' if self.kind == 'ebcdic' else b'\n'
                path.write_bytes(original)
                tag_file(path, self.tag)
            original_tag = file_tag(path) if original else None
            saved = None
            for restart in range(2):
                with Emulator(self.server, path, env) as emulator:
                    if not self.expected:
                        if emulator.port is None:
                            self.assertIn('invalid cookie', emulator.diagnostic())
                        else:
                            self.assertIsNotNone(emulator.port, emulator.diagnostic())
                            with connect(emulator.port) as connection:
                                response = exchange(connection, f'Cookie({COOKIE}) Query(ConnectionState)')
                            self.assertIn('Incorrect cookie', response)
                            self.assertTrue(response.endswith('error\n'), response)
                        return
                    self.assertIsNotNone(emulator.port, emulator.diagnostic())
                    raw = path.read_bytes()
                    expected_cookie = COOKIE if original else raw.decode('ascii')
                    self.assertEqual(0o400, path.stat().st_mode & 0o777)
                    if original:
                        self.assertEqual(original, raw, 'existing cookie bytes changed')
                        self.assertEqual(original_tag, file_tag(path), 'existing tag changed')
                    elif IS_ZOS:
                        self.assertIn('binary', file_tag(path))
                    if saved is not None:
                        self.assertEqual(saved, raw, 'cookie changed after restart')
                    saved = raw
                    with connect(emulator.port) as connection:
                        response = exchange(connection, f'Cookie({expected_cookie}) Query(ConnectionState)')
                    self.assertTrue(response.endswith('ok\n'), response)
                    self.assertIn('not-connected', response)
                    client_env = dict(env, X3270COOKIEFILE=str(path))
                    result = subprocess.run(
                        [str(self.client), '-t', str(emulator.port), 'Query(ConnectionState)'],
                        env=client_env, capture_output=True, text=True, timeout=TIMEOUT)
                    self.assertEqual(0, result.returncode, result.stderr + result.stdout)
                    self.assertIn('not-connected', result.stdout)


class ProtocolCase(unittest.TestCase):
    def __init__(self, server, client, mode):
        super().__init__()
        self.server, self.client, self.mode = server, client, mode

    def shortDescription(self):
        return f'protocol.authentication_and_connect.autocvt_{self.mode}'

    def runTest(self):
        env = dict(os.environ, _BPXK_AUTOCVT=self.mode)
        env.pop('X3270COOKIEFILE', None)
        with tempfile.TemporaryDirectory(prefix='c3270-protocol-test-') as td:
            path = Path(td) / 'cookie'
            with Emulator(self.server, path, env) as emulator:
                self.assertIsNotNone(emulator.port, emulator.diagnostic())
                cookie = path.read_bytes().decode('ascii')
                with connect(emulator.port) as connection:
                    self.assertIn('Security cookie not supplied', exchange(connection, 'Query(ConnectionState)'))
                with connect(emulator.port) as connection:
                    self.assertIn('Incorrect cookie', exchange(connection, 'Cookie(wrong-cookie)'))
                with connect(emulator.port) as authenticated:
                    self.assertTrue(exchange(authenticated, f'Cookie({cookie})').endswith('ok\n'))
                    with connect(emulator.port) as second:
                        self.assertIn('Security cookie not supplied', exchange(second, 'Query(ConnectionState)'))
                    self.assertIn('not-connected', exchange(authenticated, 'Query(ConnectionState)'))
                    result = subprocess.run(
                        [str(self.client), '-t', str(emulator.port), 'Query(ConnectionState)'],
                        env=env, capture_output=True, text=True, timeout=TIMEOUT)
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn('Security cookie not supplied', result.stdout + result.stderr)
                    with socket.socket() as listener:
                        listener.bind(('127.0.0.1', 0))
                        listener.listen()
                        listener.settimeout(TIMEOUT)
                        # Accept the emulator before sending its NVT greeting. The
                        # listener backlog lets the asynchronous client connect first.
                        target = listener.getsockname()[1]
                        authenticated.sendall(f'Connect(a:127.0.0.1:{target})\n'.encode('ascii'))
                        with contextlib.closing(listener.accept()[0]) as peer:
                            peer.sendall(b'local cookie test host\r\n')
                            response = b''
                            while not response.endswith((b'\nok\n', b'\nerror\n')):
                                chunk = authenticated.recv(4096)
                                if not chunk:
                                    break
                                response += chunk
                            self.assertTrue(response.endswith(b'ok\n'), response)
                            self.assertIn('connected-nvt', exchange(authenticated, 'Query(ConnectionState)'))
                            exchange(authenticated, 'Quit()')
                            self.assertEqual(0, emulator.process.wait(timeout=TIMEOUT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bin_dir', nargs='?', type=Path)
    parser.add_argument('--source-dir', type=Path)
    args = parser.parse_args()
    if args.source_dir:
        servers = list(args.source_dir.glob('obj/*/s3270/s3270'))
        if len(servers) != 1:
            parser.error('expected one built s3270 under SOURCE_DIR/obj/*/s3270/')
        server = servers[0].resolve()
        client = (server.parent.parent / 'x3270if' / 'x3270if').resolve()
    elif args.bin_dir:
        server, client = (args.bin_dir / 's3270').resolve(), (args.bin_dir / 'x3270if').resolve()
    else:
        parser.error('provide BIN_DIR or --source-dir')
    if not server.is_file() or not client.is_file():
        parser.error('both s3270 and x3270if must be built')
    cases = [('new', None), ('empty', 1047), ('ascii', 0), ('ascii', 819),
             ('ascii', 1208), ('ascii', 65535), ('ebcdic', 1047)]
    suite = unittest.TestSuite()
    for mode in ('ON', 'OFF'):
        for kind, tag in cases:
            suite.addTest(CookieCase(server, client, mode, kind, tag))
        suite.addTest(CookieCase(server, client, mode, 'ascii', 1047, expected=False))
        suite.addTest(CookieCase(server, client, mode, 'ebcdic', 65535, expected=False))
        suite.addTest(ProtocolCase(server, client, mode))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f'actualFailures:{len(result.failures) + len(result.errors)}')
    print(f'totalTests:{result.testsRun}')
    print('expectedFailures:0')
    print(f'expectedTotalTests:{result.testsRun}')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
