# plz 😸

*Say the magic word.*

`plz` is a job runner targeted at training machine learning models as simply, tidily and cheaply as possible. You can run jobs locally or in the cloud. It includes functionality to reproduce your experiments, and to save your history of parameters and results, so that history can be queried with any program handling json. At the moment `plz` is optimised for `pytorch`, in the sense that you can run pytorch programs without preparing a `pytorch` environment. With proper configuration and preparation it is fairly general, and can be used for practically anything that requires running a job in a repeatable fashion on a dedicated cloud VM.

*We are in beta stage. We don't expect API stability or consistence with
next versions.*

## Usage overview

We offer more details below on how to setup `plz` and run your jobs, but we can
start by giving you an overview of what `plz` does.

`plz` offers a command-line interface. You start by adding a `plz.config.json`
file to the directory where you have your source code. This file contains,
among other things, the command you run to put your program to work (for
instance, `python main.py`). Then, you can run commands like `plz run`,
as shown for this example (that is provided in this repository as well):

```
sergio@sergio:~/plz/examples/pytorch$ plz run
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
Epoch: 30. Traning loss: 0.010750
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

You can see that the command:

- captures the files in your current directory. A snapshot of your code is built
and stored in your infrastructure, so that you can retrieve the code used to run
your job in the future (yes, you can specify files to be ignored, and you do
so in the `plz.config.json`)
- captures input data (as specified in the config) and uploads it. If you run
another execution with the same input data, it will avoid uploading the data
for a second time (based on timestamps and hashes)
- starts an AWS instance, and waits until it's ready (or just runs the
execution locally depending on the configuration)
- streams the logs the same as if you were running your program directly
- shows metrics you collected during the run, such as _accuracy_ and _loss_
(you can query those later)
- downloads output files you might have created.

You can be patient and wait until it finishes, but you can also hit `Ctrl-C`
and stop the program early:

```
Epoch: 9 Traning loss: 0.330538
^C
👌 Your program is still running. To stream the logs, type:

        plz logs ad96b586-89e5-11e8-a7c5-8142e2563487
```

`plz` runs your commands in a Docker container, either in your AWS
infrastructure or in your local machine, and so your actions in the terminal
don't affect the execution. If you are running this execution only, you can
just type `plz logs` and logs will be streamed, not from the beginning
but since the current time (unless you specify `--since start`).

The big
hexadecimal number you see in the output, next to `plz logs`, is the execution
ID you can use to refer to this execution. `plz` remembers the last execution
that was *started*, and if you want to refer to that one you don't need to
include it in our command. But if you need to specify the execution id,
you can do `plz logs <execution_id>`.

Once your program has finished (or once you have stopped with `plz stop`) you
can do `plz output`, and it will download the files that your program has
written. In order to use this functionality, you need to tell your program to
write in a specific directory: `plz` sets an environment variable that your
program can use as to know where to
write). The files are saved under `output/<execution_id>` by default, or
you can specify where with the `-p` option.

The instance will be kept there for some time (specified in `plz.config.json`)
in case you're running things interactively (so that you don't need to wait
while the instance goes through the startup process again).

You can use `plz describe` to print metadata about an execution in json format.
It's useful to tell one execution from another if you have several running
at the same time.

You can use `plz run --parameters a_json_file.json` to pass parameters
to your program. Passing parameters this way has two advantages:
- the parameters are stored in the metadata and can be queried (see the
description of `plz history` below)
- you can use `plz rerun --override-parameters some_json_file.json` and run
exactly the same execution but with different parameters, which helps
running experiments in a systematic fashion.

There's also `plz history`, returning a json mapping from execution ids to
to metadata. If you write json files in a specific directory (see
`test/end-to-end/measures/simple`) they will be available in the metadata.
You can store there things you've measured during your experiment (for
instance, training loss). Parameters will be in the metadata as well, so
you can query the json output using, for instance, `jq` and get to see how
your training loss changed as you changed your parameters.

```
sergio@sergio:~/plz/examples/pytorch$ plz history | \
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

In this example, you can see that increasing the learning rate from
`0.01` to `0.1` gives you an improvement in accuracy from `98` to `98.5`,
but further increasing the learning rate leads to a disastrous decrease
to `13` (by the way, this is the classic digit recognition example using
LeNets, using a subset of the MNIST set. So this means only 13% of characters
recognised correctly).

You can do `plz list` to list the running executions and the instances that
are up in AWS. It also shows the instance ids. You can kill instances with
`plz kill -i <instance-id>`.

