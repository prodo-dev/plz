# plz 😸

*Say the magic word.*

`plz` is a job runner targetted at training machine learning models as simply, tidely and cheaply as possible. You can run jobs locally or in the cloud. At the moment `plz` is optimised for `pytorch`, in the sense that you can run pytorch programs without preparing a `pytorch` environment. With proper configuration and preparation it is fairly general, and can be used for practically anything that requires running a job in a repeatable fashion on a dedicated cloud VM.

*We are in beta stage. We don't expect API stability or consistence with forthcoming versions*

This tool helps with a lot of tasks. Some of them are the ones you're used to do when running things in the cloud or an experimentation environment:

1. Starts a "worker" (typically on AWS EC2, but also locally) to run your job.
2. Packages your code, parameters and data and ships them to the worker.
3. Runs your code.
4. Saves the results (like losses) and outcomes (like models) so that you can back to them in the future.
5. Takes down the worker.

 `plz` just automates those tasks for you. It also:

6. Reruns previous jobs as to make sure the results are repeatable.
7. Provides a history including the result and parameters, so that you have experiment data in a structured format. 

We build `plz` following these principles:

- All of your code and data must lie within your own (cloud) infrastructure.
No data or code uploaded everywhere else.
- Whatever part of the running environment can be captured by `plz`, it should
be captured as to make runs repeatable.
- It must be flexible enough so that no unnecessary restrictions are imposed
by the architecture. You should be able to do with `plz` whatever you
can do by running a container manually. It was surprising to find out how
many issues, mostly around running jobs in the cloud, could be solved only
by tweaking the configuration, without requiring any changes to the code.

`plz` is routinely used at `prodo.ai` to train ML models in the cloud, some
of them taking days to run in the most powerful instances available.

## How does it work?

There is a service called controller, and a command-line interface (CLI) that
perform requests to the controller. There are two configurations of
the controller that are ready for you to use: in one of them your jobs are run
locally, while in the other an aws instance is started for each job. (Note: The
controller itself can be deployed to the cloud (and if you're in a production
environment that's the recommended way), but we suggest you try the examples
with a controller that runs locally first.)

When you have a directory with source code, you can just add a `plz.config.json`
file including information such as:
- The command you want to run
- The location of your input data
- Whether you want to request for an instance at fix price, or bid for spot
  instances, and how much money you want to spend

Then, just typing `plz run` will run the job for you, either locally or in
aws depending on the controller you've started.


## Future work

In the future, `plz` is intended to:

* add support for visualisations, like tensorboard,
* manage epochs to capture intermediate metrics and results, and terminate runs early,
* and whatever else sounds like fun. ([Please, tell us!](https://github.com/prodo-ai/plz/issues))

## Instructions for developers

### Installing dependencies

1. Run `pip install pipenv` to install [`pipenv`](https://docs.pipenv.org/).
2. Run `make environment` to create the virtual environments and install the dependencies.

For more information, take a look at [the `pipenv` documentation](https://docs.pipenv.org/).

### Using the CLI

See the CLI's [*README.rst*](https://github.com/prodo-ai/plz/blob/master/cli/README.rst).

### Deploying a test environment

1. Clone this repository.
2. Install [direnv](https://direnv.net/).
3. Create a *.envrc* file in the root of this repository:
   ```
   export SERCRETS_DIR="${PWD}/secrets"
   ```
4. Create a configuration file named *secrets/config.json* based on *example.config.json*.
5. Run `make deploy`.

### Deploying a production environment

Do just as above, but put your secrets directory somewhere else (for example, another repository, this one private).
