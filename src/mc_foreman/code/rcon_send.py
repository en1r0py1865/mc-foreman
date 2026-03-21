#!/usr/bin/env python3
"""
rcon_send.py — 通过 RCON 向 Minecraft 服务器发送命令的 MVP 脚本。

依赖：仅标准库（socket, struct），无需 pip install。

用法：
  python rcon_send.py "say Hello"
  python rcon_send.py -f commands.txt
  python rcon_send.py -f commands.txt --delay 0.5
  python rcon_send.py --host 127.0.0.1 --port 25575 --password "$MC_RCON_PASSWORD" "list"
"""

import argparse
import json
import os
import re
import socket
import struct
import sys
import time
from pathlib import Path

SERVERDATA_AUTH = 3
SERVERDATA_EXECCOMMAND = 2
_CHANGED_RE = re.compile(
    r"(?:Changed|Successfully\s+filled)\s+(\d+)\s+(?:blocks?|block\(s\))",
    re.IGNORECASE,
)
_SETBLOCK_CHANGED_RE = re.compile(r"Changed\s+the\s+block\s+at\b", re.IGNORECASE)
_RESPONSE_ERROR_MARKERS = (
    "not loaded",
    "unknown or incomplete command",
    "unknown block type",
    "unknown item",
    "unknown entity",
    "unknown dimension",
    "syntax error",
    "cannot place blocks outside",
    "could not",
    "expected",
    "invalid",
)


def _pack_packet(request_id: int, packet_type: int, payload: str) -> bytes:
    body = struct.pack('<ii', request_id, packet_type) + payload.encode('utf-8') + b'\x00\x00'
    return struct.pack('<i', len(body)) + body


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError('RCON 连接中断')
        buf += chunk
    return buf


def _read_packet(sock: socket.socket):
    raw_len = _recv_exact(sock, 4)
    (length,) = struct.unpack('<i', raw_len)
    raw_body = _recv_exact(sock, length)
    request_id, packet_type = struct.unpack('<ii', raw_body[:8])
    payload = raw_body[8:-2].decode('utf-8', errors='replace')
    return request_id, packet_type, payload


class RconClient:
    def __init__(self, host: str, port: int, password: str, timeout: float = 10):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect((host, port))
        self._request_id = 0
        self._auth(password)

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _auth(self, password: str):
        rid = self._next_id()
        self.sock.sendall(_pack_packet(rid, SERVERDATA_AUTH, password))

        # Minecraft RCON 实现不总是稳定发送“两包”。
        # 这里循环读取，直到拿到同 request id 的响应，或 auth 失败 (-1)。
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                resp_id, _resp_type, _payload = _read_packet(self.sock)
            except socket.timeout:
                break
            if resp_id == -1:
                raise PermissionError('RCON 认证失败，请检查密码')
            if resp_id == rid:
                return
        raise TimeoutError('RCON 认证超时：服务端未返回有效认证响应')

    def send(self, command: str) -> str:
        rid = self._next_id()
        self.sock.sendall(_pack_packet(rid, SERVERDATA_EXECCOMMAND, command))
        resp_id, _resp_type, payload = _read_packet(self.sock)
        if resp_id == -1:
            raise PermissionError('RCON 执行失败：认证失效')
        return payload

    def close(self):
        self.sock.close()


def load_commands(filepath: str):
    commands = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                commands.append(line)
    return commands


def _changed_blocks_from_response(response: str) -> int:
    if not response:
        return 0
    match = _CHANGED_RE.search(response)
    if match:
        return int(match.group(1))
    if _SETBLOCK_CHANGED_RE.search(response):
        return 1
    return 0


def _response_indicates_error(response: str) -> bool:
    lowered = (response or '').strip().lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in _RESPONSE_ERROR_MARKERS)


_COULD_NOT_SET_RE = re.compile(r"could not set the block", re.IGNORECASE)
_SETBLOCK_AIR_RE = re.compile(r"setblock\s+\S+\s+\S+\s+\S+\s+air\b", re.IGNORECASE)


