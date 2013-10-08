import cgi
import datetime
import json
import urllib

from google.appengine.api import users
from google.appengine.api import search 
from google.appengine.api.images import get_serving_url
from google.appengine.ext import ndb
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers

import webapp2

class Stream(ndb.Expando):
    name = ndb.StringProperty()
    tags = ndb.StringProperty()
    cover_url = ndb.StringProperty()
    followers = []
    date = ndb.DateTimeProperty(auto_now_add=True)
    def to_dict(self):
        d = super(Stream, self).to_dict()
        d['id'] = self.key.id()
        return d

class Image(ndb.Model):
    image_url = ndb.StringProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)
    def to_dict(self):
        d = super(Image, self).to_dict()
        d['id'] = self.key.id()
        return d

class ManPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        self.response.write('Hello, class!')
        self.response.write("""
<p>
I've created my own Connexus web API for the Android miniproject and I'd like to share it with the class.<br>
<p>
<a href="https://github.com/zachwhaley/connexus-web-python" >Git repo</a><br>
<p>
It's not completely functional, but here are the things that do work:<br>
Get all streams:
<a href="http://connexus-api.appspot.com/allstreams" >connexus-api.appspot.com/allstreams</a><br>
<p>
Get subscribed streams:<br>
<a href="http://connexus-api.appspot.com/mystreams?email=zachbwhaley@gmail.com" >
connexus-api.appspot.com/mystreams?email=zachbwhaley@gmail.com</a><br>
<p>
Add stream:<br>
<code>curl --data "name=greyhounds&tags=greyhound&cover_url=http://imgur.com/IcCcXYg"
connexus-api.appspot.com/addstream</code><br>
Get stream images:<br>
<a href="http://connexus-api.appspot.com/images?stream=5629499534213120" >
connexus-api.appspot.com/images?stream=5629499534213120</a><br>
<p>
Subscribe to a stream:<br>
<code>curl --data "email=zachbwhaley@gmail.com&stream=5629499534213120" connexus-api.appspot.com/subscribe</code><br>
<p>
Things to come:<br>
Nearby Streams<br>
<a href="http://connexus-api.appspot.com/nearbystreams?latitude=foo&longitude=bar" >
connexus-api.appspot.com/nearbystreams?latitude=foo&longitude=bar</a><br>
<p>
Image uploading<br>
This is going to be a two part thing, where the Android app asks for a URL, populates that URL with image info (lat, lon, stream id, etc) and then sends the URL back as a multipart thing.
<p>
Feel free to use these in your Android app :-)<br>
Let me know if I'm missing anything, and please feel free to contribute.<br>
""")

class AddStream(webapp2.RequestHandler):
    def post(self):
        stream = Stream()
        stream.name = self.request.get('name')
        stream.tags = self.request.get('tags')
        stream.cover_url = self.request.get('cover_url')
        stream.followers = []
        stream.put()

class GetUploadUrl(webapp2.RequestHandler):
    def get(self):
        upload_url = blobstore.create_upload_url('/upload/handler')
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write(upload_url)

class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        upload_files = self.get_uploads('image')
        blob_info = upload_files[0]
        key = blob_info.key()

        serving_url = get_serving_url(key)
        stream_id = self.request.get('stream')
        latitude = self.request.get('latitude')
        longitude = self.request.get('longitude')
        stream = Stream.get_by_id(long(stream_id))

        geopoint = search.GeoPoint(float(latitude), float(longitude))
        doc = search.Document(fields=[
            search.TextField(name='key', value=str(stream.key)),
            search.GeoField(name='loc', value=geopoint)])
        search.Index(name='geopoints').put(doc)

        image = Image(parent=stream.key)
        image.image_url = serving_url
        if not stream.cover_url:
            stream.cover_url = serving_url
        image.put()

class Subscribe(webapp2.RequestHandler):
    def post(self):
        stream_id = self.request.get('stream')
        email = self.request.get('email')
        stream = Stream.get_by_id(long(stream_id))
        stream.followers.append(email)
        stream.put()

class AllStreams(webapp2.RequestHandler):
    def get(self):
        query = Stream.query().order(-Stream.date)
        streams = [stream.to_dict() for stream in query.fetch()]
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(streams, cls=DateSkipper))

class MyStreams(webapp2.RequestHandler):
    def get(self):
        query = Stream.query().order(-Stream.date)
        email = self.request.get('email')
        streams = [stream.to_dict() for stream in query.fetch() if email in stream.followers]
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(streams, cls=DateSkipper))

class NearbyStreams(webapp2.RequestHandler):
    def get(self):
        latitude = self.request.get('latitude')
        longitude = self.request.get('longitude')
        index = search.Index('geopoints')
        query = 'distance(loc, geopoint(' + str(latitude) + ',' + str(longitude) + ')) < 1000'
        results = index.search(query)
        streams = [Stream.get_or_insert(str(doc.field('key'))) for doc in results]
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(streams, cls=DateSkipper))

class StreamImages(webapp2.RequestHandler):
    def get(self):
        stream_id = self.request.get('stream')
        stream = Stream.get_by_id(long(stream_id))
        query = Image.query().ancestor(stream)
        images = [image.to_dict() for image in query.fetch()]
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(json.dumps(images, cls=DateSkipper))

class DateSkipper(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return
        return json.JSONEncoder.default(self, obj) 

application = webapp2.WSGIApplication([
    ('/', ManPage),
    ('/addstream', AddStream),
    ('/allstreams', AllStreams),
    ('/mystreams', MyStreams),
    ('/nearbystreams', NearbyStreams),
    ('/images', StreamImages),
    ('/subscribe', Subscribe),
    ('/upload/geturl', GetUploadUrl),
    ('/upload/handler', UploadHandler),
], debug=True)
