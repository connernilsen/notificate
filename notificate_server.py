#!/usr/local/bin/python

import argparse
import os
import re
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional, Set, Tuple, Type
from urllib.parse import parse_qs, urlparse


# TODO: come up with better name?


def get_all_hosts() -> Dict[str, str]:
    hosts_found = {}
    ssh_config_path = f"{os.getenv('HOME')}/.ssh/config"
    if not os.path.isfile(ssh_config_path):
        return []
    with open(ssh_config_path) as file:
        next_name = None
        while line := file.readline():
            if name := re.search(r"Host\s(\S+)", line):
                # TODO: this is probably not going to catch all cases,
                #   but it's good enough
                next_name = name.group(1)
            elif host := re.search(r"HostName\s(\S+)", line):
                if next_name:
                    hosts_found[next_name] = host.group(1)
                    next_name = None
                else:
                    print(f"Found host {host} but no name")
    return hosts_found


def execute_command(command: List[str]) -> None:
    subprocess.run(command, check=True)


SUBPROCESS_HANDLES: Dict[str, subprocess.Popen] = {}


class TunnelHandlerHandler:
    def __init__(self, port: int, dev_servers: Dict[str, str]) -> None:
        self.port = port
        self.dev_servers = dev_servers

    def __enter__(self) -> None:
        for dev_server, name in self.dev_servers.items():
            print(f"Starting SSH into {name} @ {dev_server}")
            handle = subprocess.Popen(
                [
                    "ssh",
                    "-tt",
                    dev_server,
                    "-R",
                    f"{self.port}:localhost:{self.port}",
                ],
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=0,
            )
            SUBPROCESS_HANDLES[name] = handle

            print("Server: waiting for login success...")
            line = handle.stdout.readline()
            if "Success" not in line:
                self.handle.kill()
                raise Exception(f"Error connecting to {name}")

            print(f"Success! Connected to dev server {name}")

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        tb: Optional[Any],
    ) -> None:
        for name, handle in SUBPROCESS_HANDLES.items():
            handle.communicate(input="exit\n")

            try:
                handle.wait(10)
            except Exception as e:
                print(f"failed to exit for {name}: {e}")
                handle.kill()


class NotificateRequestHandler(BaseHTTPRequestHandler):
    run_command: List[str] = []
    error_command: List[str] = []
    hosts: Dict[str, str] = []

    def make_notificate(self) -> None:
        execute_command(self.run_command)

    def make_notificate_error(self) -> None:
        execute_command(self.error_command)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        path = url.path
        queries = parse_qs(url.query)
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.send_response(200, message="Success!")

        client_name = self.client_address
        if "host" in queries:
            hosts = queries["host"]
            if len(hosts) == 1 and hosts[0] in self.hosts:
                client = hosts[0]
                client_name = self.hosts[client]

        print(
            f"[{self.log_date_time_string()}] Received notificate request from [{client_name}] for {path}"
        )

        if path == "/validate_connection":
            print("Validated successfully")
        elif path == "/notificate":
            self.make_notificate()
        elif path == "/notificate_error":
            self.make_notificate_error()


def parse_args() -> Tuple[Set[str], int]:
    parser = argparse.ArgumentParser(
        description="Runs on your local computer to notify you when \
        a long-running command on a server has finished.",
        epilog="""
        If command has multiple steps (i.e. with ";" or "&&", then COMMAND should be a string). \

        Examples: \
        ./notificate_server.py ls \
        ./notificate_server.py ls -a \
        ./notificate_server.py -p 10935 ls -a \
        ./notificate_server.py -p 10935 "ls -a && exit 1"
        """,
    )
    parser.add_argument("-p", "--port", default="10934", type=int, required=False)
    parser.add_argument(
        "-a",
        "--address",
        action="append",
        required=False,
        help="The server ssh config name or server address to connect to. If none \
        is provided, then all HostNames present in ~/.ssh/config will be used. \
        This flag can be specified multiple times",
    )
    parser.add_argument(
        "-c",
        "--command",
        default=["say", "your thing is done"],
        required=False,
        nargs=argparse.REMAINDER,
        help='The command to run when a notificate client responds with success. If command is \
        "SILENT" then notificate will notify you by bringing the terminal window to front',
    )
    parser.add_argument(
        "-e",
        "--error-command",
        default=["say", "your thing has failed"],
        required=False,
        help="The command to run when a notificate client responds with error. Only supply one argument as a string.",
    )

    args = parser.parse_args()
    dev_servers = set() if not args.address else set(args.address)
    port = args.port

    def fix_command(command: Any) -> List[str]:
        if isinstance(command, str):
            if command == "SILENT":
                return ["osascript", "-e", 'activate application "terminal"']
            command = command.split(" ")
            if len(command) == 0:
                raise Exception("Command should have at least one argument")
            return command
        elif isinstance(command, List):
            if command == ["SILENT"]:
                return ["osascript", "-e", 'activate application "terminal"']
            command = [str(s) for s in command]
            if len(command) == 0:
                raise Exception("Command should have at least one argument")
            return command
        else:
            raise Exception(f"Command had invalid type: {type(command)}")

    NotificateRequestHandler.run_command = fix_command(args.command)
    NotificateRequestHandler.error_command = fix_command(args.error_command)

    return dev_servers, port


def notificate_server() -> None:
    dev_servers, port = parse_args()

    if dev_servers:
        hosts = dev_servers
        known_hosts = get_all_hosts()
        hosts = {known_hosts.get(host, host): host for host in hosts}
    elif config_servers := get_all_hosts():
        hosts = {address: host for host, address in config_servers.items()}
    else:
        hosts = {
            input("Which host would you like to connect to: ").strip(): "your server"
        }
    print(f"Dev servers found: {hosts}")
    with TunnelHandlerHandler(port, hosts):
        NotificateRequestHandler.hosts = hosts
        server = HTTPServer(("", port), NotificateRequestHandler)

        print(f"Starting server on port {port}...")
        print(f"Will run command <{NotificateRequestHandler.run_command}> when done...")
        print(f"\tor <{NotificateRequestHandler.error_command}> if error...")

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nGoodnight!")
        except Exception as e:
            print(f"Exiting because of non-friendly error: {e}")

        server.server_close()


if __name__ == "__main__":
    notificate_server()
