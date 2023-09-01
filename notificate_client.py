#!/usr/local/bin/python

import argparse
import os
import subprocess
import sys
from typing import cast, List, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen


class NotificateClientRequestHandler:
    def __init__(self, port: int):
        self.port = port

    def create_request(self, path: str) -> Request:
        host_name = os.getenv("HOSTNAME")
        return Request(
            f"http://localhost:{self.port}/{path}?host={host_name}",
            method="GET",
        )

    def send_request(self, request: Request) -> None:
        try:
            result = urlopen(request, timeout=20)
            if result.status != 200:
                raise Exception(f"Error, result was not successful: {result}")
        except URLError:
            raise Exception(
                "Error connecting to server. Make sure you have your tunnel open and server running before running this command."
            )

    def validate_connection(self) -> None:
        request = self.create_request("validate_connection")
        self.send_request(request)
        print("Server is online and reachable :)")

    def notificate(self) -> None:
        # TODO: add time
        print("Command done, notifying")

        request = self.create_request("notificate")
        self.send_request(request)

    def notificate_error(self) -> None:
        print("Command errored, notifying")

        request = self.create_request("notificate_error")
        self.send_request(request)

    def handle_immediate_notificate(self) -> None:
        print("No command given, notifying immediately")
        self.notificate()


def run_command(command: List[str]) -> None:
    print(f"Command: [{', '.join(command)}]")
    subprocess.run(command, env=os.environ)


def parse_args() -> Tuple[int, List[str]]:
    parser = argparse.ArgumentParser(
        description="Runs on your dev server to notify you when a long-running command on a server has finished.",
        epilog="""
    COMMAND is the command to perform.
    If command has multiple steps (i.e. with
    ";" or "&&", then COMMAND should be a string).

    Examples:
        ./notificate_client.py ls
        ./notificate_client.py ls -a
        ./notificate_client.py -p 10935 ls -a
        ./notificate_client.py -p 10935 "ls -a && exit 1"
    """,
    )
    parser.add_argument("-p", "--port", default="10934", type=int, required=False)
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        default=["say", "your thing is done"],
    )
    args = parser.parse_args()

    port = args.port
    command = args.command

    if isinstance(command, str):
        command = command.split(" ")
    elif isinstance(command, list):
        command = [str(token) for token in command]
        if len(command) == 1:
            command = command[0].split(" ")

    command = cast(List[str], command)

    return port, command


def notificate_client():
    port, command = parse_args()

    handler = NotificateClientRequestHandler(port)
    handler.validate_connection()

    print("You will be notified when your command is done")

    if len(sys.argv) < 2:
        handler.handle_immediate_notificate()
        return

    run_command(command)
    handler.notificate()

    print("Done!")


if __name__ == "__main__":
    notificate_client()
