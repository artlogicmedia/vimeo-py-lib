"""
vimeo-py-lib v0.0.1
https://github.com/artlogicmedia/vimeo-py-lib

This module provides a (nearly) straight port of the phpVimeo class in Vimeo's
vimeo-php-lib library (https://github.com/vimeo/vimeo-php-lib).

For a full description of the API methods and a general overview of how to use
this module, see the included README.md file.

Copyright (c) 2014 Artlogic Media Ltd. http://artlogic.net
Released under the MIT or GPLv3 licenses.
"""

from __future__ import with_statement

import binascii
import hashlib
import hmac
import mimetypes
import os
import socket
import string
import time
import urllib
import urllib2
import uuid

try:
    import urlparse
    parse_qs = urlparse.parse_qs
except AttributeError:
    import cgi
    parse_qs = cgi.parse_qs

try:
    import cPickle
    pickle = cPickle
except ImportError:
    # Respect for alternate implementations
    import pickle

try:
    import cjson
    def json_decode(data):
        # `cjson.decode` handles escaped '/' characters differently from the
        # stdlib module, and doesn't unescape forward-slashes that Vimeo's API
        # escapes.
        return cjson.decode(data.replace('\/', '/'))
except ImportError:
    try:
        import json
        json_decode = json.loads
    except ImportError:
        raise ImportError("Could not find a json library to import.")

__all__ = ['VimeoClient', 'VimeoAPIError']

# Data values used as defaults
API_REST_URL = 'http://vimeo.com/api/rest/v2'
API_AUTH_URL = 'http://vimeo.com/oauth/authorize'
API_ACCESS_TOKEN_URL = 'http://vimeo.com/oauth/access_token'
API_REQUEST_TOKEN_URL = 'http://vimeo.com/oauth/request_token'

CACHE_FILE = 'file'
CACHE_MEMORY = 'memory'

# Strip these parameters from requests when caching
CACHE_DROP_PARAMETERS = ('oauth_nonce', 'oauth_signature', 'oauth_timestamp')

class VimeoAPIError(Exception):
    """
    A subclass of Exception that provides the api method, error code, and error
    message of the API response.
    """

    def __init__(self, method = '', code = '', msg = ''):
        self.method = method
        self.code = code
        self.msg = msg

    def __str__(self):
        return " (%s) %s %s" % (self.method or 'None', self.code, self.msg)

