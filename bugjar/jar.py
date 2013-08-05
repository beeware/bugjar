'''
This is the main entry point for the Bugjar GUI.
'''
from Tkinter import *

import argparse
import subprocess

from bugjar.view import MainWindow
from bugjar.connection import Debugger


def run(debugger):
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
    "Run a debugger session on a local process"
    parser = argparse.ArgumentParser(description='Debug a python script using a GUI.')
    parser.add_argument("--version", help="Display version number and exit", action="store_true")
    parser.add_argument('mainpyfile', metavar='script.py', help='The script to debug')
    parser.add_argument('args', nargs=argparse.REMAINDER, help='Arguments to pass to the script you are debugging')

    options = parser.parse_args()

    # Check the shortcut options
    if options.version:
        import bugjar
        print bugjar.VERSION
        return

    # Start the program to be debugged
    proc = subprocess.Popen(
        ["python", "-m", "bugjar.net", options.mainpyfile] + options.args,
        stdin=None,
        stdout=None,
        stderr=None,
        shell=False,
        bufsize=1,
        close_fds='posix' in sys.builtin_module_names
    )

    # Create a connection to the debugger instance
    debugger = Debugger('localhost', 3742, proc=proc)

    # Run the debugger
    run(debugger)


def remote():
    "Run a debugger session on a remote process"
    parser = argparse.ArgumentParser(description='Debug a python script using a GUI.')
    parser.add_argument("--version", help="Display version number and exit", action="store_true")

    parser.add_argument("--host", help="Debugger hostname (default=localhost)", action="store", default="localhost")
    parser.add_argument("-p", "--port", help="Debugger port number (default=3742)", action="store", type=int, default=3742)

    options = parser.parse_args()

    # Check the shortcut options
    if options.version:
        import bugjar
        print bugjar.VERSION
        return

    # Create a connection to the remote debugger instance
    debugger = Debugger(options.host, options.port, proc=None)

    # Run the debugger
    run(debugger)

if __name__ == "__main__":
    local()
