# vimeo-py-lib

This library provides a `vimeo` Python (2.5-2.7) module for interacting with the
Vimeo Advanced API (v2). It is heavily based on
[Vimeo's own PHP library](https://github.com/vimeo/vimeo-php-lib) for the same
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

### Differences from the PHP version

There are some minor differences from the PHP version of this library. They are
as follows:

* The depricated `uploadMulti` method has not been ported.
* The first argument of the `upload` method can be either a file path or a
  file-like object (like an open file or a `StringIO` instance or something).
  Basically anything with `read` and `seek` methods.
* This module also provides an in-memory cache for requests, which is just a
  dictionary within each `VimeoAPI` instance.

### Methods

* `VimeoClient.auth(permission = 'read', callback_url = 'oob')`
  <br>
  Return the authorization URL for the specified permission and callback URL.
  Additionally, this method will automatically get a new request token and set
  it as the active token for the VimeoClient instance. *permission* should be
  one of 'read', 'write', or 'delete'.

* `VimeoClient.call(method, params = None, request_method = 'GET',
  url = API_REST_URL, cache = True)`<br>
  Make an arbitrary API call. *params*, if provided, should be a dictionary of 
  request parameters. If the cache is active and you want this request to ignore
  it, set *cache* to `False`.

* `VimeoClient.enable_cache(type, path = '.', expire = 600)`
  <br>
  Enable the request cache. *type* should be either of the `CACHE_FILE` or
  `CACHE_MEMORY` values from this module. *path* specifies the location to write
  cache files if the file type is `CACHE_FILE`. *expire* specifies the number of
  seconds before cached data is considered stale. (Note that stale data is
  cleared on every request, but not between requests.)

* `VimeoClient.disable_cache()`
  <br>
  Disable the cache. This will not empty an existing cache data. If you want to
  empty the cache, call the *clear_cache()* method before calling this method.

* `VimeoClient.clear_cache(cache_type = None)`
  <br>
  Clear the cache. If the cache is active and *cache_type* is not specified, the
  cache type specified will be cleared (in the case of a file cache, all cache
  files will be removed; in the case of the in-memory cache, the dictionary
  storing cache values will be emptied). If the cache is not active and no cache
  type is specified, this method will do nothing. *cache_type* should be either
  of the `CACHE_FILE` or `CACHE_MEMORY` values from this module.

* `VimeoClient.get_access_token(verifier)`
  <br>
  Exchange the currently active request token (set with *set_token()* or
  *auth()*) for an access token using the *verifier* string provided by either a
  Vimeo callback redirection or user input.

* `VimeoClient.get_authorize_url(token, permission = 'read')`
  <br>
  Get a URL at which the user can authorize the given *token* string for the 
  given *permission* value. Unline the *auth()* method, above, this will not set
  any request tokens, merely return a string.

* `VimeoClient.get_request_token(callback_url = 'oob')`
  <br>
  Get a new request token from Vimeo to begin the authorization process.

* `VimeoClient.get_token()`
  <br>
  Get the currently active token. Returns a 2-tuple of `(token, token_secret)`.

* `VimeoClient.set_token(token, token_secret)`
  <br>
  Set a *token* and *token_secret* value as the currently active token.

* `VimeoClient.upload(file, replace_id = None, mimetype = None)`
  <br>
  Upload *file* to Vimeo, optionally replacing an existing video with the id
  *replace_id*. *file* can either be a file-like object (with *read* and *seek*
  methods) or a file path as a string. If the *mimetype* value is specified, the
  VimeoClient isntance will attempt to guess the MIME type using
  `mimetypes.guess_type`, which may not be very reliable unless *file* is
  provided as a file path. If the correct MIME type is not specified, you may
  run into issues uploading videos.

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