class VimeoClient(object):

    _app_name = None

    _cache_dir = None
    _cache_enabled = None
    _cache_expire = 600

    _consumer_key = None
    _consumer_secret = None

    _token = None
    _token_secret = None

    _urlopener = urllib2.build_opener(urllib2.HTTPHandler)

    def __repr__(self):
        app = ''
        if self._app_name:
            app = '-%s' % self._app_name
        return "<VimeoClient%s: %s>" % (app, self._consumer_key)

    def __init__(self,
        consumer_key,
        consumer_secret,
        token = None,
        token_secret = None,
        app_name = None):

        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._app_name = app_name or ''

        if token and token_secret:
            self.set_token(token, token_secret)

    def _cache(self, params, response_data):
        """
        Cache an API response based on a hash of the parameters (minus certain
        request-specific ones).
        """
        params = params.copy()
        # Remove some unique things
        for i in CACHE_DROP_PARAMETERS:
            if i in params:
                del params[i]

        params = urllib.urlencode(params)
        hash = hashlib.md5(params).hexdigest()

        if self._cache_enabled == CACHE_FILE:
            f = os.path.join(self._cache_dir, hash, '.cache')
            with open(f, 'w') as f:
                pickle.dump(response_data, f)
        elif self._cache_enabled == CACHE_MEMORY:
            self._memory_cache[hash] = (response_data, time.time())

    def _generate_auth_header(self, oauth_params):
        """
        Create the "Authorization" HTTP header for a set of OAuth params.
        Returns a dict.
        """
        auth_header = 'OAuth realm=""'

        for k, v in oauth_params.items():
            vals = map(self._url_encode_rfc3986, (k, str(v)))
            auth_header += ',%s="%s"' % tuple(vals)

        return {'Authorization': auth_header}

    def _generate_nonce(self):
        """
        Generate a nonce for the call, returned as a string. This nonce is an
        MD5 hash of a UUID value. The MD5 is unnecessary, but used to keep the
        format and length consistent with other strings in the request.
        """
        uid = str(uuid.uuid4())
        return hashlib.md5(uid).hexdigest()

    def _generate_signature(self,
        params,
        request_method = 'GET',
        url = API_REST_URL):
        """
        Generate the OAuth signature from the request information. This method
        is copied straight from the Vimeo PHP class, but will hopefully be
        replaced with an existing implementation (like the `oauth2` module) at
        some point in the future.
        """

        keys = sorted(params.keys())
        params = self._url_encode_rfc3986(params)

        # Make sure we iterate the dict in sorted order. We aren't using
        #  collections.OrderedDict here because we want to support 2.5+.
        items = [(k, params[k]) for k in keys]
        querystring = urllib.urlencode(items)

        # Make the base string
        base_parts = (
            request_method.upper(),
            url,
            urllib.unquote(querystring),
        )
        base_parts = self._url_encode_rfc3986(base_parts)
        base_string = '&'.join(base_parts)

        # Make the key
        key_parts = (
            self._consumer_secret,
            self._token_secret or '',
        )
        key_parts = self._url_encode_rfc3986(key_parts)
        key = '&'.join(key_parts)

        # Generate signature
        hashed = hmac.new(key, base_string, hashlib.sha1)
        return binascii.b2a_base64(hashed.digest())[:-1]

    def _get_cached(self, params):
        """
        Return the contents of a cached request, or None if the request is not
        already in the cache.
        """
        # Remove some unique things
        params = params.copy()
        for i in CACHE_DROP_PARAMETERS:
            if i in params:
                del params[i]

        params = urllib.urlencode(params)
        hash = hashlib.md5(params).hexdigest

        if self._cache_enabled == CACHE_FILE:
            f = os.path.join(self._cache_dir, hash, '.cache')
            # Check to see if the cache file is expired and remove it
            last_modified = os.path.getmtime(f)
            if f.endswith('.cache') and \
            last_modified + self._cache_expire < time.time():
                os.remove(f)
            if os.path.exists(f):
                with open(f) as f:
                    return pickle.load(f)
        elif self._cache_enabled == CACHE_MEMORY:
            for k, v in self._memory_cache.items():
                _, last_modified = v
                if last_modified + self._cache_expire < time.time():
                    del self._memory_cache[k]
            return self._memory_cache.get(hash)

    def _parse_token_string(self, tokenstring):
        """
        Parse the token string format into a dict. (Token strings are serialized
        in GET/POST-like format).
        """
        # Do this more manually for 2.5 support.
        params = parse_qs(tokenstring)
        for k, v in params.items():
            if len(v) == 1:
                params[k] = v[0]
            elif len(v) == 0:
                params[k] = None
        return params

    def _request(self,
        method,
        call_params = None,
        request_method = 'GET',
        url = API_REST_URL,
        cache = True,
        use_auth_header = True):
        """
        Call an API method. If the cache is enabled and you want to force the
        request to skip the cache, set the 'cache' parameter to False.

        In the future, this will hopefully be modified to use an existing OAuth
        request library, like the requests provided in `oauth2` library.
        """
        if call_params is None:
            call_params = {}
        request_method = request_method.upper()

        # Prepare oauth arguments
        oauth_params = {
            'oauth_consumer_key': self._consumer_key,
            'oauth_version': '1.0',
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_timestamp': int(time.time()),
            'oauth_nonce': self._generate_nonce(),
        }

        # If we have a token, include it
        if self._token:
            oauth_params['oauth_token'] = self._token

        # Regular args
        api_params = {'format': 'json'}
        if method:
            api_params['method'] = method

        # Merge args
        for k, v in call_params.items():
            if 'oauth_' in k and k.index('oauth_') == 0:
                oauth_params[k] = v
            elif v is not None:
                api_params[k] = v

        # Generate the signature
        signature_params = dict(oauth_params.items() + api_params.items())
        oauth_params['oauth_signature'] = self._generate_signature(
                                        signature_params, request_method, url)

        # Merge all args
        all_params = dict(oauth_params.items() + api_params.items())

        # Return cached value
        if self._cache_enabled:
            response_data = self._get_cached(all_params)
            if cache and response_data:
                return response_data

        # Request options
        if use_auth_header:
            params = api_params
        else:
            params = all_params

        if request_method == 'GET':
            request_url = url + '?' + urllib.urlencode(params)
        elif request_method == 'POST':
            request_url = url

        # The Vimeo API blocks many common UAs, so we want to set up a unique
        # one.
        headers = {
            'User-Agent': "vimeo-py-lib/%s" % self._app_name
        }
        if use_auth_header:
            headers.update(self._generate_auth_header(oauth_params))

        if request_method == 'POST':
            request = urllib2.Request(request_url, urllib.urlencode(items),
                        headers = headers)
        else:
            request = urllib2.Request(request_url, headers = headers)

        try:
            response = urllib2.urlopen(request, timeout = 30)
        except TypeError:
            # Old version of Python that doesn't accept a timeout argument
            old_default = socket.getdefaulttimeout()
            socket.setdefaulttimeout(30)
            response = urllib2.urlopen(request)
            # Set it back immediately so that we don't screw anything up. I
            # don't think this is thread-safe.
            socket.setdefaulttimeout(old_default)

        if method:
            response_data = response.read()
            response_data = json_decode(response_data)

            # Cache the response
            if self._cache_enabled and cache:
                self._cache(all_params, response_data)

            if response_data.get('stat') == 'ok':
                return response_data
            else:
                error = response_data.get('err')
                raise VimeoAPIError(method, error.get('code'),
                                            error.get('msg'))
        else:
            return response.read()

    def _url_encode_rfc3986(self, input):
        """
        Internal utility function to URL encode a parameter or dict of
        parameters.
        """
        if isinstance(input, dict):
            input = input.copy()
            for k, v in input.items():
                input[k] = urllib.quote(str(v), safe = '')
            return input
        # Purposefully want this to fail a string. Cover all other iterables.
        elif hasattr(input, '__iter__'):
            return [urllib.quote(str(i), safe = '') for i in input]
        elif isinstance(input, basestring):
            return urllib.quote(input, safe = '')
        else:
            return ''

    def auth(self, permission = 'read', callback_url = 'oob'):
        """
        Returns the URL to which the user should be redirected to authorize your
        app for the desired permission. This method gets a new request token and
        sets it as the active token for this instance of the client (so will
        override any token you have previously set with `set_token`).
        """
        t = self.get_request_token(callback_url)
        self.set_token(t['oauth_token'], t['oauth_token_secret'])
        return self.get_authorize_url(self._token, permission)

    def call(self,
        method,
        params = None,
        request_method = 'GET',
        url = API_REST_URL,
        cache = True):
        """
        Call an API method. If the method requires an active/valid token, you
        should set it with `set_token` before calling this method.
        """
        if not params:
            params = {}

        if not method.startswith('vimeo.'):
            method = 'vimeo.' + method
        return self._request(method, params, request_method, url, cache)

    def enable_cache(self, type, path = '.', expire = 600):
        """
        Enable the cache, or switch between cache types. Current cache types are
        as follows:

        vimeo.CACHE_FILE    - Store request information on the filesystem. Data
                             is pickled/unpickled automatically when it is saved
                             to and loaded from files.
        vimeo.CACHE_MEMORY - Store request information in memory (in a
                             `_memory_cache` attribute of the currentinstance).
        """
        self._cache_enabled = type
        if type == CACHE_MEMORY:
            self._memory_cache = {}
        elif type == CACHE_FILE:
            self._cache_dir = path
        self._cache_expire = expire

    def disable_cache(self):
        """
        Disable the cache. Existing cache entries are not deleted. To clear the
        cache completely, call `clear_cache`.
        """
        self._cache_enabled = None

    def clear_cache(self, cache_type = None):
        """
        Empty the cache. Defaults to the active cache type. If no cache type is
        active, and 'cache_type' is not set, nothing will be removed.
        """
        type = cache_type or self.__cache_enabled
        if type == CACHE_MEMORY:
            self._memory_cache = {}
        elif type == CACHE_FILE and self._cache_dir:
            files = os.path.listdir(self._cache_dir)
            files = filter(lambda f: f.endswith('.cache'), files)
            for f in files:
                os.remove(f)

    def get_access_token(self, verifier):
        """
        Get an access token. Make sure to call `set_token` with the request
        token before calling this function.
        """
        access_token = self._request(None, {
                'oauth_verifier': verifier
            },
            'GET',
            API_ACCESS_TOKEN_URL,
            False,
            True)
        return self._parse_token_string(access_token)

    def get_authorize_url(self, token, permission = 'read'):
        """
        Get the URL of the authorization page for the token and permission
        specified.
        """
        url = API_AUTH_URL + '?oauth_token=%s&permission=%s' \
            % (token, permission)
        return url

    def get_request_token(self, callback_url = 'oob'):
        """
        Get a request token.
        """
        request_token = self._request(None, {
                'oauth_callback': callback_url
            },
            'GET',
            API_REQUEST_TOKEN_URL,
            False,
            False)
        return self._parse_token_string(request_token)

    def get_token(self):
        """
        Get the stored OAuth token.
        """
        return self._token, self._token_secret

    def set_token(self, token, token_secret):
        """
        Set the OAuth token for future requests.
        """
        self._token = token
        self._token_secret = token_secret

    def upload(self,
        file,
        replace_id = None,
        mimetype = None):
        """
        Upload a video using the streaming interface. 'file' can either be a
        path to a file on disk, or an open file-like object. If 'file' is a
        file-like object, you should specify a 'mimetype' value to send to the
        API.
        """
        if not hasattr(file, 'read'):
            # Must be a file path. Try to open it.
            fp = open(file)
            ftype = mimetype or mimetypes.guess_type(file)[0] or 'video'
        else:
            fp = file
            ftype = mimetype or mimetypes.guess_type(file.name)[0] or ''

        file_name = os.path.basename(fp.name)
        fp.seek(0,2)
        file_size = fp.tell()
        fp.seek(0)

        method = 'vimeo.videos.upload.getQuota'
        quota = self.call(method)
        quota_free = quota['user']['upload_space']['free']
        if quota_free < file_size:
            raise VimeoAPIError(method, 707,
                        "The file is larger than the user's remaining quota.")

        # Get an upload ticket
        params = {}
        if replace_id:
            params['video_id'] = replace_id

        method = 'vimeo.videos.upload.getTicket'
        rsp = self.call(method, params, 'GET',
                            API_REST_URL, False)
        ticket = rsp['ticket']['id']
        endpoint = rsp['ticket']['endpoint']

        if file_size > rsp['ticket']['max_file_size']:
            raise VimeoAPIError(method, 710,
                        "File exceeds maximum allowed size.")

        headers = {
            'Content-Length': file_size,
            'Content-Type': ftype,
        }
        # PUT the file
        request = urllib2.Request(endpoint, data = fp.read(), headers = headers)
        request.get_method = lambda: 'PUT'
        self._urlopener.open(request)

        # Verify
        verify = self.call('vimeo.videos.upload.verifyChunks', {
            'ticket_id': ticket
        })

        # Make sure out file sizes match up
        errors = []
        info = verify['ticket']['chunks']['chunk']
        if int(info['size']) != file_size:
            errors.append(
                VimeoAPIError(msg =
                    'File chunk id %s is %s bytes but %s were uploaded' % \
                    (info['id'], info['size'], info['size'])
                )
            )

        # Complete the upload
        method = 'vimeo.videos.upload.complete'
        complete = self.call(method, {
            'filename': file_name,
            'ticket_id': ticket,
        })

        # Confirmation successful, return video id
        if complete['stat'] == 'ok':
            return complete['ticket']['video_id'], errors
        else:
            raise VimeoAPIError(method, complete['err']['code'],
                            complete['err']['msg'])