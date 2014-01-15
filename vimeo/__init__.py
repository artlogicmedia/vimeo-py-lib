"""
This module provides a straight port of the phpVimeo class in Vimeo's
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
import os
import socket
import time
import urllib
import uuid

try:
    import cPickle
    pickle = cPickle
except ImportError:
    # Respect for alternate implementations
    import pickle

try:
    import cjson
    json_encode = cjson.encode
    json_decode = cjson.decode
except ImportError:
    try:
        import json
        json_encode = json.dumps
        json_decode = json.loads
    except ImportError:
        raise ImportError("Could not find a json library to import.")

class VimeoAPIException(urllib2.HTTPError):
    """
    A subclass of the urllib2.HTTPError that explicitly refers to errors making
    requests against the Vimeo API.
    """
    pass

class VimeoAPI(object):

    API_REST_URL = 'http://vimeo.com/api/rest/v2'
    API_AUTH_URL = 'http://vimeo.com/oauth/authorize'
    API_ACCESS_TOKEN_URL = 'http://vimeo.com/oauth/access_token'
    API_REQUEST_TOKEN_URL = 'http://vimeo.com/oauth/request_token'

    CACHE_FILE = 'file'
    CACHE_MEMORY = 'memory'
    __cache_expire = 600
    
    __consumer_key = None
    __consumer_secret = None
    __cache_enabled = None
    __cache_dir = None
    __token = None
    __token_secret = None

    __oauth_drop_keys = ('oauth_nonce', 'oauth_signature', 'oauth_timestamp')

    def __init__(self,
        consumer_key,
        consumer_secret,
        token = None,
        token_secret = None):

        self.__consumer_key = consumer_key
        self.__consumer_secret = consumer_secret

        if token and token_secret:
            self.setToken(token, token_secret)

    def __cache(self, params, response_data):
        """
        Cache an API response
        """

        # Remove some unique things
        for i in self.__oauth_drop_keys:
            if i in params:
                del params[i]

        params = urllib.urlencode(params)
        hash = hashlib.md5(params).hexdigest()

        if self.__cache_enabled == self.CACHE_FILE:
            f = os.path.join(self.__cache_dir, hash, '.cache')
            with open(f, 'w') as f:
                pickle.dump(response_data, f)
            # Match the PHP library's functionality, which returns the number of
            # bytes written. str() is used to cast any unicode back to a string.
            return len(str(response_data))
        elif self.__cache_enabled == self.CACHE_MEMORY:
            self.__memory_cache[hash] = (pickle.dumps(response_data),
                                            time.time())

    def __generate_auth_header(self, oauth_params):
        """
        Create the authorization header for a set of params.
        """

        auth_header = 'OAuth realm=""'

        for k, v in oauth_params.items():
            auth_header += ',%s="%s"' % map(self.url_encode_rfc3986, (k, v))

        # We're using urllib2.Request to make our request, so this returns a
        # dict instead of a string (which is what the PHP library returns)
        return {'Authorization': auth_header}

    def __generate_nonce(self):
        """
        Generate a nonce for the call.
        """
        return hashlib.md5(uuid.uuid4()).hexdigest()

    def __generate_signature(self,
        params,
        request_method = 'GET',
        url = self.API_REST_URL):
        """
        Generate the OAuth signature.
        """

        keys = sorted(params.keys())
        params = self.url_encode_rfc3986(params)

        # Make sure we iterate the dict in sorted order. Unlike PHP, Python does
        # not guarantee dict key order. We aren't using collections.OrderedDict
        # here because we want to support 2.5+.
        querystring = '&'.join(['%s="%s"' % (k, params[k]) for k in keys])

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
            self.__consumer_secret,
            self.__token_secret or '',
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
        # Remove some unique things
        for i in self.__oauth_drop_keys:
            if i in params:
                del params[i]

        params = urllib.urlencode(params)
        hash = hashlib.md5(params).hexdigest

        if self.__cache_enabled == self.CACHE_FILE:
            f = os.path.join(self.__cache_dir, hash, '.cache')
            # Check to see if the cache file is expired and remove it
            last_modified = os.path.getmtime(f)
            if f.endswith('.cache') and \
            last_modified + self.__cache_expire < time.time():
                os.remove(f)
            if os.path.exists(f):
                with open(f) as f:
                    return pickle.load(f)
        elif self.__cache_enabled == self.CACHE_MEMORY:
            for k, v in self.__memory_cache.items():
                _, last_modified = v
                if last_modified + self.__cache_expire < time.time():
                    del self.__memory_cache[k]
            return self.__memory_cache.get(k)

    def __request(self,
        method,
        call_params = None,
        request_method = 'GET',
        url = self.API_REST_URL,
        cache = True,
        use_auth_header = True):
        """
        Call an API method.
        """
        if call_params is None:
            call_params = {}

        # Prepare oauth arguments
        oauth_params = {
            'oauth_consumer_key': self.__consumer_key,
            'oauth_version': '1.0',
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_timestamp': int(time.time()),
            'oauth_nonce': self.__generate_nonce(),
        }

        # If we have a token, include it
        if self.__token:
            oauth_params['oauth_token'] = self.__token

        # Regular args
        api_params = {'format': 'json'}
        if method:
            api_params['method'] = method

        # Merge args
        for k, v in call_params:
            if k.index('oauth_') == 0:
                oauth_params[k] = v
            elif v is not None:
                api_params[k] = v

        # Merge all args
        all_params = {}
        for d in (oauth_params, api_params):
            all_params.update(d)
            
        # Generate the signature
        oauth_params['oauth_signature'] = self.__generate_signature(all_params,
                                                request_method, url)

        # Return cached value
        if self.__cache_enabled:
            response_data = self.__get_cached(all_params)
            if cache and response_data:
                return response_data

        # Request options
        if use_auth_header:
            params = api_params
        else:
            params = all_params

        request_method = request_method.upper()
        if request_method == 'GET':
            request_url = url + '?' + urllib.urlencode(params)
        elif request_method == 'POST':
            request_url = url

        if use_auth_header:
            headers = self.__generate_auth_header
        else:
            headers = {}

        if request_method == 'POST':
            request = urllib2.Request(request_url, params, headers)
        else:
            request = urllib2.Request(request_url, None, headers)

        try:
            response = urllib2.urlopen(request, None, 30)
        except TypeError:
            # Old version of Python that doesn't accept a timeout argument
            old_default = socket.getdefaulttimeout()
            socket.setdefaulttimeout(30)
            response = urllib2.urlopen(request)
            socket.setdefaulttimeout(old_default)

        if method:
            response_data = response.read()
            response_data = cjson_decode(response_data)

            # Cache the response
            if self.__cache_enabled and cache:
                self.__cache(all_params, response_data)

            if response_data.get('stat') == 'ok':
                return response_data
            elif response_data.get('stat') == 'err':
                error = response_data.get('err')
                raise VimeoAPIException(error.get('msg'), error.get('code'))
        else:
            return response.read()

    def auth(self, permission = 'read', callback_url = 'oob'):
        """
        Send the user to Vimeo to authorize your app. Returns the URL to which
        the user should be redirected.
        """
        t = self.get_request_token(callback_url)
        self.set_token(
            t['oauth_token'],
            t['oauth_token_secret'],
            'request',
            true)

        url = self.get_authorize_url(self.__token, permission)
        return url

    def call(self,
        method,
        params = None,
        request_method = 'GET',
        url = self.API_REST_URL,
        cache = True):
        """
        Call a method
        """
        if not params:
            params = {}

        if not method.startswith('vimeo.'):
            method = 'vimeo.' + method
        return self.__request(method, params, request_method, url, cache)

    def enable_cache(self, type, path, expire = 600):
        """
        Enable the cache
        """
        self.__cache_enabled = type
        if type == self.CACHE_MEMORY:
            self.__memory_cache = {}
        self.__cache_expire = expire

    def get_access_token(self, verifier):
        """
        Get an access token. Make sure to call self.set_token() with the request
        token before calling this function.
        """
        access_token = self.__request(None, {
                'oauth_verifier': verifier
            }, 'GET', self.API_ACCESS_TOKEN_URL, False, True)
        return access_token

    def get_authorize_url(self, token, permission = 'read'):
        """
        Get the URL of the authorization page.
        """
        url = self.API_AUTH_URL + '?oauth_token=%s&permission=%s' \
            % (token, permission)
        return url

    def get_request_token(self, callback_url = 'oob'):
        """
        Get a request token
        """
        request_token = self.__request(None, {
                'oauth_callback': callback_url
            }, 'GET', self.API_REQUEST_TOKEN_URL, False, False)
        return request_token

    def get_token(self):
        """
        Get the stored auth token.
        """
        return self.__token, self.__token_secret

    def set_token(self, token, token_secret, type = 'access'):
        """
        Set the OAuth token
        """
        self.__token = token
        self.__token_secret = token_secret

    def upload(self,
        file_path_or_pointer,
        use_multiple_chunks = False,
        chunk_temp_dir = '.',
        size = 2097152, # 2 MB chunks
        replace_id = None):
        """
        Upload a video in one piece
        """
        if not hasattr(file_path_or_pointer, 'read'):
            # Must be a file path. Try to open it.
            fp = open(file_path_or_pointer)

        else:
            # Probably an open file or file-like object
            fp = file_path_or_pointer

        file_name = os.path.basename(fp.name)
        fp.seek(0,2)
        file_size = fp.tell()
        fp.seek(0)

        quota = self.call('vimeo.videos.upload.getQuota')
        quota_free = quota['user']['upload_space']['free']
        if quota_free < file_size:
            raise VimeoAPIException(
                "The file is larger than the user's remaining quota.", 707)

        # Get an upload ticket
        params = {}
        if replace_id:
            params['video_id'] = replace_id

        rsp = self.call('vimeo.videos.upload.getTicket', params, 'GET',
                            self.API_REST_URL, False)
        ticket = rsp['ticket']['id']
        endpoint = rsp['ticket']['endpoint']

        if file_size > rsp['ticket']['max_file_size']:
            raise VimeoAPIException("File exceeds maximum allowed size.", 710)

        # Split the file up if using multiple pieces.
        chunks = []
        if use_multiple_chunks:
            number_of_chunks = math.ceil(file_size / size)
            for i in range(number_of_chunks):
                chunk_file_name = os.path.join(chunk_temp_dir,
                                        '%s.%s' % (file_name, i))
                chunk = fp.read(size)
                with open(chunk_file_name, 'w') as f:
                    f.write(chunk)
                chunks.append({
                    'file': os.path.abspath(chunk_file_name),
                    'size': len(chunk)
                })
            fp.close() # Won't need this anymore
        else:
            chunks.append({
                'file': fp,
                'size': file_size,
            })

        for i, chunk in enumerate(chunks):
            params = {
                'oauth_consumer_key': self.__consumer_key,
                'oauth_token':  self.__token,
                'oauth_signature_method': 'HMAC-SHA1',
                'oauth_timestamp': time.time(),
                'oauth_nonce': self.__generate_nonce(),
                'oauth_version': '1.0',
                'ticket_id': ticket,
                'chunk_id': i,
            }

            if len(chunks) == 1:
                chunkfp = fp
            else:
                chunkfp = open(chunk['file'])

            # Generate the OAuth signature
            params.update({
                'oauth_signature': self.__generate_signature(params, 'POST',
                                        self.API_REST_URL),
                # don't include the file in the signature
                'file_data': chunkfp.read(),
            })

            # Post the file
            request = urllib2.Request(endpoint, params)
            _rsp = urllib2.urlopen(request)

        # Verify
        verify = self.call('vimeo.videos.upload.verifyChunks', {
            'ticket_id': ticket
        })

        # Make sure out file sizes match up
        errors = []
        for chunk_check in verify['ticket']['chunks']:
            chunk = chunks[chunk_check['id']]
            if chunk['size'] != chunk_check['size']:
                # size incorrect, uh oh
                errors.append('Chunk %s is actually %s but uploaded as %s' % \
                    (chunk_check['id'], chunk['size'], chunk_check['size']))

        # Complete the upload
        complete = self.call('vimeo.videos.upload.complete', {
            'filename': file_name,
            'ticket_id': ticket,
        })

        # Clean up
        if len(chunks) > 1:
            for chunk in chunks:
                os.remove(chunk['file'])

        # Confirmation successful, return video id
        if complete['stat'] == 'ok':
            return complete['ticket']['video_id'], errors
        elif complete['stat'] == 'err':
            raise VimeoAPIException(complete['err']['msg'],
                    complete['err']['code'])

    @staticmethod
    def url_encode_rfc3986(input):
        """
        URL encode a parameter or dict of parameters.
        """
        # If it quacks like a dict ...
        if hasattr(input, 'items') and callable(input.items):
            input = copy.copy(input)
            for k, v in input.items():
                input[k] = urllib.quote(v, safe = '')
            return input
        # Purposefully want this to fail a string. Cover all other iterables.
        elif hasattr(input, '__iter__'):
            return [urllib.quote(i, safe = '') for i in input]
        elif isinstance(input, basestring):
            return urllib.quote(basestring, safe = '')
        else:
            return ''