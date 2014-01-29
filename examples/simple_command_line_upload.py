#!/usr/bin/env python2
"""
The following is a simple example for uploading a video from the command line.

This example gives you the workflow for authorizing an app that does not use
the callback mechanism that is available in a web context, and instead requires
the user to enter the OAuth verifier manually.

For web usage, see the simple_browser_upload.py example.

Usage: ./simple_command_line_upload.py <filepath> <title> <description>
"""

import sys
import vimeo

if __name__ == '__main__':

    filepath, title, description = (sys.argv[1:] + ['', '', ''])[:3]

    consumer_id = raw_input("Please enter your consumer id: ")
    consumer_secret = raw_input("Please enter your consumer secret: ")

    client = vimeo.VimeoClient(consumer_id, consumer_secret)

    # Set the initial request token and get the authorization URL in one go.
    authorization_url = client.auth('write')

    # The user will need to visit the URL in a browser, approve the app, and
    # then return to the command line with the verifier they have been given.
    auth_prompt = """
Go to the following URL in your favorite browser to authorize this app:
%s

When you are done, enter your authorization code here: """
    verifier = raw_input(auth_prompt % authorization_url)

    # Exchange the request token for the access token using the verifier.
    token = client.get_access_token(verifier)
    # Set the access token on the client.
    access_token = token['oauth_token']
    access_token_secret = token['oauth_token_secret']
    client.set_token(access_token, access_token_secret)

    # Now do the upload. Unlike the browser example, we're going to pass in the
    # file path as a string and leave the client to deal with guessing the
    # mimetype.
    video_id, errors = client.upload(filepath)
    client.call('videos.setTitle', {
        'title': title,
        'video_id': video_id
    })
    client.call('videos.setDescription', {
        'description': description,
        'video_id': video_id
    })
    
    print "Upload complete."
    if errors:
        print "Some errors occured during upload:", [str(e) for e in errors]
    