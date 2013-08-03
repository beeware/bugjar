"""A module containing a visual representation of the debugger

This is the "View" of the MVC world.
"""
import os
from Tkinter import *
from tkFont import *
from ttk import *
import tkMessageBox

from bugjar.widgets import ReadOnlyCode


class MainWindow(object):
    def __init__(self, root):
        '''
        -----------------------------------------------------
        | main button toolbar                               |
        -----------------------------------------------------
        |       < ma | in content area >      |             |
        |            |                        |             |
        | File list  | File name              | Inspector   |
        | (stack/    | Code area              |             |
        | breakpnts) |                        |             |
        |            |                        |             |
        |            |                        |             |
        -----------------------------------------------------
        |     status bar area                               |
        -----------------------------------------------------

        '''

        # Root window
        self.root = root
        self.root.title('Bugjar')
        self.root.geometry('1024x768')

        # Prevent the menus from having the empty tearoff entry
        self.root.option_add('*tearOff', FALSE)
        # Catch the close button
        self.root.protocol("WM_DELETE_WINDOW", self.on_quit)
        # Catch the "quit" event.
        self.root.createcommand('exit', self.on_quit)

        # Setup the menu
        self._setup_menubar()

        # Set up the main content for the window.
        self._setup_button_toolbar()
        self._setup_main_content()
        self._setup_status_bar()

        # Now configure the weights for the root frame
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=0)

        # FIXME - set up some initial content.
        self.show_file('/Users/rkm/projects/beeware/bugjar/bugjar/view.py')

        self.stack_list.insert('', 'end', text='file1.py', values=('123',))

        self.breakpoint_list.insert('', 'end', text='breakpoint1.py', values=('456',))

    ######################################################
    # Internal GUI layout methods.
    ######################################################

    def _setup_menubar(self):
        # Menubar
        self.menubar = Menu(self.root)

        # self.menu_Apple = Menu(self.menubar, name='Apple')
        # self.menubar.add_cascade(menu=self.menu_Apple)

        self.menu_file = Menu(self.menubar)
        self.menubar.add_cascade(menu=self.menu_file, label='File')

        self.menu_edit = Menu(self.menubar)
        self.menubar.add_cascade(menu=self.menu_edit, label='Edit')

        # self.menu_help = Menu(self.menubar, name='help')
        # self.menubar.add_cascade(menu=self.menu_help)

        # self.menu_Apple.add_command(label='Test', command=self.cmd_dummy)

        # self.menu_file.add_command(label='New', command=self.cmd_dummy, accelerator="Command-N")
        # self.menu_file.add_command(label='Open...', command=self.cmd_dummy)
        # self.menu_file.add_command(label='Close', command=self.cmd_dummy)

        # self.menu_edit.add_command(label='New', command=self.cmd_dummy)
        # self.menu_edit.add_command(label='Open...', command=self.cmd_dummy)
        # self.menu_edit.add_command(label='Close', command=self.cmd_dummy)

        # self.menu_help.add_command(label='Test', command=self.cmd_dummy)

        # last step - configure the menubar
        self.root['menu'] = self.menubar

    def _setup_button_toolbar(self):
        '''
        The button toolbar runs as a horizontal area at the top of the GUI.
        It is a persistent GUI component
        '''

        # Main toolbar
        self.toolbar = Frame(self.root)
        self.toolbar.grid(column=0, row=0, sticky=(W, E))

        # Buttons on the toolbar
        self.run_stop_button = Button(self.toolbar, text='Run', command=self.cmd_run_stop)
        self.run_stop_button.grid(column=0, row=0)

        self.continue_button = Button(self.toolbar, text='Continue', state=DISABLED, command=self.cmd_continue)
        self.continue_button.grid(column=1, row=0)

        self.step_button = Button(self.toolbar, text='Step', state=DISABLED, command=self.cmd_step)
        self.step_button.grid(column=2, row=0)

        self.next_button = Button(self.toolbar, text='Next', state=DISABLED, command=self.cmd_next)
        self.next_button.grid(column=3, row=0)

        self.return_button = Button(self.toolbar, text='Return', state=DISABLED, command=self.cmd_return)
        self.return_button.grid(column=4, row=0)

        self.toolbar.columnconfigure(0, weight=0)
        self.toolbar.rowconfigure(0, weight=0)

    def _setup_main_content(self):
        '''
        Sets up the main content area. It is a persistent GUI component
        '''

        # Main content area
        self.content = PanedWindow(self.root, orient=HORIZONTAL)
        self.content.grid(column=0, row=1, sticky=(N, S, E, W))

        # Create subregions of the content
        self._setup_file_lists()
        self._setup_code_area()
        self._setup_inspector()

        # Set up weights for the left frame's content
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.content.pane(0, weight=1)
        self.content.pane(1, weight=2)
        self.content.pane(2, weight=1)

    def _setup_file_lists(self):

        self.file_notebook = Notebook(self.content, padding=(0, 5, 0, 5))
        self.content.add(self.file_notebook)

        self.stack_list = Treeview(self.content)
        self.stack_list.grid(column=0, row=0, sticky=(N, S, E, W))
        self.stack_list['columns'] = ('line',)
        self.stack_list.column('line', width=100, anchor='center')
        self.stack_list.heading('line', text='Line')
        self.file_notebook.add(self.stack_list, text='Stack')

        self.breakpoint_list = Treeview(self.content)
        self.breakpoint_list.grid(column=0, row=0, sticky=(N, S, E, W))
        self.breakpoint_list['columns'] = ('line',)
        self.breakpoint_list.column('line', width=100, anchor='center')
        self.breakpoint_list.heading('line', text='Line')
        self.file_notebook.add(self.breakpoint_list, text='Breakpoints')

    def _setup_code_area(self):
        self.code_frame = Frame(self.content)
        self.code_frame.grid(column=1, row=0, sticky=(N, S, E, W))

        # Label for current file
        self.current_file = StringVar()
        self.current_file_label = Label(self.code_frame, textvariable=self.current_file)
        self.current_file_label.grid(column=0, row=0, sticky=(W, E))

        # Code display area
        self.code = ReadOnlyCode(self.code_frame)
        self.code.grid(column=0, row=1, sticky=(N, S, E, W))

        # Set up event handlers for code area
        # self.code.on_line_selected = self.on_set_breakpoint

        # Set up weights for the code frame's content
        self.code_frame.columnconfigure(0, weight=1)
        self.code_frame.rowconfigure(0, weight=0)
        self.code_frame.rowconfigure(1, weight=1)

        self.content.add(self.code_frame)

    def _setup_inspector(self):
        self.inspector_tree = Treeview(self.content)
        self.inspector_tree.grid(column=2, row=0, sticky=(N, S, E, W))

        self.content.add(self.inspector_tree)

    def _setup_status_bar(self):
        # Status bar
        self.statusbar = Frame(self.root)
        self.statusbar.grid(column=0, row=2, sticky=(W, E))

        # Current status
        self.run_status = StringVar()
        self.run_status_label = Label(self.statusbar, textvariable=self.run_status)
        self.run_status_label.grid(column=0, row=0, sticky=(W, E))
        self.run_status.set('Not running')

        # Main window resize handle
        self.grip = Sizegrip(self.statusbar)
        self.grip.grid(column=1, row=0, sticky=(S, E))

        # Set up weights for status bar frame
        self.statusbar.columnconfigure(0, weight=1)
        self.statusbar.columnconfigure(1, weight=0)
        self.statusbar.rowconfigure(0, weight=0)

    ######################################################
    # Utility methods for controlling content
    ######################################################

    def show_file(self, filename, line=None, breakpoints=None, refresh=False):
        path, name = os.path.split(filename)

        self.current_file.set('%s (%s)' % (name, path))
        self.code.show(filename)

    ######################################################
    # TK Main loop
    ######################################################

    def mainloop(self):
        self.root.mainloop()

    def on_quit(self):
        self.root.quit()

    def cmd_run_stop(self):
        pass

    def cmd_continue(self):
        pass

    def cmd_step(self):
        pass

    def cmd_next(self):
        pass

    def cmd_return(self):
        pass
