(Other commands TBD)

## plz kill

Kills instances specified via the different options.

Instances can either be specified with `-i instance-id1 instance-id2 ...`
or with `--all-of-them-plz` which removes all instances used by the current
user (or instances used by any user if `--berserk` is specified).

Options are designed as to minimise the possibility of killing an instance
by mistake. As a consequence:
- If you are specifying instances individually with `-i`, you might want
  to kill only idle instances, and `--force-if-not-idle` is required to
  kill instances doing any actual work (as to prevent you to kill something
  you care about). If the instance is running an execution for another user,
  you need to set `--berserk`
- If you are specifying instances with `--all-of-them-plz`, it will kill the
  instances running an execution for the current user. Since they are running,
  they are not idle, so `--force-if-not-idle` is not needed in this case
- If you want to kill idle instances as well, in addition to
  `--all-of-them-plz` you need to set `--including-idle`. Idle
  instances do not ''belong'' to any user (if any user starts a job and
  there's a compatible idle instance, that instance will be used). Also,
  instances in which an execution is being started (but not running yet) are
  also considered idle, and so by killing an idle instance you might be
  actually slightly annoying some other user (depending on the stage, it's
  likely that plz retries getting an instance for the other user, but if
  you're unlucky the user will need to retry running)
- When using `--all-of-them-plz` you'll be asked for confirmation, unless
  you specify `--oh-yeah`

The one-liner to kill all instances is then:

`plz kill --all-of-them-plz --including-idle --berserk --oh-yeah`
