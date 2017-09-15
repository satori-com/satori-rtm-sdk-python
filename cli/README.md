
satori-rtm-cli
==============

This is a debugging and exploration tool for [Satori](https://www.satori.com) RTM.

Installation
------------

It's available from PyPI:

```
pip install satori-rtm-cli
```

If you only have `pip3` on your system, `pip3 install satori-rtm-cli` works too.
In general, any command using `pip` in this README is `pip3`-compatible.

If that command failed or `satori-rtm-cli` has not become available in your
shell, see [Troubleshooting](#troubleshooting).

Common flags
------------

* endpoint -- default is 'wss://open-data.api.satori.com', so there's no need to specify an endpoint when reading from open channels
* appkey
* role_name
* role_secret
* verbosity -- from 0 (the least chatty) to 3 (the most chatty), default is 2 (quite chatty)
* config -- path to config file, default is $XDG_CONFIG_HOME/satori/rtm-cli.config (usually this is "$HOME/.config/satori/rtm-cli.config")

Run `satori-rtm-cli --help` for full help on flags including shorthands like `-e` for `--endpoint`.

Config file format
------------------

```
# Comments start with '#'

# If --key is a flag that satori-rtm-cli can take
# Then configuring it here looks like this:
#     key = "value"

# For example, this is how you configure endpoint and appkey:
endpoint = "wss://open-data.api.satori.com"
appkey = "YOUR_APPKEY"

# Example of an option for integer value:
verbosity = 3

# Same for boolean
prettify_json = true
```

Example usage
-------------

Examples assume that $MY_ENDPOINT, $MY_APPKEY and $MY_CHANNEL have valid values.

### Read single message and exit

```
satori-rtm-cli --appkey $MY_APPKEY read big-rss
```

### Subscribe (human-friendly output)

```
satori-rtm-cli --appkey $MY_APPKEY --prettify_json subscribe big-rss
```

```
# subscribe to a private channel from a specific position
satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY --position 12345678:012 --prettify_json subscribe big-rss
```

```
# include 10 last messages when subscribing
satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY --count 10 --prettify_json subscribe big-rss
```

```
# include 5 last seconds worth of messages when subscribing
satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY --age 5 --prettify_json subscribe big-rss
```

### View

```
satori-rtm-cli --appkey $MY_APPKEY --prettify_json view 'select * from `big-rss` where title like "%Japan%" or title like "%Korea%"'
```

### Record (machine-friendly output, every line is a JSON object)

```
# record to stdout (press Control-C to stop)
satori-rtm-cli --appkey $MY_APPKEY record big-rss

# record to file (press Control-C to stop)
satori-rtm-cli --appkey $MY_APPKEY -o big-rss.recording record big-rss

# replay big-rss recording to $MY_CHANNEL
satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY replay -i big-rss.recording --override_channel $MY_CHANNEL

# replay big-rss recording to $MY_CHANNEL at half speed
satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY replay --rate 0.5x -i big-rss.recording --override_channel $MY_CHANNEL

# replay big-rss recording to $MY_CHANNEL at triple speed
satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY replay --rate 3x -i big-rss.recording --override_channel $MY_CHANNEL

# replay big-rss recording to $MY_CHANNEL at as fast as possible
satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY replay --rate unlimited -i big-rss.recording --override_channel $MY_CHANNEL

# replay big-rss recording to $MY_CHANNEL five times
satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY replay --loop 5 -i big-rss.recording --override_channel $MY_CHANNEL

# replay big-rss recording to $MY_CHANNEL in a loop forever
satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY replay --loop inf -i big-rss.recording --override_channel $MY_CHANNEL
```


### Publish

```
# publish a single JSON object message
echo '{"coords": {"x": 0.0, "y": 0.0}}' | satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY publish $MY_CHANNEL

# publish a single string message
echo "Hello" | satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY publish $MY_CHANNEL

# publish a few messages
echo "Hello\nHallo\nCiao" | satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY publish $MY_CHANNEL

# publish a few messages from a file
echo "Hello\nHallo\nCiao" > hello.txt
satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY -i hello.txt publish $MY_CHANNEL

# publish json messages from a file ([jq](https://stedolan.github.io/jq/) is used to convert file to value-per-line format)
# $ cat messages
# {"key1": "value",
#          "key2": "foo"
#     }
# ["array", "of",
#  "stuff"]
jq -c . messages | satori-rtm-cli -e $MY_ENDPOINT -a $MY_APPKEY publish $MY_CHANNEL

# publish a message every 5 seconds to create some activity in the channel
while true; do echo "mymessage" | satori-rtm-cli -e $MY_ENDPOINT -a $MY_APPKEY publish $MY_CHANNEL && sleep 5; done
```

### Key-value

```
# write
echo '{"coords": {"x": 0.0, "y": 0.0}}' | satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY write $MY_CHANNEL

# read
satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY read $MY_CHANNEL

# delete
satori-rtm-cli --endpoint $MY_ENDPOINT --appkey $MY_APPKEY delete $MY_CHANNEL
```

Troubleshooting
---------------

Note: when trying different ways to install satori-rtm-cli (or any python package)
      beware that pip will NOT reinstall it by default, even if installation flags differ.
      You'll likely have to uninstall it first to try another way of installing:

```
pip uninstall satori-rtm-cli
pip install --some --new -flags satori-rtm-cli
```

---

Problem: satori-rtm-cli package failed to install

Symptom: `pip show -f satori-rtm-cli` has empty output

The most frequent reason for `pip install satori-rtm-cli` failing is permissions problem.
There are multiple choices here:

1. Install the package as root. The upside is that `sudo pip install` usually
   installs scripts in a location that's already on PATH, meaning
   `satori-rtm-cli` will become available in your shell. A notable exception
   is pip from MacPorts, it installs scripts deeply into its internal directory
   so you can't run them immediately after installation.

2. Install the package somewhere in the user directory. This `somewhere` is different
   based on OS and Python installation. To see what it is on your system, run:

```
pip install --user satori-rtm-cli
```

3. Install the script into a specific directory (that is in your PATH and is writable by you).
   For example if such a directory is $HOME/bin, run:

```
pip install --user --install-option="--install-scripts=$HOME/bin" satori-rtm-cli
```

---

Problem: satori-rtm-cli package installed successfully, but satori-rtm-cli is
         not available in the shell

Symptom: running `satori-rtm-cli` results in something like `bash: command
         not found: satori-rtm-cli`

There are two approaches to fixing it:

1. Add the location where script resides to your PATH. You can see this location
   by running `pip show -f satori-rtm-cli`

2. Uninstall satori-rtm-cli and install it again into a directory that already
   is in your PATH. For example, if desired destination directory is "$HOME/bin",
   install the package like this:

```
pip install --user --install-option="--install-scripts=$HOME/bin" satori-rtm-cli
```
