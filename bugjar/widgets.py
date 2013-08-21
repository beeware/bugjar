from ttk import *

from tkreadonly import ReadOnlyCode

from bugjar.connection import ConnectionNotBootstrapped, UnknownBreakpoint


class DebuggerCode(ReadOnlyCode):
    def __init__(self, *args, **kwargs):
        self.debugger = kwargs.pop('debugger')
        ReadOnlyCode.__init__(self, *args, **kwargs)

        # Set up styles for line numbers
        self.lines.tag_configure('enabled', background='red')
        self.lines.tag_configure('disabled', background='gray')
        self.lines.tag_configure('ignored', background='green')
        self.lines.tag_configure('temporary', background='pink')

        self.line_bind('<Double-1>', self.on_line_double_click)
        self.name_bind('<Double-1>', self.on_name_double_click)

    def enable_breakpoint(self, line, temporary=False):
        self.lines.tag_remove(
            'disabled',
            '%s.0' % line,
            '%s.0' % (line + 1)
        )
        self.lines.tag_remove(
            'ignored',
            '%s.0' % line,
            '%s.0' % (line + 1)
        )
        if temporary:
            self.lines.tag_remove(
                'enabled',
                '%s.0' % line,
                '%s.0' % (line + 1)
            )
            self.lines.tag_add(
                'temporary',
                '%s.0' % line,
                '%s.0' % (line + 1)
            )
        else:
            self.lines.tag_remove(
                'temporary',
                '%s.0' % line,
                '%s.0' % (line + 1)
            )
            self.lines.tag_add(
                'enabled',
                '%s.0' % line,
                '%s.0' % (line + 1)
            )

    def disable_breakpoint(self, line):
        self.lines.tag_remove(
            'enabled',
            '%s.0' % line,
            '%s.0' % (line + 1)
        )
        self.lines.tag_remove(
            'ignored',
            '%s.0' % line,
            '%s.0' % (line + 1)
        )
        self.lines.tag_remove(
            'temporary',
            '%s.0' % line,
            '%s.0' % (line + 1)
        )
        self.lines.tag_add(
            'disabled',
            '%s.0' % line,
            '%s.0' % (line + 1)
        )

    def clear_breakpoint(self, line):
        self.lines.tag_remove(
            'enabled',
            '%s.0' % line,
            '%s.0' % (line + 1)
        )
        self.lines.tag_remove(
            'disabled',
            '%s.0' % line,
            '%s.0' % (line + 1)
        )
        self.lines.tag_remove(
            'ignored',
            '%s.0' % line,
            '%s.0' % (line + 1)
        )
        self.lines.tag_remove(
            'temporary',
            '%s.0' % line,
            '%s.0' % (line + 1)
        )

    def on_line_double_click(self, event):
        "When a line number is double clicked, set a breakpoint"
        try:
            # If a breakpoint already exists on this line,
            # find it and toggle it.
            bp = self.debugger.breakpoint((self.filename, event.line))
            if bp.enabled:
                self.debugger.disable_breakpoint(bp)
            else:
                self.debugger.enable_breakpoint(bp)
        except UnknownBreakpoint:
            # No breakpoint for this line; create one.
            self.debugger.create_breakpoint(self.filename, event.line)
        except ConnectionNotBootstrapped:
            print "Connection not configured"

    def on_name_double_click(self, event):
        "When a code variable is clicked on... do something"
        pass


class BreakpointView(Treeview):
    def __init__(self, *args, **kwargs):
        # Only a single stack frame can be selected at a time.
        kwargs['selectmode'] = 'browse'
        self.normalizer = kwargs.pop('normalizer')
        Treeview.__init__(self, *args, **kwargs)

        # self['columns'] = ('line',)
        # self.column('line', width=100, anchor='center')
        self.heading('#0', text='File')
        # self.heading('line', text='Line')

        # Set up styles for line numbers
        self.tag_configure('enabled', foreground='red')
        self.tag_configure('disabled', foreground='gray')
        self.tag_configure('ignored', foreground='green')
        self.tag_configure('temporary', foreground='pink')

    def insert_filename(self, filename):
        "Ensure that a specific filename exists in the breakpoint tree"
        if not self.exists(filename):
            # First, establish the index at which to insert this child.
            # Do this by getting a list of children, sorting the list by name
            # and then finding how many would sort less than the label for
            # this node.
            files = sorted(self.get_children(''), reverse=False)
            index = len([item for item in files if item > filename])

            # Now insert a new node at the index that was found.
            self.insert(
                '', index, filename,
                text=self.normalizer(filename),
                open=True,
                tags=['file']
            )

    def update_breakpoint(self, bp):
        """Update the visualization of a breakpoint in the tree.

        If the breakpoint isn't arlready on the tree, add it.
        """
        self.insert_filename(bp.filename)

        # Determine the right tag for the line number
        if bp.enabled:
            if bp.temporary:
                tag = 'temporary'
            else:
                tag = 'enabled'
        else:
            tag = 'disabled'

        # Update the display for the line number,
        # adding a new tree node if necessary.
        if self.exists(unicode(bp)):
            self.item(unicode(bp), tags=['breakpoint', tag])
        else:
            # First, establish the index at which to insert this child.
            # Do this by getting a list of children, sorting the list by name
            # and then finding how many would sort less than the label for
            # this node.
            lines = sorted((int(self.item(item)['text']) for item in self.get_children(bp.filename)), reverse=False)
            index = len([line for line in lines if line < bp.line])

            # Now insert a new node at the index that was found.
            self.insert(
                bp.filename, index, unicode(bp),
                text=unicode(bp.line),
                open=True,
                tags=['breakpoint', tag]
            )


