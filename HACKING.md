# Introduction

Detail basic command to know when developing trip.
All commands must be executed from the root of the repository.

## Debugging completion

```sh
PROGNAME=hunittest TEST_ARGS='test.' _ARG_DEBUG=1 COMP_LINE="$PROGNAME $TEST_ARGS" COMP_POINT=1024 _ARGCOMPLETE=1 $PROGNAME 8>&1
```
