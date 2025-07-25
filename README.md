[<img src="https://beeware.org/project/projects/tools/bugjar/bugjar.png" width="72" alt="image" />](https://beeware.org/bugjar)


# Bugjar

[![image](https://img.shields.io/pypi/pyversions/bugjar.svg)](https://pypi.python.org/pypi/bugjar)

[![image](https://img.shields.io/pypi/v/bugjar.svg)](https://pypi.python.org/pypi/bugjar)

[![image](https://img.shields.io/pypi/status/bugjar.svg)](https://pypi.python.org/pypi/bugjar)

[![image](https://img.shields.io/pypi/l/bugjar.svg)](https://github.com/pybee/bugjar/blob/master/LICENSE)

[![Build Status](https://github.com/beeware/bugjar/workflows/CI/badge.svg?branch=main)](https://github.com/beeware/bugjar/actions)

[![Discord server](https://img.shields.io/discord/836455665257021440?label=Discord%20Chat&logo=discord&style=plastic)](https://beeware.org/bee/chat/)

Anyone who learned to code in the mid to late 80s probably spent some
time with a Borland compiler -- probably either Turbo Pascal or Turbo C.
One of the best features of the Turbo compilers was their IDE -- and in
particular, a really good visual debugger that would let you inspect
code while it was running.

Then we all moved to Unix, and somehow forgot what a good debugger was.
GDB is perfectly functional, but isn't very intuitive. GDB gives you
perfect control over the execution of your code, but bad contextual
information to let you know what control you should be exercising.

Then came Python. Python's execution model contains excellent debugging
hooks, and supplies PDB as a proof of concept. PDB is an interface that
shares many similarities with GDB -- text mode, fantastic control, but
very bad contextual information.

So - enter `bugjar`. A graphical interface for debugging code. PDB, but
with the context to help you step through code in a meaningful way.

## Getting started

Bugjar can be installed with pip:

    $ pip install bugjar

You can then debug a Python script by typing the following at a shell
prompt:

    $ bugjar myscript.py arg1 arg2

This will start a graphical interface, with `myscript.py` loaded into
the source code window. You can set (or remove) breakpoints by clicking
on line numbers; you can step through and into code; or you can set the
program running unconstrained. Each time the debugger stops at a
breakpoint, the inspector will be updated with the current contents of
locals, globals, and builtins.

The Python script will run using your current environment; if you have
an active virtualenv, that environment will be current.

When you quit the debugger, the script will be terminated.

### Problems under Ubuntu

Ubuntu's packaging of Python omits the `idlelib` library from it's base
packge. If you're using Python 2.7 on Ubuntu 13.04, you can install
`idlelib` by running:

    $ sudo apt-get install idle-python2.7

For other versions of Python and Ubuntu, you'll need to adjust this as
appropriate.

### Problems under Windows

If you're running Cricket in a virtualenv, you'll need to set an
environment variable so that Cricket can find the TCL graphics library:

    $ set TCL_LIBRARY=c:\Python27\tcl\tcl8.5

You'll need to adjust the exact path to reflect your local Python
install. You may find it helpful to put this line in the `activate.bat`
script for your virtual environment so that it is automatically set
whenever the virtualenv is activated.

## Documentation

Documentation for bugjar can be found on [Read The
Docs](https://bugjar.readthedocs.io).

## Community

Bugjar is part of the [BeeWare suite](https://beeware.org/). You can
talk to the community through:

- [@beeware@fosstodon.org on Mastodon](https://fosstodon.org/@beeware)
- [Discord](https://beeware.org/bee/chat/)

We foster a welcoming and respectful community as described in our
[BeeWare Community Code of
Conduct](http://beeware.org/community/behavior/).

## Contributing

If you experience problems with bugjar, [log them on
GitHub](https://github.com/beeware/bugjar/issues). If you want to
contribute code, please [fork the
code](https://github.com/beeware/bugjar) and [submit a pull
request](https://github.com/beeware/bugjar/pulls).
