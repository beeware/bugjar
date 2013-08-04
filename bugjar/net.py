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

import argparse
import bdb
import linecache
import json
import os
import re
import socket
import sys
import traceback


class Restart(Exception):
    """Causes a debugger to be restarted for the debugged python program."""
    pass


__all__ = ["Debugger"]


def find_function(funcname, filename):
    cre = re.compile(r'def\s+%s\s*[(]' % re.escape(funcname))
    try:
        fp = open(filename)
    except IOError:
        return None
    # consumer of this info expects the first line to be 1
    lineno = 1
    answer = None
    while 1:
        line = fp.readline()
        if line == '':
            break
        if cre.match(line):
            answer = funcname, filename, lineno
            break
        lineno = lineno + 1
    fp.close()
    return answer


class Debugger(bdb.Bdb):
    NOT_STARTED = 0
    STARTING = 1
    STARTED = 2

    ETX = '\x03'
    EOT = '\x04'
    EOH = '\x05'

    def __init__(self, socket, host, port, skip=None):
        bdb.Bdb.__init__(self, skip=skip)

        self._run_state = Debugger.NOT_STARTED
        self.mainpyfile = ''
        self.socket = socket
        self.host = host
        self.port = port
        self.client = None

    def output(self, msg_type, **data):
        try:
            msg = {
                'type': msg_type
            }
            msg.update(data)
            print "OUTPUT %s byte message" % len(json.dumps(msg) + Debugger.EOH)
            self.client.sendall(json.dumps(msg) + Debugger.EOH)
        except socket.error:
            print "CLIENT ERROR"
        except AttributeError:
            print "No client yet"

    def reset(self):
        bdb.Bdb.reset(self)
        self.forget()

    def forget(self):
        self.lineno = None
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
        while 1:
            try:
                print "Update initial client state..."
                self.print_stack_entry(self.stack[self.curindex])

                print "Tell client we're ready for input..."
                # Send ETX to indicate the end of output that
                # the server will provide, prompting the client
                # for input.
                self.client.sendall(Debugger.ETX)
                print "Wait for input..."
                data = self.client.recv(4096)
                args = data.split(' ', 1)
                print "args:", args

                if hasattr(self, 'do_%s' % args[0]):
                    resume = getattr(self, 'do_%s' % args[0])(args[1:])
                    if resume:
                        print "resume running"
                        break
                    else:
                        print "wait for more commands"
                else:
                    self.output('error', message='Unknown command.')

            except (socket.error, AttributeError):
                # Problem with connection; look for new client
                print "Listening on %s:%s for a controller client" % (self.host, self.port)
                client, addr = self.socket.accept()

                print "Got connection from", client.getpeername()
                self.client = client

        self.forget()

    # Debugger Commands

    def do_break(self, arg, temporary=False):
        # break [ ([filename:]lineno | function) [, "condition"] ]
        if not arg:
            if self.breaks:  # There's at least one
                # self.output("Num Type         Disp Enb   Where")
                for bp in bdb.Breakpoint.bpbynumber:
                    if bp:
                        bp.bpprint(sys.stdout)
            return
        # parse arguments; comma has lowest precedence
        # and cannot occur in filename
        filename = None
        lineno = None
        cond = None
        comma = arg.find(',')
        if comma > 0:
            # parse stuff after comma: "condition"
            cond = arg[comma+1:].lstrip()
            arg = arg[:comma].rstrip()
        # parse stuff before comma: [filename:]lineno | function
        colon = arg.rfind(':')
        funcname = None
        if colon >= 0:
            filename = arg[:colon].rstrip()
            f = self.lookupmodule(filename)
            if not f:
                self.output('error', message="%s not found on sys.path" % repr(filename))
                return
            else:
                filename = f
            arg = arg[colon+1:].lstrip()
            try:
                lineno = int(arg)
            except ValueError:
                self.output('error', message='Bad lineno: %s' % arg)
                return
        else:
            # no colon; can be lineno or function
            try:
                lineno = int(arg)
            except ValueError:
                try:
                    func = eval(arg, self.curframe.f_globals, self.curframe_locals)
                except:
                    func = arg
                try:
                    if hasattr(func, 'im_func'):
                        func = func.im_func
                    code = func.func_code
                    #use co_name to identify the bkpt (function names
                    #could be aliased, but co_name is invariant)
                    funcname = code.co_name
                    lineno = code.co_firstlineno
                    filename = code.co_filename
                except:
                    # last thing to try
                    (ok, filename, ln) = self.lineinfo(arg)
                    if not ok:
                        self.output('error', message='The object %s is not a function or was not found along sys.path.' % repr(arg))
                        return
                    funcname = ok  # ok contains a function name
                    lineno = int(ln)
        if not filename:
            filename = self.curframe.f_code.co_filename
        # Check for reasonable breakpoint
        line = self.checkline(filename, lineno)
        if line:
            # now set the break point
            err = self.set_break(filename, line, temporary, cond, funcname)
            if err:
                self.output('error', message=err)
            else:
                bp = self.get_breaks(filename, line)[-1]
                self.output('breakpoint', number=bp.number, file=bp.file, line=bp.line)

    def do_tbreak(self, arg):
        self.do_break(arg, temporary=True)

    def lineinfo(self, identifier):
        failed = (None, None, None)
        # Input is identifier, may be in single quotes
        idstring = identifier.split("'")
        if len(idstring) == 1:
            # not in single quotes
            id = idstring[0].strip()
        elif len(idstring) == 3:
            # quoted
            id = idstring[1].strip()
        else:
            return failed
        if id == '':
            return failed
        parts = id.split('.')
        # Protection for derived debuggers
        if parts[0] == 'self':
            del parts[0]
            if len(parts) == 0:
                return failed
        # Best first guess at file to look at
        fname = self.curframe.f_code.co_filename
        if len(parts) == 1:
            item = parts[0]
        else:
            # More than one part.
            # First is module, second is method/class
            f = self.lookupmodule(parts[0])
            if f:
                fname = f
            item = parts[1]
        answer = find_function(item, fname)
        return answer or failed

    def checkline(self, filename, lineno):
        """Check whether specified line seems to be executable.

        Return `lineno` if it is, 0 if not (e.g. a docstring, comment, blank
        line or EOF). Warning: testing is not comprehensive.
        """
        # this method should be callable before starting debugging, so default
        # to "no globals" if there is no current frame
        globs = self.curframe.f_globals if hasattr(self, 'curframe') else None
        line = linecache.getline(filename, lineno, globs)
        if not line:
            self.output('error', message='End of file')
            return 0
        line = line.strip()
        # Don't allow setting breakpoint at a blank line
        if (not line or (line[0] == '#') or (line[:3] == '"""') or line[:3] == "'''"):
            self.output('error', message='Blank or comment')
            return 0
        return lineno

    def do_enable(self, arg):
        args = arg.split()
        for i in args:
            try:
                i = int(i)
            except ValueError:
                self.output('error', message='Breakpoint index %r is not a number' % i)
                continue

            if not (0 <= i < len(bdb.Breakpoint.bpbynumber)):
                self.output('error', message='No breakpoint numbered %s' % i)
                continue

            bp = bdb.Breakpoint.bpbynumber[i]
            if bp:
                bp.enable()

    def do_disable(self, arg):
        args = arg.split()
        for i in args:
            try:
                i = int(i)
            except ValueError:
                self.output('error', message='Breakpoint index %r is not a number' % i)
                continue

            if not (0 <= i < len(bdb.Breakpoint.bpbynumber)):
                self.output('error', message='No breakpoint numbered %s' % i)
                continue

            bp = bdb.Breakpoint.bpbynumber[i]
            if bp:
                bp.disable()

    def do_condition(self, arg):
        # arg is breakpoint number and condition
        args = arg.split(' ', 1)
        try:
            bpnum = int(args[0].strip())
        except ValueError:
            # something went wrong
            self.output('error', message='Breakpoint index %r is not a number' % args[0])
            return
        try:
            cond = args[1]
        except:
            cond = None
        try:
            bp = bdb.Breakpoint.bpbynumber[bpnum]
        except IndexError:
            self.output('error', message='Breakpoint index %r is not valid' % args[0])
            return
        if bp:
            bp.cond = cond
            if not cond:
                self.output('msg', message='Breakpoint %s is now unconditional' % bpnum)

    def do_ignore(self, arg):
        """arg is bp number followed by ignore count."""
        args = arg.split()
        try:
            bpnum = int(args[0].strip())
        except ValueError:
            # something went wrong
            self.output('error', message='Breakpoint index %r is not a number' % args[0])
            return
        try:
            count = int(args[1].strip())
        except:
            count = 0
        try:
            bp = bdb.Breakpoint.bpbynumber[bpnum]
        except IndexError:
            self.output('error', message='Breakpoint index %r is not valid' % args[0])
            return
        if bp:
            bp.ignore = count
            if count > 0:
                reply = 'Will ignore next '
                if count > 1:
                    reply = reply + '%d crossings' % count
                else:
                    reply = reply + '1 crossing'
                self.output('msg', message='%s crossing of breakpoint %d' % (reply, bpnum))
            else:
                self.output('msg', message='Will stop the next time breakpoint %s is reached.' % bpnum)

    def do_clear(self, arg):
        """Three possibilities, tried in this order:
        clear -> clear all breaks, ask for confirmation
        clear file:lineno -> clear all breaks at file:lineno
        clear bpno bpno ... -> clear breakpoints by number"""
        if not arg:
            try:
                reply = raw_input('Clear all breaks? ')
            except EOFError:
                reply = 'no'
            reply = reply.strip().lower()
            if reply in ('y', 'yes'):
                self.clear_all_breaks()
            return
        if ':' in arg:
            # Make sure it works for "clear C:\foo\bar.py:12"
            i = arg.rfind(':')
            filename = arg[:i]
            arg = arg[i+1:]
            try:
                lineno = int(arg)
            except ValueError:
                err = "Invalid line number (%s)" % arg
            else:
                err = self.clear_break(filename, lineno)
            if err:
                self.output('error', message=err)
            return
        numberlist = arg.split()
        for i in numberlist:
            try:
                i = int(i)
            except ValueError:
                self.output('error', message='Breakpoint index %r is not a number' % i)
                continue

            if not (0 <= i < len(bdb.Breakpoint.bpbynumber)):
                self.output('error', message='No breakpoint numbered %s' % i)
                continue
            err = self.clear_bpbynumber(i)
            if err:
                self.output('error', message=err)
            else:
                self.output('message', message='Deleted breakpoint %s' % i)

    def do_up(self, arg):
        if self.curindex == 0:
            self.output('message', message='Oldest frame')
        else:
            self.curindex = self.curindex - 1
            self.curframe = self.stack[self.curindex][0]
            self.curframe_locals = self.curframe.f_locals
            self.print_stack_entry(self.stack[self.curindex])
            self.lineno = None

    def do_down(self, arg):
        if self.curindex + 1 == len(self.stack):
            self.output('message', message='Newest frame')
        else:
            self.curindex = self.curindex + 1
            self.curframe = self.stack[self.curindex][0]
            self.curframe_locals = self.curframe.f_locals
            self.print_stack_entry(self.stack[self.curindex])
            self.lineno = None

    def do_until(self, arg):
        self.set_until(self.curframe)
        return 1

    def do_step(self, arg):
        self.set_step()
        return 1
    do_s = do_step

    def do_next(self, arg):
        self.set_next(self.curframe)
        return 1
    do_n = do_next

    def do_run(self, arg):
        """Restart program by raising an exception to be caught in the main
        debugger loop.  If arguments were given, set them in sys.argv."""
        if arg:
            import shlex
            argv0 = sys.argv[0:1]
            sys.argv = shlex.split(arg)
            sys.argv[:0] = argv0
        raise Restart

    def do_return(self, arg):
        self.set_return(self.curframe)
        return 1
    do_r = do_return

    def do_continue(self, arg):
        self.set_continue()
        return 1
    do_cont = do_continue
    do_c = do_continue

    def do_jump(self, arg):
        if self.curindex + 1 != len(self.stack):
            self.output('error', message='You can only jump within the bottom frame')
            return
        try:
            arg = int(arg)
        except ValueError:
            self.output('error', message="The 'jump' command requires a line number")
        else:
            try:
                # Do the jump, fix up our copy of the stack, and display the
                # new position
                self.curframe.f_lineno = arg
                self.stack[self.curindex] = self.stack[self.curindex][0], arg
                self.print_stack_entry(self.stack[self.curindex])
            except ValueError, e:
                self.output('error', message="Jump failed: %s" % e)

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

    def do_quit(self, arg):
        self._user_requested_quit = True
        self.set_quit()
        # Send EOT to terminate debug session
        self.client.sendall(Debugger.EOT)
        return 1

    def do_args(self, arg):
        co = self.curframe.f_code
        locals = self.curframe_locals
        n = co.co_argcount
        if co.co_flags & 4:
            n = n + 1
        if co.co_flags & 8:
            n = n + 1
        for i in range(n):
            name = co.co_varnames[i]
            self.output('arg', name=locals.get(name, '*** undefined ***'))

    def do_retval(self, arg):
        if '__return__' in self.curframe_locals:
            self.output('retval', value=self.curframe_locals['__return__'])
        else:
            self.output('error', message='Not yet returned!')

    def _getval(self, arg):
        try:
            return eval(arg, self.curframe.f_globals,
                        self.curframe_locals)
        except:
            t, v = sys.exc_info()[:2]
            if isinstance(t, str):
                exc_type_name = t
            else:
                exc_type_name = t.__name__
            # self.output({'***', exc_type_name + ':', repr(v))
            raise

    # def do_print(self, arg):
    #     try:
    #         self.output(repr(self._getval(arg)))
    #     except:
    #         pass
    # do_p = do_print

    # Print a traceback starting at the top stack frame.
    # The most recently entered frame is printed last;
    # this is different from dbx and gdb, but consistent with
    # the Python interpreter's stack trace.
    # It is also consistent with the up/down commands (which are
    # compatible with dbx and gdb: up moves towards 'main()'
    # and down moves towards the most recent stack frame).

    def print_stack_trace(self):
        try:
            for frame_lineno in self.stack:
                self.print_stack_entry(frame_lineno)
        except KeyboardInterrupt:
            pass

    def print_stack_entry(self, frame_lineno, prompt_prefix='>'):
        # frame, lineno = frame_lineno
        # self.output(self.format_stack_entry(frame_lineno, prompt_prefix))

        stack_data = [
            (line_no, {
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
            for frame, line_no in self.stack[2:]
        ]
        self.output('stack', stack=stack_data)

    def lookupmodule(self, filename):
        """Helper function for break/clear parsing -- may be overridden.

        lookupmodule() translates (possibly incomplete) file or module name
        into an absolute file name.
        """
        if os.path.isabs(filename) and os.path.exists(filename):
            return filename
        f = os.path.join(sys.path[0], filename)
        if os.path.exists(f) and self.canonic(f) == self.mainpyfile:
            return f
        root, ext = os.path.splitext(filename)
        if ext == '':
            filename = filename + '.py'
        if os.path.isabs(filename):
            return filename
        for dirname in sys.path:
            while os.path.islink(dirname):
                dirname = os.readlink(dirname)
            fullname = os.path.join(dirname, filename)
            if os.path.exists(fullname):
                return fullname
        return None

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


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--version", help="Display version number and exit", action="store_true")
    parser.add_argument("--host", help="server host", action="store", default="")
    parser.add_argument("-p", "--port", help="Port number", action="store", type=int, default=3742)
    parser.add_argument('mainpyfile')
    parser.add_argument('args', nargs=argparse.REMAINDER)

    options = parser.parse_args()

    # Check the shortcut options
    if options.version:
        import bugjar
        print bugjar.VERSION
        return

    # Hide "debugger.py" from argument list
    sys.argv[0] = options.mainpyfile
    sys.argv[1:] = options.args

    # Replace debugger's dir with script's dir in front of module search path.
    sys.path[0] = os.path.dirname(options.mainpyfile)

    # Create a socket and listen on it for a client debugger
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    s.bind((options.host, options.port))
    s.listen(1)

    debugger = Debugger(s, options.host, options.port)

    while True:
        try:
            print 'Start the script'
            debugger._runscript(options.mainpyfile)

            if debugger._user_requested_quit:
                print 'user requested exit'
                break

            debugger.output('restart')
        except Restart:
            print "Restarting", options.mainpyfile, "with arguments:"
            print "\t" + " ".join(sys.argv[1:])
        except KeyboardInterrupt:
            debugger.client = None
            break
        except SystemExit:
            debugger.client = None
            break
        except socket.error:
            print "Controller client disappeared; can't recover"
            debugger.client = None
            break
        except:
            traceback.print_exc()
            print "Uncaught exception. Entering post mortem debugging"
            print "Running 'cont' or 'step' will restart the program"
            t = sys.exc_info()[2]
            debugger.interaction(None, t)
            print "Post mortem debugger finished. The " + options.mainpyfile + \
                  " will be restarted"
            break

    if debugger.client:
        print "lost connection... closing"
        debugger.client.shutdown(socket.SHUT_WR)

if __name__ == '__main__':
    from bugjar import net
    net.main()
