'''
This is the main entry point for the Bugjar GUI.
'''
from Tkinter import *

import argparse
import os
import subprocess
import time

from bugjar import VERSION
from bugjar.view import MainWindow
from bugjar.connection import Debugger
from bugjar.net import run as net_run


def jar_run(debugger):
    # Set up the root Tk context
    root = Tk()

    # Construct a window debugging the nominated program
    view = MainWindow(root, debugger)

    # Run the main loop
    try:
        view.mainloop()
    except KeyboardInterrupt:
        view.on_quit()


def local():
    "Run a Bugjar session on a local process"
    parser = argparse.ArgumentParser(
        description='Debug a python script with a graphical interface.',
        version=VERSION
    )

    parser.add_argument(
        "-p", "--port",
        metavar='PORT',
        help="Port number to use for debugger communications (default=3742)",
        action="store",
        type=int,
        default=3742,
        dest="port"
    )

    parser.add_argument(
        'filename',
        metavar='script.py',
        help='The script to debug.'
    )
    parser.add_argument(
        'args', nargs=argparse.REMAINDER,
        help='Arguments to pass to the script you are debugging.'
    )

    options = parser.parse_args()

    # Start the program to be debugged
    proc = subprocess.Popen(
        ["bugjar-net", options.filename] + options.args,
        stdin=None,
        stdout=None,
        stderr=None,
        shell=False,
        bufsize=1,
        close_fds='posix' in sys.builtin_module_names
    )
    # Pause, ever so briefly, so that the net can be established.
    time.sleep(0.1)

    # Create a connection to the debugger instance
    debugger = Debugger('localhost', options.port, proc=proc)

    # Run the debugger
    jar_run(debugger)


def jar():
    "Connect a Bugjar GUI to a remote headless session."
    parser = argparse.ArgumentParser(
        description='Connect a Bugjar GUI session to a headless debugger.',
        version=VERSION
    )

    parser.add_argument(
        "-H", "--host",
        metavar='HOSTNAME',
        help="Hostname/IP address where the headless debugger is running (default=localhost)",
        action="store",
        default="localhost",
        dest="hostname")
    parser.add_argument(
        "-p", "--port",
        metavar='PORT',
        help="Port number where where the headless debugger is running (default=3742)",
        action="store",
        type=int,
        default=3742,
        dest="port"
    )

    options = parser.parse_args()

    # Create a connection to the remote debugger instance
    debugger = Debugger(options.hostname, options.port, proc=None)

    # Run the debugger
    jar_run(debugger)


def net():
    "Create a headless Bugjar session."
    parser = argparse.ArgumentParser(
        description='Run a script inside a headless Bugjar session.',
        version=VERSION
    )

    parser.add_argument(
        "-H", "--host",
        metavar='HOSTNAME',
        help="Hostname/IP address where the headless debugger will listen for connections (default=0.0.0.0)",
        action="store",
        default="0.0.0.0",
        dest="hostname")
    parser.add_argument(
        "-p", "--port",
        metavar='PORT',
        help="Port number where the headless debugger will listen for connections (default=3742)",
        action="store",
        type=int,
        default=3742,
        dest="port"
    )
    parser.add_argument(
        'filename',
        metavar='script.py',
        help='The script to debug.'
    )
    parser.add_argument(
        'args', nargs=argparse.REMAINDER,
        help='Arguments to pass to the script you are debugging.'
    )

    options = parser.parse_args()

    # Convert the filename provided on the command line into a canonical form
    filename = os.path.abspath(options.filename)
    filename = os.path.normcase(filename)

    # Run the debugger
    net_run(options.hostname, options.port, filename, *options.args)
