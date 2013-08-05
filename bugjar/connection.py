import json
import socket
import time
from threading import Thread

from bugjar.events import EventSource


ETX = '\x03'


def command_buffer(debugger):
    "Buffer input from a socket, yielding complete command packets."
    remainder = ''
    while True:
        new_buffer = debugger.socket.recv(1024)

        if not new_buffer:
            # If recv() returns None, the socket has closed
            break
        else:
            print "NEW BUFFER: %s >%s<" % (len(new_buffer), new_buffer[:50])
            if new_buffer[-1] == ETX:
                terminator = new_buffer[-1]
                full_buffer = remainder + new_buffer[:-1]
            else:
                terminator = None
                full_buffer = remainder + new_buffer

            messages = full_buffer.split(ETX)
            if terminator is None:
                remainder = messages.pop()
            else:
                remainder = ''
            for message in messages:
                print "READ %s bytes" % len(message)
                event, data = json.loads(message)
                print "EMIT", event
                debugger.emit(event, **data)
    print "FINISH PROCESSING COMMAND BUFFER"


class Debugger(EventSource):
    "A networked connection to a debugger session"

    def __init__(self, host, port, proc=None):
        self.host = host
        self.port = port

        self.proc = proc

    def start(self):
        connected = False
        while not connected:
            try:
                print (self.host, self.port)
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((self.host, self.port))
                connected = True
            except socket.error, e:
                print "no connection", e
                time.sleep(0.1)

        print "GOT CONNECTION"
        t = Thread(target=command_buffer, args=(self,))
        t.daemon = True
        t.start()

    def stop(self):
        "Shut down the debugger session"
        if self.proc is not None:
            # If this is a local debugger session, kill the child process.
            print "Tell child process to quit"
            self.socket.sendall('quit')

        print "Shutdown socket"
        self.socket.shutdown(socket.SHUT_WR)

        if self.proc is not None:
            # If this is a local debugger session, wait for
            # the child process to die.
            print "Waiting for child process to die..."
            self.proc.wait()
            print "Child process is dead"

    def do_run(self):
        "Set the debugger running until the next breakpoint"
        self.socket.sendall('continue')

    def do_step(self):
        "Step through one stack frame"
        self.socket.sendall('step')

    def do_next(self):
        "Go to the next line in the current stack frame"
        self.socket.sendall('next')

    def do_return(self):
        "Return to the previous stack frame"
        self.socket.sendall('return')