The command `plz last` is useful, particularly when writing shell commands,
to refer to the last execution _started_.

Finally, `plz rerun` allows you to rerun a job given an execution id.

### Functionality summary

This tool helps with a lot of tasks. Some of them are the ones you're used to do when running things in the cloud, or an experimentation environment:

1. Starts a "worker" (typically on AWS EC2, but also locally) to run your job.
2. Packages your code, parameters and data and ships them to the worker.
3. Runs your code.
4. Saves the results (like losses) and outcomes (like models) so that you can back to them in the future.
5. Takes down the worker.

 `plz` just automates those tasks for you.

It also:

6. Reruns previous jobs as to make sure the results are repeatable.
7. Provides a history including the result and parameters, so that you have experiment data in a structured format. 

We build `plz` following these principles:

- Code and data must be stored for future reference.
- Whatever part of the running environment can be captured by `plz`, we capture
it as to make jobs repeatable.
- plz functionality is based on standard mechanisms like files and environment
variables. You don't need to add extra dependencies to your code or learn
how to read/write your data in specific ways.
- The tool must be flexible enough so that no unnecessary restrictions are
imposed by the architecture. You should be able to do with `plz` whatever you
can do by running a container manually. It was surprising to find out how
many issues, mostly around running jobs in the cloud, could be solved only
by tweaking the configuration, without requiring any changes to the code.

`plz` is routinely used at `prodo.ai` to train ML models in the cloud, some
of them taking days to run in the most powerful instances available. We trust
it to start and terminate these instances as needed, and to get us the best
price.

## How does it work?

There is a service called `controller`, and a command-line interface (CLI) that
performs requests to the controller. The CLI is an executable `plz` accepting
operation arguments, so that you type `plz run`, `plz stop`, `plz list`, etc.

There are two configurations of the controller that are ready for you to use:
in one of them your jobs are run locally, while in the other one an aws instance
is started for each job. (Note: the controller itself can be deployed to the
cloud --and if you're in a production environment that's the recommended way
to use it--, but we suggest you try the examples with a controller that runs
locally first.)

When you have a directory with source code, you can just add a `plz.config.json`
file including information such as:
- The command you want to run
- The location of your input data
- Whether you want to request for an instance at fix price, or bid for spot
  instances, how much money you want to bid, etc.

Then, just typing `plz run` will run the job for you, either locally or in
aws, depending on the controller you've started.


## Installation instructions

Chances are you that you have most of the supporting tools already
installed, as these are broadly used tools. 

A full list of instructions for Ubuntu is listed below (we've used the tool in
both Ubuntu and Mac), but in summary you need to: install docker; install
docker-compose; install the aws CLI, and configure it with your Access key;
`git clone https://github.com/prodo-ai/plz.git`; install the cli by running 
`./install_cli` inside the `plz/` directory; run the controller with a script
we provide.

### Local configuration

One of the available configurations for the controller runs the jobs in the
current machine (another one uses AWS). We recommend trying the examples with
the local configuration first.

The following instructions suffice as to get the local controller working on a
fresh Ubuntu 18.04 installation.

*Note: the command `./start_local_controller` will take some time the first
time it's run, as it downloads a whole pytorch environment to be used by docker,
including anaconda and a lot of bells and whistles*


```
# Install basic packages we need

sudo apt update
sudo apt install -y curl git python-pip python3-pip awscli

# Install docker

curl -fsSL get.docker.com -o get-docker.sh
chmod u+x get-docker.sh
./get-docker.sh
sudo usermod -aG docker $USER

# Install docker compose

sudo curl -L https://github.com/docker/compose/releases/download/1.21.2/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone plz

git clone https://github.com/prodo-ai/plz.git

cd plz

# Install the cli

./install_cli

# Start a new terminal so that the current user is in the docker group,
# and the plz executable is in the path (pip3 will put it in $HOME/.local/bin)

sudo su - $USER

# If you executed the previous command, you're not inside plz/ anymore

cd plz

# Check that docker works (you should see a possibly empty list of images,
# and not a permission or connection error)

docker ps

# Start the local controller. Instructions for the controller that uses AWS are
# detailed below. This runs detached and spits the output to the terminal.
# You might want to run it in a different terminal (remember `cd plz/`).

./start_local_controller

```

The controller can be stopped at any time with:
```
./stop_controller
```


### AWS configuration

You need to do all the steps listed above for the local configuration, except
for the last one starting the local controller. The additional steps for using
AWS are below.

