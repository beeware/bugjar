import json
import socket
import time
from threading import Thread


class UnknownBreakpoint(Exception):
    pass


class ConnectionNotBootstrapped(Exception):
    pass


class Breakpoint(object):
    def __init__(self, bpnum, filename, line, enabled=True, temporary=False, funcname=None):
        self.bpnum = bpnum
        self.filename = filename
        self.line = line
        self.enabled = enabled
        self.temporary = temporary
        self.funcname = funcname

    def __unicode__(self):
        return u'%s:%s' % (self.filename, self.line)


def command_buffer(debugger):
    "Buffer input from a socket, yielding complete command packets."
    remainder = ''
    while True:
        new_buffer = debugger.socket.recv(1024)

        if not new_buffer:
            # If recv() returns None, the socket has closed
            break
        else:
            # print "CLIENT NEW BUFFER: %s >%s<" % (len(new_buffer), new_buffer[:50])
            if new_buffer[-1] == debugger.ETX:
                terminator = new_buffer[-1]
                full_buffer = remainder + new_buffer[:-1]
            else:
                terminator = None
                full_buffer = remainder + new_buffer

            messages = full_buffer.split(debugger.ETX)
            if terminator is None:
                remainder = messages.pop()
            else:
                remainder = ''
            for message in messages:
                # print "READ %s bytes" % len(message)
                event, data = json.loads(message)

                if hasattr(debugger, 'on_%s' % event):
                    getattr(debugger, 'on_%s' % event)(**data)
                else:
                    print "Unknown server event:", event

    # print "FINISH PROCESSING CLIENT COMMAND BUFFER"


class Debugger(object):
    "A networked connection to a debugger session"

    ETX = '\x03'

    def __init__(self, host, port, proc=None):
        self.host = host
        self.port = port

        self.proc = proc

        # By default, no view is known.
        # It must be set after
        self.view = None

    def start(self):
        "Start the debugger session"
        connected = False
        while not connected:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((self.host, self.port))
                connected = True
            except socket.error, e:
                print "Waiting for connection...", e
                time.sleep(1.0)

        t = Thread(target=command_buffer, args=(self,))
        t.daemon = True
        t.start()

    def stop(self):
        "Shut down the debugger session"
        if self.proc is not None:
            # If this is a local debugger session, kill the child process.
            self.output('quit')

        self.socket.shutdown(socket.SHUT_WR)

        if self.proc is not None:
            # If this is a local debugger session, wait for
            # the child process to die.
            # print "Waiting for child process to die..."
            self.proc.wait()

    def output(self, event, **data):
        "Send a single command packet to the debugger"
        try:
            # print "OUTPUT %s byte message" % len(json.dumps((event, data)) + Debugger.ETX)
            self.socket.sendall(json.dumps((event, data)) + Debugger.ETX)
        except socket.error, e:
            print "CLIENT ERROR", e
        except AttributeError, e:
            print "No client yet", e

    #################################################################
    # Utilities for retrieving current breakpoints.
    #################################################################

    def breakpoint(self, bp):
        """Retrieve a specific breakpoint object.

        Accepts either a breakpoint number, or a (filename, line) tuple
        """
        try:
            if isinstance(bp, tuple):
                filename, line = bp
                return self.bp_index[filename][line]
            else:
                return self.bp_list[bp]
        except AttributeError:
            raise ConnectionNotBootstrapped()
        except KeyError:
            raise UnknownBreakpoint()

    def breakpoints(self, filename):
        try:
            return self.bp_index.get(filename, {})
        except AttributeError:
            raise ConnectionNotBootstrapped()

    #################################################################
    # Commands that can be passed to the debugger
    #################################################################

    def create_breakpoint(self, filename, line, temporary=False):
        "Create a new, enabled breakpoint at the specified line of the given file"
        self.output('break', filename=filename, line=line, temporary=temporary)

    def enable_breakpoint(self, breakpoint):
        "Enable an existing breakpoint"
        self.output('enable', bpnum=breakpoint.bpnum)

    def disable_breakpoint(self, breakpoint):
        "Disable an existing breakpoint"
        self.output('disable', bpnum=breakpoint.bpnum)

    def ignore_breakpoint(self, breakpoint, count):
        """Ignore an existing breakpoint for `count` iterations

        Use a count of 0 to restore the breakpoint.
        """
        self.output('ignore', bpnum=breakpoint.bpnum, count=count)

    def clear_breakpoint(self, breakpoint):
        "Clear an existing breakpoint"
        self.output('clear', bpnum=breakpoint.bpnum)

    def do_run(self):
        "Set the debugger running until the next breakpoint"
        self.output('continue')

    def do_step(self):
        "Step through one stack frame"
        self.output('step')

    def do_next(self):
        "Go to the next line in the current stack frame"
        self.output('next')

    def do_return(self):
        "Return to the previous stack frame"
        self.output('return')

    #################################################################
    # Handlers for events raised by the debugger
    #################################################################

    def on_bootstrap(self, breakpoints):
        self.bp_index = {}
        self.bp_list = [None]
        for bp_data in breakpoints:
            self.on_breakpoint_create(**bp_data)

    def on_breakpoint_create(self, **bp_data):
        bp = Breakpoint(**bp_data)
        self.bp_index.setdefault(bp.filename, {}).setdefault(bp.line, bp)
        self.bp_list.append(bp)
        if bp.enabled:
            self.view.on_breakpoint_enable(bp=bp)
        else:
            self.view.on_breakpoint_disable(bp=bp)

    def on_breakpoint_enable(self, bpnum):
        bp = self.bp_list[bpnum]
        bp.enabled = True
        self.view.on_breakpoint_enable(bp=bp)

    def on_breakpoint_disable(self, bpnum):
        bp = self.bp_list[bpnum]
        bp.enabled = False
        self.view.on_breakpoint_disable(bp=bp)

    def on_breakpoint_ignore(self, bpnum, count):
        bp = self.bp_list[bpnum]
        bp.ignore = count
        self.view.on_breakpoint_ignore(bp=bp, count=count)

    def on_breakpoint_clear(self, bpnum):
        bp = self.bp_list[bpnum]
        self.view.on_breakpoint_clear(bp=bp)

    def on_stack(self, stack):
        self.stack = stack
        self.view.on_stack(stack=stack)

    def on_restart(self):
        self.view.on_restart()

    def on_call(self, args):
        self.view.on_call(args)

    def on_return(self, retval):
        self.view.on_return(retval)

    def on_line(self, filename, line):
        self.view.on_line(filename, line)

    def on_exception(self, name, value):
        self.view.on_exception(name=name, value=value)

    def on_postmortem(self):
        self.view.on_postmortem()

    def on_info(self, message):
        self.view.on_info(message=message)

    def on_warning(self, message):
        self.view.on_warning(message=message)

    def on_error(self, message):
        self.view.on_error(message=message)
