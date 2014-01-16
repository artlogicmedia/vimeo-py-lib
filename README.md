# vimeo-py-lib

This library provides a `vimeo` Python (2.5-2.7) module for interacting with the
Vimeo Advanced API (v2). It is heavily based on
(Vimeo's own PHP library)[https://github.com/vimeo/vimeo-php-lib] for the same
purpose.

## Dependencies

If you are running Python 2.6 or 2.7, the only dependencies are having either
[setuptools](https://pypi.python.org/pypi/setuptools) or
[ez_setup](https://pypi.python.org/pypi/ez_setup) installed on your system.

If you are using this on Python 2.5 you will need to install a JSON parsing
library. By default the module will attempt to import the names `json` (looking
for the stdlib module in 2.6+) or `cjson`, which is
[available on PyPi](https://pypi.python.org/pypi/python-cjson).

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

## TODO/caveats/warnings

* I currently don't like the fact that this is using a roll-yer-own OAuth
  implementation (copied from Vimeo's, but still). Will migrade to the `oauth2`
  module as soon as time permits.
* The verification of uploads is using the `vimeo.videos.upload.verifyChunks`
  method, instead of proper streaming verification (which involves repeating the
  `PUT` used to upload the video and checking the response headers). This is not
  optimal, and it means that resuming interrupted uploads isn't supported.
* Support for arbitrary caching methods, by passing in functions for saving and
  loading from the cache, might be nice. This would enable database/session
  caching of requests, which would be better for some apps.