Introduction
============

Detail basic command to know when hacking ``hunittest``.
All commands must be executed from the root of the repository.

Test suite
----------

To run ``hunittest`` own automatic test suite:

.. code:: bash

    python3 -m unittest discover hunittest.test

or

.. code:: bash

    python3 -m hunittest.cli hunittest.test


To test the CLI
---------------

.. code:: bash

    PYTHONPATH=. python3 -m hunittest.cli hunittest.test_samples

Debugging completion
--------------------

The logger in the `hunittest.completionlib` module can be activated by
setting `LOGGER_ENABLED = True` at the beginning of the file. The log
file can be found in the source tree at `hunittest/completionlib.log`.

.. code:: bash

    PROGNAME=hunittest TEST_ARGS='test.' _ARG_DEBUG=1 COMP_LINE="$PROGNAME $TEST_ARGS" COMP_POINT=1024 _ARGCOMPLETE=1 $PROGNAME 8>&1