def _is_benign_failure(command: str, response: str) -> bool:
    """Detect harmless failures like setting air where it's already air."""
    if _COULD_NOT_SET_RE.search(response or "") and _SETBLOCK_AIR_RE.search(command or ""):
        return True
    return False


def run(commands, host: str, port: int, password: str, delay: float):
    print(f'→ 连接 {host}:{port} ...')
    client = RconClient(host, port, password)
    print(f'→ 认证成功，共 {len(commands)} 条命令\n')
    summary = {
        'host': host,
        'port': port,
        'command_count': len(commands),
        'results': [],
        'error_count': 0,
        'success_count': 0,
        'changed_blocks': 0,
        'success': True,
    }
    try:
        for i, cmd in enumerate(commands, 1):
            print(f'[{i}/{len(commands)}] {cmd}')
            item = {
                'index': i,
                'command': cmd,
                'ok': False,
                'response': '',
                'error': None,
                'changed_blocks': 0,
            }
            try:
                resp = client.send(cmd)
                item['response'] = resp
                item['changed_blocks'] = _changed_blocks_from_response(resp)
                if _response_indicates_error(resp):
                    if _is_benign_failure(cmd, resp):
                        item['ok'] = True
                        item['benign_warning'] = resp
                        summary['success_count'] += 1
                        print(f'  ⚠ 良性警告 (已忽略): {resp}')
                    else:
                        item['error'] = resp or 'server reported command failure'
                        print(f'  ✗ 响应失败: {item["error"]}')
                else:
                    item['ok'] = True
                    summary['success_count'] += 1
                    summary['changed_blocks'] += item['changed_blocks']
                    if resp:
                        print(f'  ← {resp}')
            except Exception as e:
                item['error'] = str(e)
                print(f'  ✗ 错误: {e}')
            if not item['ok']:
                summary['error_count'] += 1
                summary['success'] = False
            summary['results'].append(item)
            if i < len(commands):
                time.sleep(delay)
    finally:
        client.close()
    print('\n→ 完成')
    return summary


def main():
    parser = argparse.ArgumentParser(description='RCON 命令发送工具 (MVP)')
    parser.add_argument('command', nargs='?', help='单条命令')
    parser.add_argument('-f', '--file', help='从文件读取命令（每行一条）')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=25575)
    parser.add_argument('--password', default=os.environ.get('MC_RCON_PASSWORD'))
    parser.add_argument('--delay', type=float, default=1.0, help='命令间隔秒数（默认 1）')
    parser.add_argument('--summary-json', help='把执行摘要写到 JSON 文件')
    parser.add_argument(
        '--max-error-ratio',
        type=float,
        default=0.0,
        help='最大允许错误比例 (0-1)。超过此比例才以非零退出码退出 (默认 0 = 不容忍任何错误)',
    )
    args = parser.parse_args()

    if args.file:
        commands = load_commands(args.file)
    elif args.command:
        commands = [args.command]
    else:
        parser.print_help()
        sys.exit(1)

    if not args.password:
        print('ERROR: --password or MC_RCON_PASSWORD is required')
        sys.exit(1)

    if not commands:
        print('没有要执行的命令')
        sys.exit(0)

    summary = run(commands, args.host, args.port, args.password, args.delay)

    if args.summary_json:
        path = Path(args.summary_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    if not summary['success']:
        cmd_count = summary.get('command_count', 0)
        err_count = summary.get('error_count', 0)
        if cmd_count > 0 and args.max_error_ratio > 0:
            actual_ratio = err_count / cmd_count
            if actual_ratio <= args.max_error_ratio:
                print(f'→ 错误比例 {actual_ratio:.2%} ≤ 容忍阈值 {args.max_error_ratio:.0%}，视为成功')
                sys.exit(0)
        sys.exit(1)


if __name__ == '__main__':
    main()
