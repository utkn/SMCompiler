# Running

Running the tests are done the same way as described in the initial handout:

```
$ python3 -m pytest
```

To run the measurement scripts (which was added by us), first create a virtual environment with the requirements listed in `requirements.txt` and run:

```
$ python3 measurements.py -r $NUM_RUNS -e $EXPERIMENT_ID -a $ARGUMENT
```

Note that `$ARGUMENT` corresponds to the *N* variable in the experiment descriptions in report.
