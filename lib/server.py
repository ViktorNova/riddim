from datetime       import datetime
from SocketServer   import TCPServer
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

from lib.config     import Config
from lib.streamer   import Streamer
from lib.logger     import log
from lib.data       import DataManager


class Server(HTTPServer):

    def __init__(self, addr):
        self.allow_reuse_address    = 1
        self.hostname, self.port    = addr
        TCPServer.__init__(self, addr, ServerRequestHandler)

        # shared state
        self.data = dict()

        # set server defaults
        self.data = {
                'started_at'    : datetime.now(),
                'port'          : self.port,
                'hostname'      : Config.hostname,
                'running'       : True
        }

        # create a shared Data object
        self.manager = DataManager(address=('', self.port + 1),
                 authkey=Config.authkey)

        # "Private" methods ('__'-prefixed) are *not* exported out of
        # the manager by default.  This includes stuff to make dict work
        # minimally.  See
        #   http://docs.python.org/library/multiprocessing.html
        #
        # Upshot is we need to explicitly name the exposed functions:
        DataManager.register('get_data', callable=lambda: self.data,
                exposed=('__str__', '__delitem__', '__getitem__',
                    '__setitem__'))

        self.manager.start()
        self.manager.connect()
        self.data = self.manager.get_data()


        log.info("Bloops and bleeps at http://%s:%s" % self.server_address)
        self.serve_forever()
        self.cleanup()

    def serve_forever(self):
        while self.data['running']:
            print "handling requests"
            self.handle_request()
        print "done handling requests (server got message)"

    def cleanup(self):
        log.debug("cleaning up")
        self.manager.shutdown()
        self.server_close()
        #sys.exit(1)


class ServerRequestHandler(BaseHTTPRequestHandler):

    def do_HEAD(self, icy_client):
        log.debug("head")
        #if icy_client:
        self.send_response(200, "ICY")
        # fixme verbose
        headers = {
            'icy-notice1'   : Config.notice_1,
            'icy-notice2'   : Config.notice_2,
            'icy-name'      : Config.icy_name,
            'icy-genre'     : Config.icy_genre,
            'icy-url'       : Config.icy_url,
            'icy-pub'       : Config.icy_pub,
            #'icy-br'        : 128,
            'icy-metaint'   : Config.icy_metaint,
            'content-type'  : Config.content_type
        }
        [self.send_header(k, v) for k, v, in headers.iteritems()]
        self.end_headers()

    def do_POST(self):
        time.sleep(6000)

    def do_GET(self):
        log.debug("post")
        # Handle well-behaved bots
        _path = self.path.strip()
        log.info("Request path: %s" % _path)
        if _path == "/robots.txt":
            self.send("User-agent: *\nDisallow: /\n")
        elif _path != "/":
            self.send_error(403, "Bad request.\n")
        else:
            # path is /
            #
            # examine some headers

            # Client candidates:
            """ cmus """
            # GET / HTTP/1.0
            # Host: 0x7be.org
            # User-Agent: cmus/v2.3.2
            # Icy-MetaData: 1

            """ mplayer """
            # GET / HTTP/1.0
            # Host: 0x7be.org:18944
            # User-Agent: MPlayer/SVN-r31347-4.5.0
            # Icy-MetaData: 1
            # Connection: close

            # GET / HTTP/1.0
            # Accept: */*
            # User-Agent: NSPlayer/4.1.0.3856
            # Host: 0x7be.org:18944
            # Pragma: xClientGUID={c77e7400-738a-11d2-9add-0020af0a3278}
            # Pragma: no-cache,rate=1.000000,stream-time=0,stream-offset=0:0,
            #           request-context=1,max-duration=0
            # Connection: Close

            """ squeezebox """
            # Connection: close
            # Cache-Control: no-cache
            # Accept: */*
            # Host: localhost:18944
            # User-Agent: iTunes/4.7.1 (Linux; N; Linux; i686-linux; EN;
            #           utf8) SqueezeCenter, Squeezebox Server/7.4.1/28947
            # Icy-Metadata: 1

            H, icy_client = self.headers, False
            try:
                icy_client = (int(H['icy-metadata']) == 1)
            except KeyError, e:
                log.error("non-icy client:  %s" % e)
                log.error(self.address_string())

            if not icy_client:
                self.send_response(400, "Bad client.\n Try http://cmus.sourceforge.net/\n")
                return False

            user_agent = None
            try:                user_agent = H['user-agent']
            except KeyError, e: log.exception("Couldn't get user agent.")
            if user_agent:      log.info("User-Agent:  %s" % user_agent)

            self.do_HEAD( icy_client )
            Streamer( self.request, self.server.port ).stream( icy_client )

        return 0
