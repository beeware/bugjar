'''
This is the main entry point.
'''
from Tkinter import *

from argparse import ArgumentParser

from bugjar.view import MainWindow


def main():
    "Run the main loop of the app."
    parser = ArgumentParser()

    parser.add_argument("--version", help="Display version number and exit", action="store_true")

    options = parser.parse_args()

    # Check the shortcut options
    if options.version:
        import bugjar
        print bugjar.VERSION
        return

    options = parser.parse_args()

    # Set up the root Tk context
    root = Tk()

    # Construct an empty window
    view = MainWindow(root)

    # Run the main loop
    try:
        view.mainloop()
    except KeyboardInterrupt:
        view.on_quit()

if __name__ == "__main__":
    main()
