# Welcome to hunittest

Hunittest is user friendly command line interface for unittest.
It is to unittest what htop is to top. Just a nicer command line interface.
It does not add or change anything on the API side of the `unittest` module.

# Features

* Work with any unittest test suite
* One line progress status output (inspired by
  [ninja](https://github.com/martine/ninja)). Thus, buffering of stdout/stderr
  is always on (no `-b/--buffer` option like in usual `unittest` driver).
* No mandatory dependencies.
* Fancy color if your terminal support it.
* Convenient shell completion if you install
  [argcomplete](https://pypi.python.org/pypi/argcomplete)
* Error are printed on the go (no need for `-c/--catch` equivalent).
* `-f/--failfast` option like in `unittest`.
* `-q/--quiet` option that truly prints nothing. Only the exit status
  tells you whether the test suite was successful.
* `-t/--top-level-directory` option just like `unittest`.
* Filter rules system.
* Time individual tests
* ImportError are properly reported while collecting test spec.
* Coverage support if you install
  [coverage](https://pypi.python.org/pypi/coverage/4.0a5).
* Automatically pop-up a page with the error message if any (see
  `--pager` options).
* Tested with Python 3.4.x

# Installation

It requires Python 3.4.x at the moment. And you can install `colorama` and
`argcomplete` (using `pip3`) if you really want to enjoy it all.

## From source

```sh
git clone <FIXME:hunittesturl> <path/to/hunittest/repo>
```

Add this lines to your `~/.bash_profile` or `~/.zshenv` file:

```sh
export PATH="<path/to/hunittest/repo>/bin:$PATH"
export HUNITTEST_AUTO_PYTHONPATH=true
```

With this installation you won't be able to use hunittest like this:

```sh
python3 -m hunittest.cli ...
```

But you can do:

```sh
hunittest ...
```

## shell completion

To enable shell completion follow instructions in
[argcomplete](https://pypi.python.org/pypi/argcomplete) documentation.

Here is just what I did for *zsh*:
* install argcomplete: `pip3 install argcomplete`
* Add something like this to my `.zshrc`:
  ```sh
  # Register python completion
  if type register-python-argcomplete &> /dev/null
  then
    eval "$(register-python-argcomplete 'hunittest')"
  fi
  ```
* Re-launch your shell: `exec zsh`

# Known bugs

* Does not work with nested TestCase.
* If shell-completion does not work whereas we have configured it
  well, you probably have an module that cannot be imported. I do not
  know how to print error message in this case using
  argcomplete. Thus, to trouble shoot such situation do:
  `hunittest -c myproject.test` to check for any error.

# Hacking

See HACKING.md for details.

# License

_hunittest_ is released under the term of the [Simplified BSD License](http://choosealicense.com/licenses/bsd-2-clause).
Copyright (c) 2015, Nicolas Desprès
All rights reserved.
