import os
import glob
import socket
import SocketServer # see:  http://docs.python.org/library/socketserver.html
import BaseHTTPServer

#import RiddimPlaylist
from lib.streamer import RiddimStreamer

class RiddimServerRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    def do_HEAD(self,icy_client):
        if icy_client:
            self.send_response(200,"ICY")
            headers = {
                'icy-notice1'   : '<BR>Riddim<BR>',
                'icy-notice2'   : 'riddim-server<BR>',
                'icy-name'      : 'riddim on %s' % socket.gethostname(),
                'icy-genre'     : 'unknown',
                'icy-url'       : 'http://github.com/noah/riddim',
                'content-type'  : 'audio/mpeg',
                'icy-pub'       : 0,
                #'icy-br'        : 128,
                'icy-metaint'   : 16384
            }
            for k,v, in headers.iteritems():
                self.send_header(k,v)
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'audio/x-mpegurl')
            self.end_headers()
        self.end_headers()

    def do_POST(self):
        """ xmlrpclib """
        # POST /RPC2 HTTP/1.0
        # Host: downbe.at:18944
        # User-Agent: xmlrpclib.py/1.0.1 (by www.pythonware.com)
        # Content-Type: text/xml
        # Content-Length: 112
        pass

    def do_GET(self):
        # Potential client candidates:

        """ cmus """
        # GET / HTTP/1.0
        # Host: downbe.at
        # User-Agent: cmus/v2.3.2
        # Icy-MetaData: 1

        """ mplayer """
        # GET / HTTP/1.0
        # Host: downbe.at:18944
        # User-Agent: MPlayer/SVN-r31347-4.5.0
        # Icy-MetaData: 1
        # Connection: close

        # GET / HTTP/1.0
        # Accept: */*
        # User-Agent: NSPlayer/4.1.0.3856
        # Host: downbe.at:18944
        # Pragma: xClientGUID={c77e7400-738a-11d2-9add-0020af0a3278}
        # Pragma: no-cache,rate=1.000000,stream-time=0,stream-offset=0:0,request-context=1,max-duration=0
        # Connection: Close

        """ squeezebox (wut?) """
        # Connection: close
        # Cache-Control: no-cache
        # Accept: */*
        # Host: localhost:18944
        # User-Agent: iTunes/4.7.1 (Linux; N; Linux; i686-linux; EN; utf8) SqueezeCenter, Squeezebox Server/7.4.1/28947
        # Icy-Metadata: 1


        H = self.headers
        icy_client = False
        try:
            icy_client = (int(H['icy-metadata']) == 1)
        except KeyError, e:
            print "non-icy (dry?) client:  %s" % e

        user_agent = None
        try:
            user_agent = H['user-agent']
        except KeyError, e:
            print "Couldn't get user agent!"

        if user_agent:
            print "User-Agent:  %s" % user_agent

        self.do_HEAD(icy_client)
        # playlist = RiddimPlaylist()
        streamer = RiddimStreamer(self.request)

        # mp3, MP3, mP3, Mp3 <-- why do people insist on 
        # mixed-case filenames?
        # FIXME
        playlist = glob.glob(
                os.path.join('/home/noah/gits/github/riddim/mp3',
                    '*.[mM][pP]3'))
        playlist.sort()
        for file in playlist:
            streamer.stream(file,icy_client)

class RiddimServer(BaseHTTPServer.HTTPServer):
    def __init__(self,addr):
        SocketServer.TCPServer.__init__(self,addr,RiddimServerRequestHandler)
