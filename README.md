# plz 😸

*Say the magic word.*

`plz` is a job runner targetted at training machine learning models as cheaply as possible.
It is, however, fairly general, so can be used for practically anything that requires running a job in a repeatable fashion on a dedicated cloud VM.

`plz run` performs a number of operations:

1. It starts a "worker" (typically on AWS EC2, as a spot instance) to run your job.
2. It packages your code and data and ships them to the worker.
3. It runs your code.
4. It aggregates the results.
5. It takes down the worker to make sure you're paying as little as possible.

We have tried to strike a balance between speed and price, so the `plz` controller keeps instances around for a little while before terminating them.

## Future work

In the future, `plz` is intended to:

* gather and plot metrics over multiple runs, to understand how training is progressing,
* search over hyperparameters in parallel to optimise models,
* manage epochs to capture intermediate metrics and results, and terminate runs early,
* and whatever else sounds like fun. ([Please, tell us!](https://github.com/prodo-ai/plz/issues))

## Installing dependencies

1. Run `pip install pipenv` to install [`pipenv`](https://docs.pipenv.org/).
2. Run `make environment` to create the virtual environments and install the dependencies.

For more information, take a look at [the `pipenv` documentation](https://docs.pipenv.org/).

## Using the CLI

See the CLI's [*README.rst*](https://github.com/prodo-ai/plz/blob/master/cli/README.rst).

## Deploying a test environment

1. Clone this repository.
2. Install [direnv](https://direnv.net/).
3. Create a *.envrc* file in the root of this repository:
   ```
   export SERCRETS_DIR="${PWD}/secrets"
   ```
4. Create a configuration file named *secrets/config.json* based on *example.config.json*.
5. Run `make deploy`.

## Deploying a production environment

Do just as above, but put your secrets directory somewhere else (for example, another repository, this one private).
