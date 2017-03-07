====================
Welcome to hunittest
====================

.. Macros
.. |hunittest| replace:: *Hunittest*
.. External links
.. _unittest: https://docs.python.org/3/library/unittest.html
.. _ninja: https://github.com/ninja-build/ninja
.. _argcomplete: https://pypi.python.org/pypi/argcomplete
.. _coverage: https://pypi.python.org/pypi/coverage/4.0a5

|hunittest| is a user friendly command line interface for unittest_.
It is to unittest what htop is to top. Just a nicer command line interface.
It does not add or change anything to unittest_ module API.

Features
========

* Work with any unittest test suite
* One line progress status output (inspired by ninja_). Thus,
  buffering of stdout/stderr is always on (no ``-b/--buffer`` option
  like in usual unittest_ driver).
* No mandatory dependencies.
* Fancy color if your terminal support it.
* Convenient shell completion if you install argcomplete_.
* Support parallel execution of test.
* Error are printed on the go (no need for ``-c/--catch`` like in unittest_).
* ``-f/--failfast`` option like in unittest_.
* ``-q/--quiet`` option that truly prints nothing. Only the exit status
  tells you whether the test suite was successful.
* ``-t/--top-level-directory`` option just like unittest_.
* Filter rules system.
* Time individual tests.
* ImportError are properly reported while collecting test spec (i.e.
  you see the exception raised while importing the module instead of
  an uninformative exception coming from unittest_ loading system)
* Coverage support if you install coverage_.
* |hunittest| write a log of all error/failures (in ``.hunittest/log``)
  so that we can review them using the pager of your choice. By
  default, it will always popup the pager if the error log file is not
  empty. You can control this behavior using the ``--pager`` option.
* Support ``--pdb`` option to start debugging when the first error
  happens.
* Run test whose last status was error or failure first.
* Highlight parts of the traceback concerning user's modules.
* Report detailed test status delta between two runs. Useful to see
  how many tests have been fixed/broken by your change.
* Report modification of working directory during test.
* Support sub-tests.
* Tested with Python 3.4.x

Installation
============

It requires Python 3.4.x at the moment. And you can install
argcomplete_ (using ``pip3``) if you really want to enjoy it all.

Directly from the source
------------------------

.. code:: bash

    $ git clone https://github.com/nicolasdespres/hunittest.git
    $ cd hunittest
    $ python3 setup.py develop

To uninstall it, you ca do:

.. code:: bash

    $ python3 setup.py develop --uninstall

However, this won't remove the easy install entry script generated.

Shell completion
----------------

To enable shell completion follow instructions in argcomplete_ documentation.

Here is just what I did for ``zsh``:

#. Install argcomplete_: ``pip3 install argcomplete``
#. Add something like this to my ``.zshrc``:

    .. code:: bash

        # Register python completion
        if type register-python-argcomplete &> /dev/null
        then
          eval "$(register-python-argcomplete 'hunittest')"
        fi

#. Re-launch your shell: ``exec zsh``

Usage examples
==============

Once installed you can use |hunittest| either like a regular command or like
regular python module.

.. code:: bash

    $ hunittest myproject.test
    $ python3 -m hunittest myproject.test

Note that when using the later form, the shell completion won't work but you
can specify the specific interpreter you want to use.

Known bugs
==========

* Does not work with nested TestCase.
* If shell-completion does not work whereas you have configured it
  well, you probably have a module that cannot be imported. In such
  case an error message is issued. Sometimes it will be printed more than once
  whereas you just hit TAB once. In all case, to trouble shoot the buggy
  modules in such situation do:
  ``hunittest -c myproject.test`` to check for any error.

Hacking
=======

See `HACKING <HACKING.rst>`_ for details.

License
=======

|hunittest| is released under the term of the
`Simplified BSD License <http://choosealicense.com/licenses/bsd-2-clause>`_.
Copyright (c) 2015, Nicolas Desprès
All rights reserved.