*Note: the command
`./start_aws_controller` will take some time the first time it's run, as it
downloads a whole pytorch environment to be used in docker (unless you've run
the local configuration before) and also uploads that your AWS infrastructure
so that it's ready for your instances to use*

*Note: if you usually use AWS in a particular region, please edit
aws_config/config.json and set your region there. The default file sets the
region to eu-west-1, Ireland.*


```
# Configure access to AWS.
# You'll need your access key. You can get it from the AWS console.
# In the top bar, click on your name, then `My security credentials`, then
# create one in `Access keys`
# You only need to set the access key ID and the secret access key

aws configure

# Check that AWS works. You should see a possibly empty list of instances

aws ec2 describe-instances --region eu-west-1

# Start the AWS controller. This runs detached and spits the output to the
# terminal. You might want to run it in a different terminal (remember
# `cd plz/`). Remember to edit `aws_config/config.json` to set your region,
# unless you want eu-west-1.

./start_aws_controller
```

## Examples

*Note: if you want to run the examples using the AWS instances, be aware that
this has a cost. You can change the value of
`"max_bid_price_in_dollars_per_hour": N` in `plz.config.json` to any value
you like. Examples takes around 5 minutes to run.
The value in the provided configs range from 0.5 dollars/hour to 2 dollars/hour
(for GPU-powered machines). See the following note as well.*

*Note: unless you add `"instance_max_uptime_in_minutes": null,` to your
`plz.config.json`, all AWS instances you start terminate after 60 minutes.
That's on purpose, in case you're just trying the tool and something doesn't
go well (like, there's a power cut). You can always use `plz list` and
`plz kill` before leaving your computer, as to make sure that there no
instances remaining. For maximum assurance, you can check your instances in
the AWS console.*


### Pytorch

In the directory `plz/examples/pytorch` there's a full-fledged example
for the task of digit recognition using the classic approach of
LeNets and a subset of the well-known MNIST dataset. There's also a simple
example using only python, described in the section below.

Anything related to `plz` is in `main.py`. In fact the most relevant lines
are the following ones:

```
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
This shows how to get the input data and parameters that `plz` uploads
for you. There's a configuration file whose name comes in the environment
variable `CONFIGURATION_FILE`. If that variable is present, you're running
with `plz`, and you can read and parse the file as a json object. The object
has the following keys:
- `input_directory` is a directory where you'll find your input data. If
you have `"input": "file://../data/mnist",` in your `plz.config.json` file,
the directory `config[input_directory]` will have the same contents that
`../data/mnist/` has locally.
- `output_directory` is directory where you can write files. These are
retrieved via `plz output`, or downloaded if you keep the CLI running
until the end of the job
- `parameters` is the json object that you passed with `plz run --parameters
a_json_file.json`, if you so did. Otherwise it's an empty object
- `measures_directory` is a directory so that each file is interpreted as
an entry in a json object, with the key being the file name and the value
the content of the file, interpreted as a json object. By writing the code
```
    with open(os.path.join(measures_directory, f'epoch_{epoch:2d}'), 'w') as f:
        json.dump({'training_loss': training_loss, 'accuracy': accuracy}, f)
```
you can then run:
```
sergio@sergio-asus:~/plz/examples/pytorch$ plz measures
{
  "epoch_ 1": {
    "training_loss": 2.1326301097869873,
    "accuracy": 45.4
  },
  "epoch_ 2": {
[...]
```
- `summary_measures_path` is a path to a file in which you can write
a json object with a summary of the results you obtained in your run
(best accuracy, total training time, etc.). The summary is available
via `plz measures -s`, and also printed by the CLI if you wait until the
job finishes.

If you want to use CUDA for this example, you can do:
```
plz -c plz.cuda.config.json run
```
to use a config file that tells docker to use the cuda runtime.
If you're running the controller that run jobs locally (as opposed to
AWS) to might need to install the NVIDIA docker runtime (see
`https://github.com/NVIDIA/nvidia-docker`).

### Python

In the directory `plz/examples/python` there is a minimal example showing
how to do input and output with `plz`. Doing just `plz run` should start the
job.


## Future work

In the future, `plz` is intended to:

* add support for names inputs and outputs, and function as a ``build system
in the cloud``, particulary suitable to build pipelines
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
   export SECRETS_DIR="${PWD}/secrets"
   ```
4. Create a configuration file named *secrets/config.json* based on *example.config.json*.
5. Run `make deploy`.

### Deploying a production environment

Do just as above, but put your secrets directory somewhere else (for example, another repository, this one private).
