# Welcome to hunittest

Hunittest is user friendly command line interface for unittest.
It to unittest what htop is to top.

# Features

* Work with any unittest test suite
* One line progress status output (inspired by
  [ninja](https://github.com/martine/ninja))
* No dependency: you can just copy it as is in your project.
* Fancy color if you install [colorama](https://pypi.python.org/pypi/colorama)
* Convenient shell completion if you install
  [argcomplete](https://pypi.python.org/pypi/argcomplete)
* Error are printed as soon as they happen, not at the end of the entire
  test suite.
* Filter rules system.
* Just one single python script.

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
export PYTHONPATH="<path/to/hunittest/repo>:$PYTHONPATH"
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

# Hacking

See HACKING.md for details.

# License

_hunittest_ is released under the term of the [Simplified BSD License](http://choosealicense.com/licenses/bsd-2-clause).
Copyright (c) 2015, Nicolas Desprès
All rights reserved.
