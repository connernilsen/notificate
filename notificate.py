#!/usr/local/bin/python

import os

from notificate_client import notificate_client
from notificate_server import notificate_server

# TODO: come up with better name?
# TODO: plugin system for custom handling when done


def main() -> None:
    if os.getenv("HOSTNAME"):
        notificate_client()
    else:
        notificate_server()


if __name__ == "__main__":
    main()
