Bugjar
======

Bugjar is an interactive graphical debugger for Python code.

Getting started
---------------

Bugjar can be installed with pip:

    $ pip install bugjar

You can then debug a Python script by typing the following at a shell prompt:

    $ bugjar myscript.py arg1 arg2

This will start a graphical interface, with ``myscript.py`` loaded into the
source code window. You can set (or remove) breakpoints by clicking on line
numbers; you can step through and into code; or you can set the program
running unconstrained. Each time the debugger stops at a breakpoint, the
inspector will be updated with the current contents of locals, globals, and
builtins.

The Python script will run using your current environment; if you have an
active virtualenv, that environment will be current.

When you quit the debugger, the script will be terminated.

Headless mode
-------------

Bugjar can also operate in a headless mode. This can be use to debug processes
running on a remote machine (although it also works on local machines).

In headless mode, Bugjar is split into two parts:

 * The **Net**: a headless backend responsible for debugging code

 * The **Jar**: the GUI used to inspect code.

To debug in headless mode, you first start a headless debugger (the net) on the
process that you want to debug:

    $ bugjar-net myscript.py arg1 arg2

Then, on the machine that you want to visualize the debugging session, you
start the user interface (the jar), and attach it to the net:

    $ bugjar-jar --host example.com

If the net and the jar are running on the same machine, the
``--host example.com`` argument can be ommitted.

Unlike local mode, when you quit the debugger, the script will *not* be
terminated by closing the jar. If you close the jar, and reopen a new session,
the GUI will resume where it left off. The net is responsible for running the
script; when the net is stopped, the script will be terminated.
