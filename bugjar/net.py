#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""A Python debugger that takes commands via a socket.

This code is substantially derived from the code for PDB,
the builtin debugger. The code was copied from the source
code for Python 2.7.5.

The original PDB code is:
    Copyright © 2001-2013 Python Software Foundation; All Rights Reserved

License terms for the original PDB code can be found here:
    http://docs.python.org/2/license.html
"""

import bdb
import linecache
import json
import os
import re
import socket
import sys
from threading import Thread
import traceback

try:
    from Queue import Queue
except ImportError:
    from queue import Queue  # python 3.x


class Restart(Exception):
    """Causes a debugger to be restarted for the debugged python program."""
    pass


class ClientClose(Exception):
    """Causes a debugger to wait for a new debugger client to connect."""
    pass


__all__ = ["Debugger"]


def find_function(funcname, filename):
    cre = re.compile(r'def\s+%s\s*[(]' % re.escape(funcname))
    try:
        fp = open(filename)
    except IOError:
        return None
    # consumer of this info expects the first line to be 1
    line = 1
    answer = None
    while 1:
        line = fp.readline()
        if line == '':
            break
        if cre.match(line):
            answer = funcname, filename, line
            break
        line = line + 1
    fp.close()
    return answer


def command_buffer(debugger):
    "Buffer input from a socket, yielding complete command packets."
    remainder = ''
    while True:
        new_buffer = debugger.client.recv(1024)

        if not new_buffer:
            # If recv() returns None, the socket has closed
            break
        else:
            # print "SERVER NEW BUFFER: %s >%s<" % (len(new_buffer), new_buffer[:50])
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
                command, args = json.loads(message)
                try:
                    debugger.commands.put(json.loads(message))
                except ValueError:
                    print "Invalid command: %s" % message

    # print "FINISH PROCESSING SERVER COMMAND BUFFER"
    debugger.commands.put(('close', {}))


class Debugger(bdb.Bdb):
    NOT_STARTED = 0
    STARTING = 1
    STARTED = 2

    ETX = '\x03'

    def __init__(self, socket, host, port, skip=None):
        bdb.Bdb.__init__(self, skip=skip)

        self._run_state = Debugger.NOT_STARTED
        self.mainpyfile = ''
        self.socket = socket
        self.host = host
        self.port = port
        self.client = None
        self.command_thread = None
        self.commands = None

    def output(self, event, **data):
        try:
            # print "OUTPUT %s byte %s message" % (len(json.dumps((event, data)) + Debugger.ETX), event)
            # print json.dumps((event, data))
            self.client.sendall(json.dumps((event, data)) + Debugger.ETX)
        except socket.error, e:
            pass
            # print "CLIENT ERROR", e
        except AttributeError:
            pass
            # print "No client yet"

    def output_stack(self):
        "Output the current stack"
        # If this is a normal operational stack frame,
        # the top two frames are BDB and the Bugjar frame
        # that is executing the program.
        # If this is an exception, there are 2 extra frames
        # from the Bugjar net.
        # All these frames can be ignored.
        if self.stack[1][0].f_code.co_filename == '<string>':
            str_index = 2
        elif self.stack[3][0].f_code.co_filename == '<string>':
            str_index = 4

        stack_data = [
            (
                line_no,
                {
                    'filename': frame.f_code.co_filename,
                    'locals': dict((k, repr(v)) for k, v in frame.f_locals.items()),
                    'globals': dict((k, repr(v)) for k, v in frame.f_globals.items()),
                    'builtins': dict((k, repr(v)) for k, v in frame.f_builtins.items()),
                    'restricted': frame.f_restricted,
                    'lasti': repr(frame.f_lasti),
                    'exc_type': repr(frame.f_exc_type),
                    'exc_value': repr(frame.f_exc_value),
                    'exc_traceback': repr(frame.f_exc_traceback),
                    'current': frame is self.curframe,
                }
            )
            for frame, line_no in self.stack[str_index:]
        ]
        self.output('stack', stack=stack_data)

    def forget(self):
        self.line = None
        self.stack = []
        self.curindex = 0
        self.curframe = None

    def setup(self, f, t):
        self.forget()
        self.stack, self.curindex = self.get_stack(f, t)
        self.curframe = self.stack[self.curindex][0]
        # The f_locals dictionary is updated from the actual frame
        # locals whenever the .f_locals accessor is called, so we
        # cache it here to ensure that modifications are not overwritten.
        self.curframe_locals = self.curframe.f_locals

    # Override Bdb methods

    def user_call(self, frame, argument_list):
        """This method is called when there is the remote possibility
        that we ever need to stop in this function."""
        if self._run_state == Debugger.STARTING:
            return
        if self.stop_here(frame):
            self.output('call', args=argument_list)
            self.interaction(frame, None)

    def user_line(self, frame):
        """This function is called when we stop or break at this line."""
        if self._run_state == Debugger.STARTING:
            if (self.mainpyfile != self.canonic(frame.f_code.co_filename) or frame.f_lineno <= 0):
                return
            self._run_state = Debugger.STARTED
        self.output('line', filename=self.canonic(frame.f_code.co_filename), line=frame.f_lineno)
        self.interaction(frame, None)

    def user_return(self, frame, return_value):
        """This function is called when a return trap is set here."""
        if self._run_state == Debugger.STARTING:
            return
        frame.f_locals['__return__'] = return_value
        self.output('return', retval=return_value)
        self.interaction(frame, None)

    def user_exception(self, frame, exc_info):
        """This function is called if an exception occurs,
        but only if we are to stop at or just below this level."""
        if self._run_state == Debugger.STARTING:
            return
        exc_type, exc_value, exc_traceback = exc_info
        frame.f_locals['__exception__'] = exc_type, exc_value
        if isinstance(exc_type, basestring):
            exc_type_name = exc_type
        else:
            exc_type_name = exc_type.__name__
        self.output('exception', name=exc_type_name, value=repr(exc_value))
        self.interaction(frame, exc_traceback)

    # General interaction function

    def interaction(self, frame, tb):
        self.setup(frame, tb)
        self.output_stack()
        while 1:
            try:
                # print "Server Wait for input..."
                command, args = self.commands.get(block=True)

                # print "Server command:", command, args
                if hasattr(self, 'do_%s' % command):
                    try:
                        resume = getattr(self, 'do_%s' % command)(**args)
                        if resume:
                            # print "resume running"
                            break
                    except (ClientClose, Restart):
                        # Reraise any control exceptions
                        raise
                    except Exception, e:
                        # print "Unknown problem with command %s: %s" % (command, e)
                        self.output('error', message='Unknown problem with command %s: %s' % (command, e))
                else:
                    # print "Unknown command %s" % command
                    self.output('error', message='Unknown command: %s' % command)

            except (socket.error, AttributeError, ClientClose):
                # Problem with connection; look for new client
                print "Listening on %s:%s for a bugjar client" % (self.host, self.port)
                client, addr = self.socket.accept()

                print "Got connection from", client.getpeername()
                self.client = client

                # Start the command queue
                self.commands = Queue()
                self.command_thread = Thread(target=command_buffer, args=(self,))
                self.command_thread.daemon = True
                self.command_thread.start()

                # print "Bootstrap the state of a new connection..."
                self.output(
                    'bootstrap',
                    breakpoints=[
                        {
                            'bpnum': bp.number,
                            'filename': bp.file,
                            'line': bp.line,
                            'temporary': bp.temporary,
                            'enabled': bp.enabled,
                            'funcname': bp.funcname
                        }
                        for bp in bdb.Breakpoint.bpbynumber[1:]
                    ]
                )

                # print "Describe initial stack..."
                self.output_stack()

        # print "END INTERACTION LOOP"
        self.forget()

    # Debugger Commands

    def do_break(self, filename, line, temporary=False):
        # Check for reasonable breakpoint
        if self.is_executable_line(filename, line):
            # now set the break point
            err = self.set_break(filename, line, temporary, None, None)
            if err:
                self.output('error', message=err)
            else:
                bp = self.get_breaks(filename, line)[-1]
                self.output(
                    'breakpoint_create',
                    bpnum=bp.number,
                    filename=bp.file,
                    line=bp.line,
                    temporary=bp.temporary,
                    funcname=bp.funcname
                )
        else:
            self.output('error', message="%s:%s is not executable" % (filename, line))

    def is_executable_line(self, filename, line):
        """Check whether specified line is executable.

        Return True if it is, False if not (e.g. a docstring, comment, blank
        line or EOF).
        """
        # this method should be callable before starting debugging, so default
        # to "no globals" if there is no current frame
        globs = self.curframe.f_globals if hasattr(self, 'curframe') else None
        code = linecache.getline(filename, line, globs)
        if not code:
            return False
        code = code.strip()
        # Don't allow setting breakpoint at a blank line
        if (not code or (code[0] == '#') or (code[:3] == '"""') or code[:3] == "'''"):
            return False
        return True

    def do_enable(self, bpnum):
        if not (0 <= bpnum < len(bdb.Breakpoint.bpbynumber)):
            self.output('error', message='No breakpoint numbered %s' % bpnum)
        else:
            bp = bdb.Breakpoint.bpbynumber[bpnum]
            bp.enable()
            self.output('breakpoint_enable', bpnum=bpnum)

    def do_disable(self, bpnum):
        bpnum = int(bpnum)
        if not (0 <= bpnum < len(bdb.Breakpoint.bpbynumber)):
            self.output('error', message='No breakpoint numbered %s' % bpnum)
        else:
            bp = bdb.Breakpoint.bpbynumber[bpnum]
            bp.disable()
            self.output('breakpoint_disable', bpnum=bpnum)

    # def do_condition(self, arg):
    #     # arg is breakpoint number and condition
    #     args = arg.split(' ', 1)
    #     try:
    #         bpnum = int(args[0].strip())
    #     except ValueError:
    #         # something went wrong
    #         self.output('error', message='Breakpoint index %r is not a number' % args[0])
    #         return
    #     try:
    #         cond = args[1]
    #     except:
    #         cond = None
    #     try:
    #         bp = bdb.Breakpoint.bpbynumber[bpnum]
    #     except IndexError:
    #         self.output('error', message='Breakpoint index %r is not valid' % args[0])
    #         return
    #     if bp:
    #         bp.cond = cond
    #         if not cond:
    #             self.output('msg', message='Breakpoint %s is now unconditional' % bpnum)

    def do_ignore(self, bpnum, count):
        """arg is bp number followed by ignore count."""
        try:
            count = int(count)
        except ValueError:
            count = 0

        if not (0 <= bpnum < len(bdb.Breakpoint.bpbynumber)):
            self.output('error', message='No breakpoint numbered %s' % bpnum)
        else:
            bp = bdb.Breakpoint.bpbynumber[bpnum]
            bp.ignore = count
            if count > 0:
                self.output('breakpoint_ignore', bpnum=bpnum, count=count)
            else:
                self.output('breakpoint_enable', bpnum=bpnum)

    def do_clear(self, bpnum):
        bpnum = int(bpnum)
        if not (0 <= bpnum < len(bdb.Breakpoint.bpbynumber)):
            self.output('error', message='No breakpoint numbered %s' % bpnum)
        else:
            err = self.clear_bpbynumber(bpnum)
            if err:
                self.output('error', message=err)
            else:
                self.output('breakpoint_clear', bpnum=bpnum)

    # def do_up(self, arg):
    #     if self.curindex == 0:
    #         self.output('error', message='Already at oldest frame')
    #     else:
    #         self.curindex = self.curindex - 1
    #         self.curframe = self.stack[self.curindex][0]
    #         self.curframe_locals = self.curframe.f_locals
    #         self.output_stack()
    #         self.lineno = None

    # def do_down(self, arg):
    #     if self.curindex + 1 == len(self.stack):
    #         self.output('error', message='Alread at newest frame')
    #     else:
    #         self.curindex = self.curindex + 1
    #         self.curframe = self.stack[self.curindex][0]
    #         self.curframe_locals = self.curframe.f_locals
    #         self.output_stack()
    #         self.lineno = None

    # def do_until(self, arg):
    #     self.set_until(self.curframe)
    #     return 1

    def do_step(self):
        self.set_step()
        return 1

    def do_next(self):
        self.set_next(self.curframe)
        return 1

    def do_restart(self, **argv):
        """Restart program by raising an exception to be caught in the main
        debugger loop.  If arguments were given, set them in sys.argv."""
        if argv:
            argv0 = sys.argv[0:1]
            sys.argv = argv
            sys.argv[:0] = argv0
        raise Restart

    def do_return(self):
        self.set_return(self.curframe)
        return 1

    def do_continue(self):
        self.set_continue()
        return 1

    # def do_jump(self, arg):
    #     if self.curindex + 1 != len(self.stack):
    #         self.output('error', message='You can only jump within the bottom frame')
    #         return
    #     try:
    #         arg = int(arg)
    #     except ValueError:
    #         self.output('error', message="The 'jump' command requires a line number")
    #     else:
    #         try:
    #             # Do the jump, fix up our copy of the stack, and display the
    #             # new position
    #             self.curframe.f_lineno = arg
    #             self.stack[self.curindex] = self.stack[self.curindex][0], arg
    #             self.output_stack()
    #         except ValueError, e:
    #             self.output('error', message="Jump failed: %s" % e)

    # def do_debug(self, arg):
    #     sys.settrace(None)
    #     globals = self.curframe.f_globals
    #     locals = self.curframe_locals
    #     p = Debugger(...)
    #     p.prompt = "(%s) " % self.prompt.strip()
    #     self.output("ENTERING RECURSIVE DEBUGGER")
    #     sys.call_tracing(p.run, (arg, globals, locals))
    #     self.output("LEAVING RECURSIVE DEBUGGER")
    #     sys.settrace(self.trace_dispatch)
    #     self.lastcmd = p.lastcmd

    def do_quit(self):
        self._user_requested_quit = True
        self.set_quit()
        return 1

    def do_close(self):
        """Respond to a closed socket.

        This isn't actually a user comman,but it's something the command
        queue can generate in response to the socket closing; we handle
        it as a user command for the sake of elegance.
        """
        # print "Close down socket"
        self.client = None
        # print "Wait for command thread"
        self.command_thread.join()
        # print "Thread is dead"
        self.commands = None
        raise ClientClose

    # def do_args(self, arg):
    #     co = self.curframe.f_code
    #     locals = self.curframe_locals
    #     n = co.co_argcount
    #     if co.co_flags & 4:
    #         n = n + 1
    #     if co.co_flags & 8:
    #         n = n + 1
    #     for i in range(n):
    #         name = co.co_varnames[i]
    #         self.output('arg', name=locals.get(name, '*** undefined ***'))

    # def do_retval(self, arg):
    #     if '__return__' in self.curframe_locals:
    #         self.output('retval', value=self.curframe_locals['__return__'])
    #     else:
    #         self.output('error', message='Not yet returned!')

    # def _getval(self, arg):
    #     try:
    #         return eval(arg, self.curframe.f_globals,
    #                     self.curframe_locals)
    #     except:
    #         t, v = sys.exc_info()[:2]
    #         if isinstance(t, str):
    #             exc_type_name = t
    #         else:
    #             exc_type_name = t.__name__
    #         # self.output({'***', exc_type_name + ':', repr(v))
    #         raise

    # def do_print(self, arg):
    #     try:
    #         self.output(repr(self._getval(arg)))
    #     except:
    #         pass
    # do_p = do_print

    def _runscript(self, filename):
        # The script has to run in __main__ namespace (or imports from
        # __main__ will break).
        #
        # So we clear up the __main__ and set several special variables
        # (this gets rid of debugger's globals and cleans old variables on restarts).
        import __main__
        __main__.__dict__.clear()
        __main__.__dict__.update({
            "__name__": "__main__",
            "__file__": filename,
            "__builtins__": __builtins__,
        })

        # When bdb sets tracing, a number of call and line events happens
        # BEFORE debugger even reaches user's code (and the exact sequence of
        # events depends on python version). So we take special measures to
        # avoid stopping before we reach the main script (see user_line and
        # user_call for details).
        self._run_state = Debugger.STARTING
        self.mainpyfile = self.canonic(filename)
        self._user_requested_quit = False
        self.run('execfile(%r)' % filename)


def run(hostname, port, filename, *args):
    # Hide "debugger.py" from argument list
    sys.argv[0] = filename
    sys.argv[1:] = args

    # Replace debugger's dir with script's dir in front of module search path.
    sys.path[0] = os.path.dirname(filename)

    # Create a socket and listen on it for a client debugger
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    s.bind((hostname, port))
    s.listen(1)

    debugger = Debugger(s, hostname, port)

    while True:
        try:
            # print 'Start the script'
            debugger._runscript(filename)

            if debugger._user_requested_quit:
                # print 'user requested exit'
                break

            debugger.output('restart')
        except Restart:
            print "Restarting", filename, "with arguments:"
            print "\t" + " ".join(sys.argv[1:])
        except KeyboardInterrupt:
            print "Keyboard interrupt"
            debugger.client = None
            break
        except SystemExit:
            print "System exit"
            debugger.client = None
            break
        except socket.error:
            print "Controller client disappeared; can't recover"
            debugger.client = None
            break
        except:
            traceback.print_exc()
            debugger.output('postmortem')
            t = sys.exc_info()[2]
            debugger.interaction(None, t)

    if debugger.client:
        # print "closing connection"
        debugger.client.shutdown(socket.SHUT_WR)
