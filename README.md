# plz 😸

*Say the magic word.*

`plz` is a job runner targetted at training machine learning models as simply, tidely and cheaply as possible. You can run jobs locally or in the cloud. At the moment `plz` is optimised for `pytorch`, in the sense that you can run pytorch programs without preparing a `pytorch` environment. With proper configuration and preparation it is fairly general, and can be used for practically anything that requires running a job in a repeatable fashion on a dedicated cloud VM.

*We are in beta stage. We don't expect API stability or consistence with forthcoming versions*

### Functionality

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
