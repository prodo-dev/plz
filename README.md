# plz 😸

*Say the magic word.*

`plz` is a job runner targeted at training machine learning models as simply, tidily and cheaply as possible. You can run jobs locally or in the cloud. At the moment `plz` is optimised for `pytorch`, in the sense that you can run pytorch programs without preparing a `pytorch` environment. With proper configuration and preparation it is fairly general, and can be used for practically anything that requires running a job in a repeatable fashion on a dedicated cloud VM.

*We are in beta stage. We don't expect API stability or consistence with
next versions.*

## Usage overview

We offer more details below on how to setup `plz` and run your jobs, but we can
start by giving you an overview of what `plz` does.

`plz` offers a command-line interface. You can add a `plz.config.json` file
to the directory where you have your source code. This file contains, among
other things, the command you run to put your program to work (for instance,
`python main.py`). Then, you can run commands like `plz run`:

```
sergio-prodo@sergio:~/plz/examples/python$ plz run
👌 Capturing the files in /home/sergio-prodo/plz/examplespython
👌 Building the program snapshot
Step 1/4 : FROM python:3-slim
 ---> 7bf3b26249fa
[...]
Removing intermediate container 08951133db14
 ---> 8c7fceb87231
Successfully built 8c7fceb87231
Successfully tagged plz/builds:some-person-trying-trying-a-project-1531847873426
👌 Capturing the input
👌 147 input bytes to upload
👌 Sending request to start executio
Instance status: querying availability
Instance status: requesting new instance
Instance status: waiting for the instance to be ready
Instance status: pending
[...]
👌 Execution ID is: 58a80ffa-89e5-11e8-a1ca-2554f21c13fe
👌 Streaming logs...
Running with plz!
We are in the quest of finding a mysterious value for k.
The value happens to be 1/3, but don't tell anyone.
Running with plz!
k: 0.0
k: 0.54
Best model so far! Saving
k: 0.5344
[...]
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

You can be patient and wait until it works, but you can also hit `Ctrl-C` and
stop the program early:

```
k: 0.5209
^C
👌 Your program is still running. To stream the logs, type:

        plz logs ad96b586-89e5-11e8-a7c5-8142e2563487
```

`plz` runs your commands in a Docker container, either in your AWS
infrastructure or in your local machine, so what you do in the terminal
doesn't really matter. If you are running this execution only, you can just
type `plz logs` and logs will be streamed, not from the beginning
but since the current time (unless you specify `--since start`).

The big
hexadecimal number you see in the output, next to `plz logs`, is the execution
ID you can use to refer to this execution. `plz` remembers the last execution
that was *started* and if you want to refer to that one you don't need to
include it in our command. But if you need to specify the execution id,
you can do `plz logs <execution_id>`.

Once your program has finished (or once you have stopped with `plz stop`) you
can do `plz output`, and it will download the files that your program has
written (you need to tell your program to write in a specific directory. `plz`
sets an environment variable that you can use as to know where to write).
The files are saved under `output/<execution_id>`.

`plz output` is also executed if the program finishes:
```
k: 0.3333
Best model so far! Saving
k: 0.3333
k: 0.3333
👌 Harvesting the output...
👌 Retrieving summary of measures (if present)...
👌 Execution succeeded.
👌 Retrieving the output...
model.json
👌 Done and dusted.
```

The instance will be kept there for some time (specified in `plz.config.json`)
in case you're running things interactively (so that you don't need to wait
while the instance goes through the startup process again).

Use `plz describe` to print metadata about executions.

You can use `plz run --parameters a_json_file.json` to pass parameters.
See `test/end-to-end/parameters/simple` as to see how to access those
parameters from your program. Passing parameters this way has the advantage
that the parameters are stored in the metadata and can be queried.

There's also `plz history`, returning a json mapping from execution ids to
to metadata. If you write json files in a specific directory (see
`test/end-to-end/measures/simple`) they will be available in the metadata.
You can store there things you've measured during your experiment (for
instance, training loss). Parameters will be in the metadata as well, so
you can query that json using, for instance, `jq` and get to see how
your training loss changed as you changed your parameters.

You can do `plz list` to list the running executions. It also shows the instance
ids. You can kill instances with `plz kill -i <instance-id>`.

Finally, `plz rerun` allows you to rerun a previous job.

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

There is a service called controller, and a command-line interface (CLI) that
perform requests to the controller. The CLI is an executable `plz` accepting
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

What you need to install are broadly used tools. Chances are you already
have most of the these tools installed.

A full list of instructions for Ubuntu is listed below (we use the tool in both
Ubuntu and Mac), but in summary you need to: install docker; install
docker-compose; install the aws CLI, and configure it with your Access key;
`git clone https://github.com/prodo-ai/plz.git`; install the cli by running 
`./install_cli` inside the `plz/` directory; run the controller with a script
we provide.

### Local configuration

One of the avaialble configurations for the controller runs the jobs in the
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

You need to do all the steps above, except for starting the controller. The
additional steps for using AWS are below.

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

## Example

In the directory `plz/examples/python` there is a minimal example showing
how to do input and output with `plz`. You can also see the directory
`plz/tests/end-to-end` for examples on how to use parameters and measures,
which this documentation doesn't cover yet.

*Note: if you want to run the example using the AWS instances, be aware that
this has a cost. You can change the value of
`"max_bid_price_in_dollars_per_hour": N` in `plz.config.json` to any value
you like. The value in the provided file is 0.5 dollars/hour. See the
following note as well. The example takes around 5 minutes to run.*

*Note: unless you add `"instance_max_uptime_in_minutes": null,` to your
`plz.config.json`, the instance terminates after 60 minutes.  That's on
purpose, in case you're just trying the tool and something doesn't go well
(like, there's a power cut). You can always use `plz list` and `plz kill`
before leaving your computer, as to make sure that there no instances remaining.
For maximum assurance, you can check your instances in the AWS console.*

If you've followed the installation instructions, doing just
`plz run` should start the work.

In case you want to use pytorch, you can run an alternative configuration
file with `plz -c plz.pytorch.config.json`. This file uses a different
base image (`prodoai/plz_ml-pytorch`), uses an instance type with a gpu
(`p2.xlarge`) and increases the bid price to 2 dollars/hour.


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
