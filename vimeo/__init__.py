"""
This module provides a (nearly) straight port of the phpVimeo class in Vimeo's
vimeo-php-lib library (https://github.com/vimeo/vimeo-php-lib).

There are probably plenty of further Python-centric adjustments that could be
made.
"""

from __future__ import with_statement

import binascii
import copy
import hashlib
import hmac
import math
import mimetypes
import os
import random
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
        # stdlib module.
        return cjson.decode(data.replace('\/', '/'))
except ImportError:
    try:
        import json
        json_decode = json.loads
    except ImportError:
        raise ImportError("Could not find a json library to import.")

# Data values used as defaults
API_REST_URL = 'http://vimeo.com/api/rest/v2'
API_AUTH_URL = 'http://vimeo.com/oauth/authorize'
API_ACCESS_TOKEN_URL = 'http://vimeo.com/oauth/access_token'
API_REQUEST_TOKEN_URL = 'http://vimeo.com/oauth/request_token'

CACHE_FILE = 'file'
CACHE_MEMORY = 'memory'

class VimeoAPIException(Exception):
    """
    A subclass of Exception that provides the api method, error code, and error
    message of the API response.
    """

    def __init__(self, method = '', code = '', msg = ''):
        self.method = method
        self.code = code
        self.msg = msg

    def __str__(self):
        return "API Error calling method %s: %s %s" % \
            (self.method, self.code, self.msg)

