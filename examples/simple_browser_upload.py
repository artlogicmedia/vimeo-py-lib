#!/usr/bin/env python2
"""
An example for using this module in an actual website workflow to upload videos
to a user's account. This uses Bottle (http://bottlepy.org/) for serving pages
and Beaker (http://beaker.readthedocs.org/) for session management, but the 
principles apply equally to Django/Pylons/Pyramid.

This example authorizes the account using the 'callback' setting in the Vimeo
app settings. When the user finishes authorizing the request token, they are
redirected back to the callback URL with the 'oauth_token' and 'oauth_verifier'
parameters set as GET parameters.
"""

import bottle
import mimetypes
import urllib2
import vimeo

# Bottle doesn't provide built-in session support, so we're using Beaker
from beaker.middleware import SessionMiddleware

session_opts = {
    'session.type': 'memory',
    'session.auto': True
}
app = SessionMiddleware(bottle.app(), session_opts)

# These are the keys as provided by Vimeo. You should edit these with your own
# app's keys.
CONSUMER_ID = ''
CONSUMER_SECRET = ''

# This actually handles the request (although in this example, we're putting
# all requests through the same handler, rather than individual ones).
@bottle.route('<path:path>', method=["GET", "POST"])
def handle_request(path, *args, **kwargs):

    session = bottle.request.environ.get('beaker.session')

    # The client that will interface with a single user's account. The app_name
    # argument is added to the UA when making requests.
    client = vimeo.VimeoClient(CONSUMER_ID, CONSUMER_SECRET, app_name = 'MyApp')

    # These will be set if we are coming back from a callback from the Vimeo
    # authorization page.
    token = bottle.request.query.get('oauth_token')
    verifier = bottle.request.query.get('oauth_verifier')

    if session.get('access_token'):
        # We already have an access key. Set it on the client and continue.
        access_token = session['access_token']
        access_token_secret = session['access_token_secret']
        client.set_token(access_token, access_token_secret)

        # If we have an access token and the user is attempting an upload,
        # process that upload.
        title = bottle.request.forms.get('title') or ''
        description = bottle.request.forms.get('description') or ''
        video = bottle.request.files.get('video')

        # Guess the mimetype and pass it to the client. The upload() method will
        # also attempt to guess it if it can, but in a real application you
        # probably want to pass this in explicitly.
        mimetype = mimetypes.guess_type(video.filename)

        try:
            # The video_id returned by this call should be stored. It is the
            # canonical reference to the video in question.
            video_id, errors = client.upload(video.file, None, mimetype)
            # Now set the title and description
            client.call('videos.setTitle', {
                'title': title,
                'video_id': video_id
            })
            client.call('videos.setDescription', {
                'description': description,
                'video_id': video_id
            })

            # Verification errors. If Vimeo doesn't return an 'OK' response for
            # the final check of whether the upload was successful, an exception
            # will be thrown anyway (VimeoAPIError).
            if errors:
                return ("The video was uploaded but some errors were "
                        "encountered: %s") % [str(e) for e in errors]

        # Explict check for fatal API errors
        except vimeo.VimeoAPIError, e:
            bottle.response.status = 500
            return "Error completing upload to Vimeo: %s (%s)" % (e.msg, e.code)

        # We can also catch more general errors attempting to make the request
        except urllib2.URLError, e:
            bottle.response.status = 500
            return "Could not contact Vimeo. (%s)" % repr(e)

    elif token and verifier:
        # The final step of authorization
        #
        # If you aren't re-creating the client object on each request, storing
        # and retrieving the request tokens in the session is an unnecessary
        # step
        request_token = session['request_token']
        request_token_secret = session['request_token_secret']
        client.set_token(request_token, request_token_secret)

        # Make the final token exchange
        token = client.get_access_token(verifier)
        access_token = token['oauth_token']
        access_token_secret = token['oauth_token_secret']
        # Set the access token on the client.
        client.set_token(access_token, access_token_secret)
        # Now store the access token in the session (for reuse later).
        session.update({
            'access_token': access_token,
            'access_token_secret': access_token_secret,
        })

    else:
        # No access key is set, so direct the user to the auth page.
        #
        # Calling the auth() method will get the initial token from Vimeo, set
        # it on the client object, and return the appropriate URL.
        authorize_url = client.auth('write')
        # If you aren't re-creating the client object on each request, storing
        # and retrieving the request tokens in the session is an unnecessary
        # step
        session.update({
            'request_token': client._token,
            'request_token_secret': client._token_secret,
        })
        html = ('<a href="%s">Click here to authorize this app to use your '
                'Vimeo account</a>') % authorize_url
        return html

    upload_form = """
    <form action="" method="POST" enctype="multipart/form-data">
        Title: <input type="text" name="title" /><br>
        Description: <input type="text" name="description" /><br>
        Video: <input type="file" name="video" accept="video/*" /><br>
        <input type="submit" value="Submit" />
    </form>
    """

    return upload_form


if __name__ == '__main__':
        
    bottle.debug(True)
    bottle.run(app = app, host='0.0.0.0', port=8080, reloader=True)