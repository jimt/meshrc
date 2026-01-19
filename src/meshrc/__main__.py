import argparse
import sys

from . import __version__
from .app import MeshrcApp


def run():
    parser = argparse.ArgumentParser(description=f"MeshRC {__version__}")

    parser.add_argument("-s", "--serial", help="Serial port (e.g. /dev/ttyUSB0)")
    parser.add_argument(
        "-b",
        "--baudrate",
        type=int,
        default=115200,
        help="Baud rate for serial connection",
    )
    parser.add_argument("-t", "--target", help="TCP host (e.g. localhost)")
    parser.add_argument("-p", "--port", type=int, default=4403, help="TCP port")
    parser.add_argument("-a", "--address", help="BLE device address")
    parser.add_argument("--log", help="Log file path (JSON format)")

    args = parser.parse_args()

    connection_args = {}
    if args.log:
        connection_args["log_file"] = args.log

    if args.serial:
        connection_args["type"] = "serial"
        connection_args["port"] = args.serial
        connection_args["baudrate"] = args.baudrate
    elif args.target:
        connection_args["type"] = "tcp"
        connection_args["host"] = args.target
        connection_args["port"] = args.port
    elif args.address:
        connection_args["type"] = "ble"
        connection_args["address"] = args.address
    else:
        # If no explicit connection arg, maybe user wants to scan?
        # For now, require arguments.
        parser.print_help()
        sys.exit(1)

    app = MeshrcApp(connection_args)
    app.run()


if __name__ == "__main__":
    run()
