
satori_rtm_cli.py
=================

This is a debugging and exploration tool for [Satori](https://www.satori.com) RTM.

Common flags
------------

* endpoint -- default is 'wss://open-data.api.satori.com', so there's no need to specify an endpoint when reading from open channels
* appkey
* role_name
* role_secret
* verbosity -- from 0 (the least chatty) to 3 (the most chatty), default is 2 (quite chatty)

Run `satori_rtm_cli.py --help` for full help on flags.

Example usage
-------------

Examples assume that $MY_ENDPOINT, $MY_APPKEY and $MY_CHANNEL have valid values.

### Read single message and exit

```
satori_rtm_cli.py --appkey=$MY_APPKEY read big-rss
```

### Subscribe (human-friendly output)

```
satori_rtm_cli.py --appkey=$MY_APPKEY --prettify_json subscribe big-rss
```

### Filter

```
satori_rtm_cli.py --appkey=$MY_APPKEY --prettify_json filter 'select * from `big-rss` where title like "%Japan%" or title like "%Korea%"'
```

### Record (machine-friendly output, every line is a JSON object)

```
# record to stdout (press Control-C to stop)
satori_rtm_cli.py --appkey=$MY_APPKEY record big-rss

# record to file (press Control-C to stop)
satori_rtm_cli.py --appkey=$MY_APPKEY -o big-rss.recording record big-rss

# replay big-rss recording to $MY_CHANNEL
satori_rtm_cli.py --endpoint=$MY_ENDPOINT --appkey=$MY_APPKEY replay -i big-rss.recording --override_channel=$MY_CHANNEL
```


### Publish

```
# publish a single JSON object message
echo '{"coords": {"x": 0.0, "y": 0.0}}' | satori_rtm_cli.py --endpoint=$MY_ENDPOINT --appkey=$MY_APPKEY publish $MY_CHANNEL

# publish a single string message
echo "Hello" | satori_rtm_cli.py --endpoint=$MY_ENDPOINT --appkey=$MY_APPKEY publish $MY_CHANNEL

# publish a few messages
echo "Hello\nHallo\nCiao" | satori_rtm_cli.py --endpoint=$MY_ENDPOINT --appkey=$MY_APPKEY publish $MY_CHANNEL

# publish a few messages from a file
echo "Hello\nHallo\nCiao" > hello.txt
satori_rtm_cli.py --endpoint=$MY_ENDPOINT --appkey=$MY_APPKEY -i hello.txt publish $MY_CHANNEL
```

### Key-value

```
# write
echo '{"coords": {"x": 0.0, "y": 0.0}}' | satori_rtm_cli.py --endpoint=$MY_ENDPOINT --appkey=$MY_APPKEY write $MY_CHANNEL

# read
satori_rtm_cli.py --endpoint=$MY_ENDPOINT --appkey=$MY_APPKEY read $MY_CHANNEL

# delete
satori_rtm_cli.py --endpoint=$MY_ENDPOINT --appkey=$MY_APPKEY delete $MY_CHANNEL
```
