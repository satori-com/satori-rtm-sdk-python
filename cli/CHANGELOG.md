1.5.2 (2017-08-26)
------------------

* Fixed logging error in `replay --loop inf`

1.5.1 (2017-08-24)
------------------

* Added --loop option to replay subcommand
* replay subcommand now shows some stats

1.5.0 (2017-08-21)
------------------

* Added --position, --age and --count options for subscribe and view subcommands
* Added an undocumented feature

1.4.3 (2017-08-11)
------------------

* Silence the warning about missing config file unless --config option was explicitly used

1.4.2 (2017-08-05)
------------------

* Take options from a configuration file and from environment variables

1.3.0 (2017-07-29)
------------------

* Enabled --rate option of `replay` command to accept relative speed like `2x` and `0.5x`
* Added shortcuts for most options (like -e for --endpoint)
* Fixed the docstring regarding the default value of `--verbosity`

1.2.0 (2017-07-13)
------------------

* Renamed 'filter' command to 'view'
* Added 'period' option for 'view'

1.1.0 (2017-07-12)
------------------

Renamed to satori-rtm-cli (package name and executable name are now the same)

1.0.0
-----

Initial release