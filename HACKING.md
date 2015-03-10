# Introduction

Detail basic command to know when developing trip.
All commands must be executed from the root of the repository.

## Test suite

To run `hunittest` own automatic test suite:

```sh
python3 -m unittest discover hunittest.test
```

## To test the CLI

```sh
PYTHONPATH=. ./bin/hunittest test_samples
```

## Debugging completion

```sh
PROGNAME=hunittest TEST_ARGS='test.' _ARG_DEBUG=1 COMP_LINE="$PROGNAME $TEST_ARGS" COMP_POINT=1024 _ARGCOMPLETE=1 $PROGNAME 8>&1
```
