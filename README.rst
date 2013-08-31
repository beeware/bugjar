Bugjar
======

Bugjar is part of the `BeeWare suite`_. The project website is
`http://pybee.org/bugjar`_.

Anyone who learned to code in the mid to late 80s probably spent some
time with a Borland compiler -- probably either Turbo Pascal or Turbo C.
One of the best features of the Turbo compilers was their IDE -- and
in particular, a really good visual debugger that would let you inspect
code while it was running.

Then we all moved to Unix, and somehow forgot what a good debugger was.
GDB is perfectly functional, but isn't very intuitive. GDB gives you
perfect control over the execution of your code, but bad contextual
information to let you know what control you should be exercising.

Then came Python. Python's execution model contains excellent debugging
hooks, and supplies PDB as a proof of concept. PDB is an interface that
shares many similarities with GDB -- text mode, fantastic control, but
very bad contextual information.

So - enter ``bugjar``. A graphical interface for debugging code.
PDB, but with the context to help you step through code in a meaningful way.

.. _BeeWare suite: http://pybee.org/
.. _http://pybee.org/bugjar: http://pybee.org/bugjar

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


Documentation
-------------

Documentation for bugjar can be found on `Read The Docs`_.

Community
---------

Bugjar is part of the `BeeWare suite`_. You can talk to the community through:

 * `@pybeeware on Twitter`_

 * The `BeeWare Users Mailing list`_, for questions about how to use the BeeWare suite.

 * The `BeeWare Developers Mailing list`_, for discussing the development of new features in the BeeWare suite, and ideas for new tools for the suite.

Contributing
------------

If you experience problems with bugjar, `log them on GitHub`_. If you want to contribute code, please `fork the code`_ and `submit a pull request`_.

.. _Read The Docs: http://bugjar.readthedocs.org
.. _@pybeeware on Twitter: https://twitter.com/pybeeware
.. _BeeWare Users Mailing list: https://groups.google.com/forum/#!forum/beeware-users
.. _BeeWare Developers Mailing list: https://groups.google.com/forum/#!forum/beeware-developers
.. _log them on Github: https://github.com/pybee/bugjar/issues
.. _fork the code: https://github.com/pybee/bugjar
.. _submit a pull request: https://github.com/pybee/bugjar/pulls
