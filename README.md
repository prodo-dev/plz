# Plz 😸

_Say the magic word._

_Plz_ (pronounced "please") runs your jobs storing code, input, outputs and
results so that they can be queried programmatically. That way, it helps with
traceability and reproducibility. In case you want to run your jobs in the
cloud, it makes the process frictionless compared to running them locally. Jump
[here](#plz-in-action) to see it in action.

At Prodo.AI, we use Plz to train our PyTorch-based machine learning models.

_Plz is an experimental product and is not guaranteed to be stable across
versions._

## Contents:

- [Plz in action](#plz-in-action)
- [How does it work?](#how-does-it-work)
- [Installation instructions](#installation-instructions)
- [Examples](#examples)
- [Plz principles](#plz-principles)
- [Future work](#future-work)

## Highlights

- simple command line interface
- cloud-agnostic architecture (on top of Docker), allowing you to run jobs
  locally, on bare metal, or on the cloud
  - Plz currently supports Amazon Web Services (AWS), but will most likely
    support other cloud providers in the future
  - full control of the type of cloud instance, allowing you to use whatever
    machine fits your job (and budget)
  - full support for NVIDIA GPUs, allowing you to run deep learning experiments
- common tooling support, with the following straight out of the box:
  - Python
  - Anaconda
  - PyTorch
- data-based workflow, so that you don't accidentally compute your model with
  the wrong input
- parameter awareness, so that you can run the same experiment with multiple
  sets of parameters
- full history, so that you can review your experiments over time
- useful examples provided (see the [Examples](#Examples) section)
- MIT-license allowing modification, distribution, private or commercial use
  (see [LICENSE](LICENSE) for more details)
- open for contributions, plz

## Plz in action

We offer more details [below](#installation-instructions) on how to setup Plz
and run your jobs, but we can start by giving you an overview of what Plz does.

Plz offers a command-line interface. You start by adding a `plz.config.json`
file to the directory where you have your source code. This file contains, among
other things, the command you run to put your program to work (for instance,
`python3 main.py`). Then you can use Plz to run your program with `plz run`. The
following example (provided in this repository) demonstrates this:

```
sergio@spaceship:~/plz/examples/pytorch$ plz run
👌 Capturing the files in /home/sergio/plz/examples/pytorch
👌 Building the program snapshot
Step 1/4 : FROM prodoai/plz_ml-pytorch
# Executing 3 build triggers
 ---> Using cache
[...]
---> 9c39e889659d
Successfully built 9c39e889659d
Successfully tagged 024444204267.dkr.ecr.eu-west-1.amazonaws.com/plz/builds:some-person-trying-pytorch-mnist-example-1541436382135
👌 Capturing the input
👌 983663 input bytes to upload
👌 Sending request to start execution
Instance status: querying availability
Instance status: requesting new instance
Instance status: pending
[...]
Instance status: starting container
Instance status: running
👌 Execution ID is: 55b66652-e11a-11e8-a36a-233ad251f4c1
👌 Streaming logs...
Using device: cuda
Epoch: 1. Training loss: 2.146302
Evaluation accuracy: 47.90 (max 0.00)
Best model found at epoch 1, with accurary 47.90
Epoch: 2. Training loss: 0.660179
Evaluation accuracy: 83.30 (max 47.90)
Best model found at epoch 2, with accurary 83.30
Epoch: 3. Training loss: 0.251717
Evaluation accuracy: 87.80 (max 83.30)
Best model found at epoch 3, with accurary 87.80
[...]
Epoch: 30. Training loss: 0.010750
Evaluation accuracy: 97.50 (max 98.10)
👌 Harvesting the output...
👌 Retrieving summary of measures (if present)...
{
  "max_accuracy": 98.1,
  "training_loss_at_max": 0.008485347032546997,
  "epoch_at_max": 25,
  "training_time": 43.3006055355072
}
👌 Execution succeeded.
👌 Retrieving the output...
le_net.pth
👌 Done and dusted.
```

From the above output, you'll see Plz do the following:

- Plz captures the files in your current directory. A snapshot of your code is
  built and stored in your infrastructure, so that you can retrieve the code
  used to run your job in the future (yes, you can specify files to be ignored,
  and you do so in the `plz.config.json`).
- It captures input data (as specified in the config) and uploads it. If you run
  another execution with the same input data, it will avoid uploading the data
  for a second time (based on timestamps and hashes).
- It starts an AWS instance, and waits until it's ready (or just runs the
  execution locally depending on the configuration).
- It streams the logs, just as if you were running your program directly.
- It shows metrics you collected during the run, such as _accuracy_ and _loss_
  (you can query those later).
- Finally, it downloads output files you might have created.
- (The AWS instance will be shut down in the background)

You can be patient and wait until it finishes, or you can hit `Ctrl+C` and stop
the program early:

```
Epoch: 9 Training loss: 0.330538
^C
👌 Your program is still running. To stream the logs, type:

        plz logs ad96b586-89e5-11e8-a7c5-8142e2563487
```

Plz runs your commands in a Docker container, either in your AWS infrastructure
or in your local machine, and so your actions in the terminal don't affect the
execution. If you are running this execution only, you can just type `plz logs`
and logs will be streamed from the current moment (unless you specify
`--since=start`, which will tell it to stream from the start of execution).

The big hexadecimal number you see in the output, next to `plz logs`, is the
execution ID you can use to refer to this execution. Plz remembers the last
execution that was _started_, and if you want to refer to that one you don't
need to include it in your command (you can just type `plz logs`). But if you
need to specify the execution ID, you can do `plz logs <execution-id>`.

Once your program has finished (or you've stopped it with `plz stop`) you can
run `plz output`, and it will download the files that your program has written.
In order to use this functionality, you need to tell your program to write to a
specific directory, which is provided to your program as an environment
variable. The files are saved under `output/<execution-id>` by default, but you
can specify the location with the `-p` option.

The instance will be kept there for some time (specified in `plz.config.json`)
in case you're running things interactively (so that you don't need to wait
while the instance goes through the startup process again).

You can use `plz describe` to print metadata about an execution in JSON format.
It's useful to tell one execution from another if you have several running at
the same time.

You can use `plz run --parameters a_json_file.json` to pass parameters to your
program. Passing parameters this way has two advantages:

- the parameters are stored in the metadata and can be queried (see the
  description of `plz history` below)
- you can use `plz rerun --override-parameters some_json_file.json` and run
  exactly the same execution but with different parameters, which helps running
  experiments in a systematic fashion.

There's also `plz history`, returning a JSON mapping from execution IDs to
metadata. If you write JSON files to a specific directory (see
`test/end-to-end/measures/simple`) they will be available in the metadata. You
can store things you've measured during your experiment (for instance, training
loss). Parameters will be in the metadata as well, so you can transform the
metadata using, for instance, [`jq`](https://stedolan.github.io/jq/), and find
out how your training loss changed as you changed your parameters.

```
sergio@spaceship:~/plz/examples/pytorch$ plz history | \
    jq 'to_entries[] | { "execution_id": .key,
                         "learning_rate": .value.parameters.learning_rate,
                         "accuracy": .value.measures.summary.max_accuracy }'
{
  "execution_id": "dafcb478-e11e-11e8-9f2c-87dc520968d5",
  "learning_rate": 0.01,
  "accuracy": 98
}
{
  "execution_id": "9cfd3f1a-e1cf-11e8-9449-b1cc03bcdb5f",
  "learning_rate": 0.1,
  "accuracy": 98.5
}
{
  "execution_id": "c0d65d66-e1cf-11e8-8ed8-0d6f99ec4bc3",
  "learning_rate": 0.5,
  "accuracy": 13
}
```

In this example, you can see that increasing the learning rate from `0.01` to
`0.1` gives you an improvement in accuracy from 98% to 98.5%, but further
increasing the learning rate leads to a disastrous decrease to 13%.

You can run `plz list` to list the running executions, as well as any running
instances on AWS. It also shows the instance IDs. You can kill instances with
`plz kill -i <instance-id>`.

The command `plz last` is useful, particularly when writing shell commands, to
get the last execution _started_.

We also make it easy to manage dependencies for projects using Anaconda.
Projects using the image `prodoai/plz_ml-pytorch` need to have an
`environment.yml` file, as the one produced by `conda env export` (see
[the one in the Pytorch example](examples/pytorch/environment.yml)). This file
will be applied on top of
[the environment in the image](base-images/ml-pytorch/environment.yml).
Installation of dependencies is cached, so the process of dependency
installation occurs only the first time after you change the environment file.

## How does it work?

Plz consists of a _controller_ service and a _command-line interface_ (CLI) that
issues requests to the controller. The CLI is a Python executable, `plz`, which
takes instructions (such as `plz run ...`) as described above.

There are two configurations of the controller that are ready for you to use: in
one of them your jobs are run locally, while in the other one an AWS instance is
started for each job. (Note: the controller itself can be deployed to the cloud,
and if you're in a production environment that's the recommended way to use it,
but we suggest you try the examples with a controller that runs locally first.)

When you have a directory with source code, you can just add a `plz.config.json`
file including information such as:

- the location of your Plz server,
- the command you want to run,
- the location of your input data,
- whether you want to request an on-demand instance at a fixed price, or bid for
  spot instances with a ceiling,
- and much more.

Then, just typing `plz run` will run the job for you, either locally or on AWS,
depending on the controller you've started.

## Installation instructions

Chances are you that you have most of the supporting tools already installed, as
these are broadly used tools.

1. Install Git, and Python 3.
   1. On Ubuntu, you can run
      `sudo apt install -y git python3 python3-pip python-pip`.
   2. On macOS, install [Homebrew](https://brew.sh/), then run
      `brew install git python`.
   3. For all other operating systems, you're going to have to Google it.
2. Install [Docker](https://docs.docker.com/install/).
   1. On Ubuntu, you can run:
      ```
      sudo apt install -y curl
      curl -fsSL https://get.docker.com -o get-docker.sh
      sudo sh get-docker.sh
      sudo usermod -aG docker "$USER"
      ```
      then start a new shell with `sudo su - "$USER"` so that it picks up the
      membership to the `docker` group.
   2. On macOS, you can use Homebrew to install Docker with
      `brew cask install docker`.
3. Install Docker Compose (`pip install docker-compose`). You might want to make
   sure that `pip` installs the `docker-compose` command somewhere in your
   `PATH`. On Ubuntu with the default Python installation, this is typically
   `$HOME/.local/bin` (so you need the command
   `export PATH="${HOME}/.local/bin:${PATH}"`).
4. If you're planning on running code with CUDA in your machine, install the
   [NVIDIA Container Runtime for Docker](https://github.com/NVIDIA/nvidia-docker)
   (not needed for using CUDA on AWS).
5. `git clone https://github.com/prodo-ai/plz`, then `cd plz`.
6. Install the CLI by running `./install_cli`, which calls `pip3`. Same as for
   `docker-compose` you might want to check that the `plz` command is in your
   path.
7. Run the controller
   ([keep reading](#running-the-controller-for-local-executions)).

The first time you run the controller, it will take some time, as it downloads a
"standard" environment which includes Anaconda and PyTorch. When it's ready the
logs will show `Harvesting complete. You can run plz commands now`.

The controller runs in the foreground, and can be killed with _Ctrl+C_. If you'd
like to run it in the background, append `-d` to the command to run it in
"detached" mode.

If you've run the controller in the background, or if you lose your terminal, it
will carry on running. You can stop it with `./stop`.

### Running the controller for local executions

Once you've set up your system as above, run:

```
./start/local-prebuilt
```

The controller can be stopped at any time with:

```
./stop
```

### Running the controller for AWS executions

If you want to run the examples using the AWS instances, be aware that this has
a cost. By default, Plz uses _t2.micro_ on-demand instances. You can find out
how much these cost on the
[AWS EC2 Pricing](https://aws.amazon.com/ec2/pricing/on-demand/) page.

To start a controller that talks to AWS, you'll need to first set up the AWS
CLI:

1. Install the AWS CLI: `pip install awscli`
2. Configure it with your access key: `aws configure`
3. Verify you can connect to AWS by running `aws iam get-user` and checking your
   username is correct.

If you usually use AWS in a particular region, please edit
`aws_config/config.json` and set your region there. The default file sets the
region to _eu-west-1_ (Ireland).

Then run:

```
./start/aws-prebuilt
```

Unless you add `"instance_max_uptime_in_minutes": null,` to your
`plz.config.json`, all AWS instances you start terminate after 60 minutes.
That's on purpose, in case you're just trying the tool and something doesn't go
well (for example, there's a power cut). You can always use `plz list` and
`plz kill` before leaving your computer, as to make sure that there no instances
remaining. For maximum assurance, we recommend checking the state of your
instances in the AWS console.

By default, Plz uses on-demand instances. In order to use spot instances,
specify the following in your _plz.config.json_ file:

```json
{
    ...
    "instance_market_type": "spot",
    "max_bid_price_in_dollars_per_hour": <price>
}
```

The value in the example configuration files range from \$0.5/hour to \$2/hour
(for GPU-powered machines).

## Examples

### Python

In the directory `examples/python`, there is a minimal example showing how to
run a program with Plz that handles input and output. Once you
[have a working controller](#installation-instructions), running `plz run`
inside the directory will start the job.

### PyTorch

In the directory `examples/pytorch`, there's a full-fledged example for the task
of digit recognition using the classic approach of LeNets and a subset of the
well-known MNIST dataset.

Anything related to Plz is in `main.py`. In fact the most relevant lines are the
following ones:

```python
def get_from_plz_config(key: str, non_plz_value: T) -> T:
    configuration_file = os.environ.get('CONFIGURATION_FILE', None)
    if configuration_file is not None:
        with open(configuration_file) as c:
            config = json.load(c)
        return config[key]
    else:
        return non_plz_value
[...]
    input_directory = get_from_plz_config(
        'input_directory', os.path.join('..', 'data'))
    output_directory = get_from_plz_config('output_directory', 'models')
    parameters = get_from_plz_config('parameters', DEFAULT_PARAMETERS)
    measures_directory = get_from_plz_config('measures_directory', 'measures')
    summary_measures_path = get_from_plz_config(
        'summary_measures_path',
        os.path.join('measures', 'summary'))
```

This shows how to get the input data and parameters that Plz uploads for you.
There's a configuration file whose name comes in the environment variable
`CONFIGURATION_FILE`. If that variable is present, you're running with Plz, and
you can read and parse the file as a JSON object. The object has the following
keys:

- `input_directory` is a directory where you'll find your input data. If you
  have `"input": "file://../data/mnist",` in your `plz.config.json` file, the
  directory `config['input_directory']` will have the same contents that
  `../data/mnist` has locally.
- `output_directory` is directory where you can write files. These are retrieved
  via `plz output`, or downloaded if you keep the CLI running until the end of
  the job.
- `parameters` is the JSON object that you passed with
  `plz run --parameters a_json_file.json`, if you so did. Otherwise it's an
  empty object.
- `measures_directory` is a directory in which you can write measures. You can
  query these with `plz measures`. Each file is interpreted as a property in a
  JSON object, using the file name as the key, and the file contents as the
  value, interpreted as JSON. By writing the code:

  ```python
      with open(os.path.join(measures_directory, f'epoch_{epoch}'), 'w') as f:
          json.dump({'training_loss': training_loss, 'accuracy': accuracy}, f)
  ```

  You can then run:

  ```
  sergio@spaceship:~/plz/examples/pytorch$ plz measures
  {
    "epoch_1": {
      "training_loss": 2.1326301097869873,
      "accuracy": 45.4
    },
    "epoch_2": {
      [...]
    }
  }
  ```

- `summary_measures_path` is a path to a file in which you can write a JSON
  object with a summary of the results you obtained in your run (best accuracy,
  total training time, etc.). The summary is available via `plz measures -s`,
  and also printed by the CLI if you wait until the job finishes.

If you want to use CUDA for this example, we have provided an example
configuration file for this purpose:

```
plz -c plz.cuda.config.json run
```

This tells Docker to use the
[CUDA runtime](https://github.com/NVIDIA/nvidia-docker).

## Plz principles

We built Plz following these principles:

- Data that isn't reproducible is worthless.
- You don't know the value of your data at the time of creation.
- Whatever part of the running environment can be captured by Plz, we capture it
  as to make jobs repeatable.
- Hardware is expensive.
- Code is a means to an end. What matters is the outcome you obtain from running
  your code.
- Functionality is based on standard mechanisms like files and environment
  variables. You don't need to add extra dependencies to your code or learn how
  to read/write your data in specific ways.
- The tool must be flexible enough so that no unnecessary restrictions are
  imposed by its architecture. You should be able to do with Plz whatever you
  can do by running a program manually. It was surprising to find out how much
  of the friction around running jobs in the cloud could be solved, only by
  tweaking the configuration and without requiring any changes to Plz code.

Plz is routinely used at `prodo.ai` to train ML models on AWS, some of them
taking days to run in the most powerful instances available. We trust it to
start and terminate these instances as needed, and to manage our spot instances,
allowing us to get a much better price than if we were using on-demand instances
all the time.

## How does Plz help

If you didn't have Plz, the steps you'd need as to run your code in an AWS
instance would be:

- go to the AWS console and start an instance (or have created a launch template
  and then use the cli)
- wait until the instance is up
- get the IP address of the instance from the console
- copy your code and data by ssh-ing to the instance
- ssh to the instance and run your job. Preferably inside docker so that a
  dropped connection doesn't kill your job (but if you want to have docker you
  have to take care of a `Dockerfile` and build the image)
- each time the connection drops or you turn off your computer, you need to ssh
  again. If you didn't use docker, you lost your terminal and it's very likely
  your job died
- watch your job until it finishes (and lose money at the point it has already
  finished and your instance keeps running, if you don't look often enough)
- copy your results back to your machine by ssh-ing to the instance, being
  disciplined about where you store them and making sure you can link them to
  the (version of the) code that produced them if you'll have several runs that
  you want to compare. Or, if you started from a program that was running
  locally, change it to write to a non-ephemeral location
- if you care about your standard output/logs, gather and retrieve them somehow
- make a note of your results (like stats or accuracy), or copy files with
  results

All of that gets simplified to `plz run`. If you stopped the output of `plz run`
(by hitting Ctrl-C, or turning off your computer) can do `plz output` to get the
output at any time.

If you want to rerun your job later (for instance, to try different parameters),
you would need to have saved a copy of the code (or have been very disciplined
with your git history, plus have tags or have commits for every single one-line
tweak you try --more about that [below](#why-is-Plz-the-way-it-is)), and
possibly also have the same data you have used. You'd need to retrieve the code
from wherever you have it (for instance, you may need to find the git branch,
and switch to it --possibly after creating a different copy of the repo if you
don't want to stop working on what you are doing it).

Another important factor is that it gives you a standard way to run your code.
Same as when you see a Makefile and you know that you can type `make`, when you
see a `plz.config.json` you know that you can do `plz run`. Then your code can
be launched in whatever machine your teammate happens to be sitting (specially
if the job runs in the cloud). Teammates need to install `plz`, sure, but your
team will know how to do it after a couple installs, and that's setting up one
program per team member, instead of one setup per project.

## Why is Plz the way it is

This section is an attempt to describe the rationale behind the high-level
architecture of Plz.

- why Docker: simplifies input and output, which results in concrete
  simplifications like log handling: we obtain a stream of logs from the running
  jobs just by calling the Docker API, with facilities to filter for time.
  Running commands with ssh requires to either keep the connection as to gather
  the output or redirecting the output and reading it later from a file. In
  general, Docker doesn't provide only isolation, but also an environment where
  the job runs autonomously with controlled inputs and outputs
- why not using git to store code snapshots (and use git to transfer code to the
  instance): because it's very common that users want to make changes that they
  don't necessarily want in their commit history. For instance, when users try
  to make their job run in the cloud, or to run it at a different scale than
  what they use to (for instance, to run the job with far more data than they do
  locally), they might try several one-line tweaks. These commits (possibly
  paired with messages that would be meaningless in a month, like ''Change
  foobar from 0 to 1'') are hardly useful and pollute the repo history. Plz
  could also create a different branch for each job but (in order to allow for
  `plz rerun`) then these branches should be kept, would be listed in
  `git branch`, etc. _A good summary answer to the question would be: because
  users want to commit stuff that ''works'' (commits you can revert to, use for
  reference, etc.) and you don't know whether something works until you've run
  it._ The solution for code storage we implemented, using Docker images, is
  quite simple to implement and understand as the docker API allows you to just
  send the files as a tarball in order to create an image (if we were using git,
  for the case of private repos, we would need to implement usage of git
  credentials in the instance, which would actually be more complicated than
  using Docker). Docker images are given a name so that they can be referenced
  later, making `plz rerun` easy to implement as well. The code can be retrieved
  by looking inside the image, which is a reliable source of truth, as it stores
  the code that was actually running

### Could Plz be smaller?

- why do we need a controller/server: one reason is to manage locks (for
  instance, to avoid two jobs requests using the same instance). It's true that
  locking could be done just by using a redis server (so instead of a
  controller/Plz server, the CLI could maybe point to a redis server taking care
  of locks). That would force the tool to assume that everyone uses it
  collaboratively (one could engineer an altered CLI that locks every instance,
  etc.). We are having this assumption now, but we are not forced to keep it in
  the future. Another reason for a controller is a feature that we have
  considered for a while: to rerun jobs for spot instances that were terminated
  because of being overbid. To that end, we need something to be running
  permanently the cloud, as there might not be a CLI running at the point in
  time where the spot instance is terminated. In general, it sounds like if you
  want to do something serious about a bunch of instances that are running
  permanently, eventually you'll need a coordinator/controller. Even if the
  current features might not strictly require a controller, it's good that any
  features that do require it won't need a major refactor. Needless to say, a
  controller-less Plz cannot be obtained by just erasing the controller: a major
  effort would be needed so that the tasks being done by the controller (setting
  inputs, collecting outputs, etc.) are done by, for instance, a wrapper of the
  program being run by the user
- why collecting information from the running program: while it would be
  possible to leave to user programs the task to write to whatever non-ephemeral
  storage they choose, that would put a burden on the Plz user to change their
  program significantly, with respect to a program that they already run locally
  (for instance, instead of writing local files, to use the AWS API to write to
  S3). With the current Plz mechanism, as long as there is a single point in
  your program where you can set the output directory (and, if you program
  doesn't have such point, it's a good idea to implement it anyway) you can
  write files and Plz will make them non-ephemeral for you. Also, with the
  current mechanism team members know how to access the outcomes of your job
  even if they don't know the details (`plz output` for ''blobs'' and
  `plz measures` for structured outputs), and can read them using standard
  tools, as every computer setup can process json and files (as opposed to, say,
  running SQL queries in the cloud)
- why managing the instances ourselves/why not using Kubernetes: because
  autoscaling mechanisms (either using Kubernetes or autoscaling groups) do not
  cover the case of ''interactive users'' which want to run instances, see them
  spawn when they launch a job and see them terminate when they stop it.
  Autoscaling mechanisms have ''cooling times'' specified so that scaling
  changes are not happening all the time, degrading performance, but they cause
  operations not to be immediate/deterministic and that can be really annoying
  when working interactively. We discovered all of these because our first
  attempt was to use AWS autoscaling groups, and that Plz was a pain to use and
  also to test manually (''did AWS get that we want to terminate this instance?
  Let's wait, sometimes it takes 5 minutes to take it down''). With respect to
  Kubernetes specifically, when we started Plz the Kubernetes implementation of
  AWS (EKS) wasn't there. There is a feature for Kubernetes in the works. We
  plan that users would be able to specify a Kubernetes cluster to which the
  execution will be sent (to support the case of a non-interactive user), or, as
  we currently do, specify an instance type, so that an instance will be started
  and managed by Plz (to support the case of an interactive user)

## Future work

In the future, Plz is intended to:

- add support for named inputs and outputs, and function as a sort of "build
  system" in the cloud, particulary suitable for build pipelines,
- add support for visualisations, such as
  [Tensorboard](https://www.tensorflow.org/guide/summaries_and_tensorboard),
- manage epochs to capture intermediate metrics and results, and terminate runs
  early,
- and whatever else sounds like fun.
  ([Please, tell us!](https://github.com/prodo-ai/plz/issues))

## Instructions for developers

### Installing dependencies

1. Run `pip install pipenv` to install [`pipenv`](https://docs.pipenv.org/).
2. Run `make environment` to create the virtual environments and install the
   dependencies.
3. Run `make check` to run the tests.

For more information, take a look at
[the `pipenv` documentation](https://docs.pipenv.org/).

### Using the CLI

See the CLI's
[_README.rst_](https://github.com/prodo-ai/plz/blob/master/cli/README.rst).

### Deploying a test environment

1. Clone this repository.
2. Install [direnv](https://direnv.net/).
3. Create a _.envrc_ file in the root of this repository:
   ```
   export SECRETS_DIR="${PWD}/secrets"
   ```
4. Create a configuration file named _secrets/config.json_ based on
   _example.config.json_.
5. Run `make deploy`.

### Deploying a production environment

Do just as above, but put your secrets directory somewhere else (for example,
another repository, this one private and encrypted).
