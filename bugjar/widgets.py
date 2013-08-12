from idlelib.WidgetRedirector import WidgetRedirector
from Tkinter import *
from ttk import *

from pygments import lex
from pygments.lexers import PythonLexer
from pygments.styles import get_style_by_name
from pygments.token import Token


def tk_break(*args, **kwargs):
    "Return a Tk 'break' event result."
    return "break"


def text_set(widget):
    "Create a function for `widget` that will respond to scroll events"
    def set_fn(start, end):
        widget.yview('moveto', start)
    return set_fn


def combine(*functions):
    """Combine multiple event handlers into a single combined handler.

    The return value for the last function provided will be returned as
    the return value for the full list.
    """
    def _combined(*args, **kwargs):
        for fn in functions:
            retval = fn(*args, **kwargs)
        return retval
    return _combined


class ReadOnlyText(Text):
    """A Text widget that redirects the insert and delete
    handlers so that they are no-ops. This effectively makes
    the widget readonly with respect
    to keyboard input handlers.

    Adapted from http://tkinter.unpythonic.net/wiki/ReadOnlyText, which
    is itself adapting a solution described here: http://wiki.tcl.tk/1152
    """
    def __init__(self, *args, **kwargs):
        Text.__init__(self, *args, **kwargs)

        self.redirector = WidgetRedirector(self)
        self.insert = self.redirector.register("insert", tk_break)
        self.delete = self.redirector.register("delete", tk_break)


class ReadOnlyCode(Frame):
    """A widget for displaying read-only, syntax highlighted code.

    """
    def __init__(self, *args, **kwargs):
        Frame.__init__(self, *args, **kwargs)

        # What is currently being displayed
        self.current_file = None
        self.current_line = None

        # Get the code style
        self.style = get_style_by_name('monokai')

        # The Text widget holding the line numbers.
        self.lines = Text(self,
            width=5,
            padx=4,
            highlightthickness=0,
            takefocus=0,
            bd=0,
            background='lightgrey',
            foreground='black',
            cursor='arrow',
            state=DISABLED
        )
        self.lines.grid(column=0, row=0, sticky=(N, S))

        # The Main Text Widget
        self.code = ReadOnlyText(self,
            width=80,
            height=25,
            wrap=NONE,
            background=self.style.background_color,
            highlightthickness=0,
            bd=0,
            padx=4,
            cursor='arrow',
        )
        self.code.grid(column=1, row=0, sticky=(N, S, E, W))

        # Set up styles for the code window
        for token in self.style.styles:
            self.code.tag_configure(str(token), **self._tag_style(token))

        self.code.tag_configure("current_line", background=self.style.highlight_color)

        # Set up event handlers:
        # - Double clicking on a variable
        self.code.tag_bind(str(Token.Name), '<Double-1>', self._on_code_variable_double_click)

        # - Double clicking on a line number
        self.lines.bind('<Double-1>', self._on_line_double_click)

        # The widgets vertical scrollbar
        self.vScrollbar = Scrollbar(self, orient=VERTICAL)
        self.vScrollbar.grid(column=2, row=0, sticky=(N, S))

        # Tie the scrollbar to the text views, and the text views
        # to each other.
        self.code.config(yscrollcommand=combine(text_set(self.lines), self.vScrollbar.set))
        self.lines.config(yscrollcommand=combine(text_set(self.code), self.vScrollbar.set))
        self.vScrollbar.config(command=combine(self.lines.yview, self.code.yview))

        # Configure the weights for the grid.
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=0)
        self.rowconfigure(0, weight=1)

    def _tag_style(self, token):
        "Convert a heirarchical style definition into a Tk style string"
        if token.parent is not None:
            kwargs = self._tag_style(token.parent)
        else:
            kwargs = {}
        for part in self.style.styles[token].split():
            if part.startswith('#'):
                kwargs['foreground'] = part
            # elif part == 'bold':
            #     kwargs['font'] = part
            elif part.startswith('bg:'):
                kwargs['background'] = part[3:]
        return kwargs

    def show(self, filename, line=None, refresh=False):
        """Show a specific line of a specific file.

        If line is None, no current line will be highlighted
        If refresh is True, the file will be reloaded regardless

        Returns true if a file refresh was performed.
        """
        # If the file has changed, or a refresh has been requested,
        # reload the file.
        if refresh or self.current_file != filename:
            file_change = True
            self.code.delete('1.0', END)
            with open(filename) as code:
                for token, content in lex(code.read(), PythonLexer()):
                    self.code.insert(END, content, str(token))

            # Now update the text for the linenumbers
            end_index = self.code.index(END)
            line_count = int(end_index.split('.')[0])
            lineNumbers = '\n'.join('%5d' % i for i in range(1, line_count))
            self.lines.config(state=NORMAL)
            self.lines.delete('1.0', END)
            self.lines.insert('1.0', lineNumbers)
            self.lines.config(state=DISABLED)

            # Store the new filename, and clear any current line
            self.current_file = filename
            self.current_line = None
        else:
           file_change = False

        if self.current_line:
            self.code.tag_remove('current_line',
                '%s.0' % self.current_line,
                '%s.0' % (self.current_line + 1)
            )

        self.current_line = line
        if self.current_line:
            self.code.see('%s.0' % self.current_line)
            self.code.tag_add('current_line',
                '%s.0' % self.current_line,
                '%s.0' % (self.current_line + 1)
            )
        else:
            # Reset the view
            self.code.see('1.0')

        return file_change

    def _on_line_double_click(self, event):
        """Internal event handler when a double click event is registered in the lines area.

        Converted into an event on a specific line for public API purposes.
        """
        line = int(self.code.index("@%s,%s" % (event.x, event.y)).split('.')[0])
        self.on_line_double_click(line)

    def on_line_double_click(self, line):
        "Respose when a "
        pass

    def _on_code_variable_double_click(self, event):
        "Response when a double click event is registered on a variable."
        range = self.code.tag_nextrange(str(Token.Name), "@%s,%s wordstart" % (event.x, event.y))
        self.on_code_variable_double_click(self.code.get(range[0], range[1]))

    def on_code_variable_double_click(self, var):
        pass
