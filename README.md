# vimeo-py-lib

This library provides a `vimeo` Python (2.5-2.7) mdule that is a direct port of
(Vimeo's own PHP library)[https://github.com/vimeo/vimeo-php-lib].

This supports version 2 of the API.

## Dependencies

If you are running Python 2.6 or 2.7, the only dependencies are having either
[setuptools](https://pypi.python.org/pypi/setuptools) or
[ez_setup](https://pypi.python.org/pypi/ez_setup) installed on your system.

If you are using this on Python 2.5 you will need to install a JSON parsing
library. By default the module will attempt to import the names `json` (looking
for the stdlib module in 2.6+) or `cjson`, which is
[available on PyPi](https://pypi.python.org/pypi/python-cjson).

## Development dependencies

[Nose](https://pypi.python.org/pypi/nose/) is required for running the automated
tests.

## API

### How to use

Coming soon. In the meantime, refer to the PHP documentation and the list of
differences below.

### Differences from the PHP version

There are some minor differences from the PHP version of this library. They are
as follows:

* The depricated `uploadMulti` method has not been ported.
* The first argument of the `upload` method can be either a file path or a file-
  like object (like an open file or a `StringIO` instance or something).
  Basically anything with `read` and `seek` methods.
* This module also provides an in-memory cache for requests, which is just a
  dict within the `VimeoAPI` instance.

## Bugs

Please file any bugs you find on the Github issues page for this project.