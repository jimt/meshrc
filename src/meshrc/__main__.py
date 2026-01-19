import argparse
import sys
import sqlite3
import os

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
    parser.add_argument("--logdb", help="Log database path (SQLite)")

    args = parser.parse_args()

    connection_args = {}
    if args.log:
        connection_args["log_file"] = args.log
    
    if args.logdb:
        if check_and_init_db(args.logdb):
            connection_args["log_db"] = args.logdb
        else:
             print("Database initialization failed or cancelled.")
             sys.exit(1)

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


def check_and_init_db(path):
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS msgs (
        timestamp INTEGER,
        sender TEXT,
        name TEXT,
        text TEXT,
        type TEXT,
        channel_idx INTEGER,
        pubkey_prefix TEXT,
        raw_json TEXT
    );
    """
    
    # Check if exists
    if not os.path.exists(path):
        print(f"Database at '{path}' does not exist.")
        response = input("Create it? [y/N] ").strip().lower()
        if response != 'y':
            return False
        
        # Create
        try:
            with sqlite3.connect(path) as conn:
                conn.execute(create_table_sql)
            print(f"Created database at '{path}'.")
            return True
        except Exception as e:
            print(f"Error creating database: {e}")
            return False
            
    # Exists, check table
    try:
        with sqlite3.connect(path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='msgs';")
            if not cursor.fetchone():
                print(f"Database exists but missing 'msgs' table.")
                response = input("Create table? [y/N] ").strip().lower()
                if response != 'y':
                     return False
                conn.execute(create_table_sql)
                print("Created 'msgs' table.")
    except Exception as e:
        print(f"Error checking database: {e}")
        return False

    return True

if __name__ == "__main__":
    run()