class VimeoClient(object):

    _cache_expire = 600

    _consumer_key = None
    _consumer_secret = None
    _cache_enabled = None
    _cache_dir = None
    _token = None
    _token_secret = None

    _cache_drop_keys = ('oauth_nonce', 'oauth_signature', 'oauth_timestamp')

    _app_name = None

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
        Cache an API response
        """

        params = copy.copy(params)

        # Remove some unique things
        for i in self._cache_drop_keys:
            if i in params:
                del params[i]

        params = urllib.urlencode(params)
        hash = hashlib.md5(params).hexdigest()

        if self._cache_enabled == CACHE_FILE:
            f = os.path.join(self._cache_dir, hash, '.cache')
            with open(f, 'w') as f:
                pickle.dump(response_data, f)
            # Match the PHP library's functionality, which returns the number of
            # bytes written. str() is used to cast any unicode back to a string.
            return len(str(response_data))
        elif self._cache_enabled == CACHE_MEMORY:
            self.__memory_cache[hash] = (response_data, time.time())

    def __generate_auth_header(self, oauth_params):
        """
        Create the authorization header for a set of params.
        """

        auth_header = 'OAuth realm=""'

        for k, v in oauth_params.items():
            vals = map(self.url_encode_rfc3986, (k, str(v)))
            auth_header += ',%s="%s"' % tuple(vals)

        # We're using urllib2.Request to make our request, so this returns a
        # dict instead of a string (which is what the PHP library returns)
        return {'Authorization': auth_header}

    def __generate_nonce(self):
        """
        Generate a nonce for the call.
        """
        uid = str(uuid.uuid4())
        return hashlib.md5(uid).hexdigest()

    def __generate_signature(self,
        params,
        request_method = 'GET',
        url = API_REST_URL):
        """
        Generate the OAuth signature.
        """

        keys = sorted(params.keys())
        params = self.url_encode_rfc3986(params)

        # Make sure we iterate the dict in sorted order. Unlike PHP, Python does
        # not guarantee dict key order. We aren't using collections.OrderedDict
        # here because we want to support 2.5+.
        items = [(k, params[k]) for k in keys]
        querystring = urllib.urlencode(items)

        # Make the base string
        base_parts = (
            request_method.upper(),
            url,
            urllib.unquote(querystring),
        )
        base_parts = self.url_encode_rfc3986(base_parts)
        base_string = '&'.join(base_parts)

        # Make the key
        key_parts = (
            self._consumer_secret,
            self._token_secret or '',
        )
        key_parts = self.url_encode_rfc3986(key_parts)
        key = '&'.join(key_parts)

        # Generate signature
        hashed = hmac.new(key, base_string, hashlib.sha1)
        return binascii.b2a_base64(hashed.digest())[:-1]

    def __get_cached(self, params):
        """
        Get the unserialized contents of the cached request.
        """

        params = copy.copy(params)
        # Remove some unique things
        for i in self._cache_drop_keys:
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
            for k, v in self.__memory_cache.items():
                _, last_modified = v
                if last_modified + self._cache_expire < time.time():
                    del self.__memory_cache[k]
            return self.__memory_cache.get(hash)

    def __request(self,
        method,
        call_params = None,
        request_method = 'GET',
        url = API_REST_URL,
        cache = True,
        use_auth_header = True):
        """
        Call an API method.
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
            'oauth_nonce': self.__generate_nonce(),
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
        oauth_params['oauth_signature'] = self.__generate_signature(
                                        signature_params, request_method, url)

        # Merge all args
        all_params = dict(oauth_params.items() + api_params.items())

        # Return cached value
        if self._cache_enabled:
            response_data = self.__get_cached(all_params)
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

        # For some reason using the default user agent that urllib2 provides
        # causes the API to always return XML and not JSON.
        headers = {
            'User-Agent': "Python/vimeo.VimeoClient %s" % self._app_name
        }
        if use_auth_header:
            headers.update(self.__generate_auth_header(oauth_params))

        if request_method == 'POST':
            request = urllib2.Request(request_url, urllib.urlencode(items), headers)
        else:
            request = urllib2.Request(request_url, headers = headers)

        try:
            response = urllib2.urlopen(request, timeout = 30)
        except TypeError:
            # Old version of Python that doesn't accept a timeout argument
            old_default = socket.getdefaulttimeout()
            socket.setdefaulttimeout(30)
            response = urllib2.urlopen(request)
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
                raise VimeoAPIException(method, error.get('code'),
                                            error.get('msg'))
        else:
            return response.read()

    def auth(self, permission = 'read', callback_url = 'oob'):
        """
        Send the user to Vimeo to authorize your app. Returns the URL to which
        the user should be redirected.
        """
        t = self.get_request_token(callback_url)
        self.set_token(t['oauth_token'], t['oauth_token_secret'])
        url = self.get_authorize_url(self._token, permission)
        return url

    def call(self,
        method,
        params = None,
        request_method = 'GET',
        url = API_REST_URL,
        cache = True):
        """
        Call an API method
        """
        if not params:
            params = {}

        if not method.startswith('vimeo.'):
            method = 'vimeo.' + method
        return self.__request(method, params, request_method, url, cache)

    def enable_cache(self, type, path = '.', expire = 600):
        """
        Enable the cache, or switch between cache types.
        """
        self._cache_enabled = type
        if type == CACHE_MEMORY:
            self.__memory_cache = {}
        elif type == CACHE_FILE:
            self._cache_dir = path
        self._cache_expire = expire

    def disable_cache(self):
        """
        Disable the cache.
        """
        self._cache_enabled = None

    def _parse_token(self, tokenstring):
        """
        Parse the token string format into a dict.
        """
        params = parse_qs(tokenstring)
        for k, v in params.items():
            if len(v) == 1:
                params[k] = v[0]
            elif len(v) == 0:
                params[k] = None
        return params


    def get_access_token(self, verifier):
        """
        Get an access token. Make sure to call self.set_token() with the request
        token before calling this function.
        """
        access_token = self.__request(None, {
                'oauth_verifier': verifier
            }, 'GET', API_ACCESS_TOKEN_URL, False, True)
        return self._parse_token(access_token)

    def get_authorize_url(self, token, permission = 'read'):
        """
        Get the URL of the authorization page.
        """
        url = API_AUTH_URL + '?oauth_token=%s&permission=%s' \
            % (token, permission)
        return url

    def get_request_token(self, callback_url = 'oob'):
        """
        Get a request token
        """
        request_token = self.__request(None, {
                'oauth_callback': callback_url
            }, 'GET', API_REQUEST_TOKEN_URL, False, False)
        return self._parse_token(request_token)

    def get_token(self):
        """
        Get the stored auth token.
        """
        return self._token, self._token_secret

    def set_token(self, token, token_secret):
        """
        Set the OAuth token
        """
        self._token = token
        self._token_secret = token_secret

    def upload(self,
        file,
        replace_id = None,
        mimetype = None):
        """
        Upload a video using the streaming interface.
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
            raise VimeoAPIException(method, 707,
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
            raise VimeoAPIException(method, 710,
                        "File exceeds maximum allowed size.")

        headers = {
            'Content-Length': file_size,
            'Content-Type': ftype,
        }
        # PUT the file
        opener = urllib2.build_opener(urllib2.HTTPHandler)
        request = urllib2.Request(endpoint, data = fp.read(), headers = headers)
        request.get_method = lambda: 'PUT'
        _rsp = opener.open(request)

        # Verify
        verify = self.call('vimeo.videos.upload.verifyChunks', {
            'ticket_id': ticket
        })

        # Make sure out file sizes match up
        errors = []
        info = verify['ticket']['chunks']['chunk']
        if info['size'] != file_size:
            errors.append(
                VimeoAPIException(msg =
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
            raise VimeoAPIException(method, complete['err']['code'],
                            complete['err']['msg'])

    @staticmethod
    def url_encode_rfc3986(input):
        """
        URL encode a parameter or dict of parameters.
        """
        # If it quacks like a dict ...
        if hasattr(input, 'items') and callable(input.items):
            input = copy.copy(input)
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