class StackView(Treeview):
    def __init__(self, *args, **kwargs):
        # Only a single stack frame can be selected at a time.
        kwargs['selectmode'] = 'browse'
        self.normalizer = kwargs.pop('normalizer')
        Treeview.__init__(self, *args, **kwargs)

        self['columns'] = ('line',)
        self.column('line', width=50, anchor='center')
        self.heading('#0', text='File')
        self.heading('line', text='Line')

    def update_stack(self, stack):
        "Update the display of the stack"
        # Retrieve the current stack list
        displayed = self.get_children()

        # Iterate over the entire stack. Update each entry
        # in the stack to match the current frame description.
        # If we need to add an extra frame, do so.
        index = 0
        for line, frame in stack:
            if index < len(displayed):
                self.item(
                    displayed[index],
                    text=self.normalizer(frame['filename']),
                    values=(line,)
                )
            else:
                self.insert(
                    '', index, 'frame:%s' % index,
                    text=self.normalizer(frame['filename']),
                    open=True,
                    values=(line,)
                )
            index = index + 1

        # If we've stepped back out of a frame, there will
        # be less frames than are currently displayed;
        # delete the excess entries.
        for i in range(index, len(displayed)):
            self.delete(displayed[i])


class InspectorView(Treeview):
    def __init__(self, *args, **kwargs):
        # Only a single stack frame can be selected at a time.
        kwargs['selectmode'] = 'browse'
        Treeview.__init__(self, *args, **kwargs)

        self.locals = self.insert(
            '', 'end', ':builtins:',
            text='builtins',
            open=False,
        )

        self.globals = self.insert(
            '', 'end', ':globals:',
            text='globals',
            open=False,
        )

        self.locals = self.insert(
            '', 'end', ':locals:',
            text='locals',
            open=True,
        )

        self['columns'] = ('value',)
        self.column('#0', width=150, anchor='w')
        self.column('value', width=200, anchor='w')
        self.heading('#0', text='Name')
        self.heading('value', text='Value')

    def show_frame(self, frame):
        "Update the display of the stack frame"
        self.update_node(':builtins:', frame['builtins'])
        self.update_node(':globals:', frame['globals'])
        self.update_node(':locals:', frame['locals'])

    def update_node(self, parent, frame):
        # Retrieve the current stack list
        displayed = self.get_children(parent)

        # The next part is a dual iteration: a primary iteration
        # over all the variables in the frame, with a secondary
        # iteration over all the current displayed tree nodes.
        # The iteration finishes when we reach the end of the
        # primary iteration.
        display = 0
        index = 0
        variables = sorted(frame.items())

        while index < len(variables):
            name, value = variables[index]
            node_name = '%s%s' % (parent, name)
            if display < len(displayed):
                if node_name == displayed[display]:
                    # Name matches the expected index.
                    # Update the existing node value, and
                    # move to the next displayed index.
                    self.item(
                        node_name,
                        text=name,
                        values=(value,)
                    )
                    index = index + 1
                    display = display + 1
                elif node_name > displayed[display]:
                    # The variable name will sort after the next
                    # displayed name. This means a variable has
                    # passed out of scope, and should be deleted.
                    # Move to the next displayed index.
                    self.delete(displayed[display])
                    display = display + 1
                else:
                    # The variable name will sort before the next
                    # displayed name. This means a new variable
                    # has entered scope and must be added.
                    self.insert(
                        parent, index, node_name,
                        text=name,
                        values=(value,)
                    )
                    index = index + 1
            else:
                # There are no more displayed nodes, but there are still
                # variables in the frame; we add them all to the end
                self.insert(
                    parent, 'end', node_name,
                    text=name,
                    values=(value,)
                )
                index = index + 1

        # Primary iteration has ended, which means we've run out of variables
        # in the frame. However, there may still be display nodes. Delete
        # them, because they are stale.
        for i in range(display, len(displayed)):
            self.delete(displayed[i])
