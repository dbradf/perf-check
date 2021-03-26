# perfcheck

A script to compare the evergreen performance results from different sources.

This is a quickly put together scripts to check if cedar performance results cover all the
results obtained from legacy evergreen. It is nowhere near ready for "production", but can be
used for exploration.

## Usage

```bash
$ perf-check --build-id <evergreen build id> --weeks-back 4
...
================================================================================
Correct: 12359
Missing Order: 0
Missing Result: 4433
Incorrect result: 0
```

This will look at all the tasks that completed successful in the given evergreen build and
check their performance history over the provided time. 

It will print out any discrepancies as well as a summary of what was found.

