from os import walk
from os.path import isfile, realpath, join, isdir
import re
import sys
import time
import math
import fnmatch
import random
import cPickle as pickle
from multiprocessing import Pool
from datetime import datetime

from lib.config     import Config
from lib.logger     import log
from lib.song       import Song
from lib.data       import DataManager
from lib.util       import is_stream

label_bool      = {True: 'on', False: 'off'}
label_status    = {"stopped" : ".", "playing" : ">"}


def filesizeformat(bytes):
    """
    Formats the value like a 'human-readable' file size (i.e. 13 KB, 4.1 MB,
    102 bytes, etc).  Modified django
    """
    try:    bytes = float(bytes)
    except (TypeError, ValueError, UnicodeDecodeError):
        return "%s bytes" % 0

    pretty = lambda x: round(x, 1)

    if bytes < 1024: return "%s bytes" % pretty(bytes)
    if bytes < 1024 * 1024: return "%s KB" % pretty((bytes / 1024))
    if bytes < 1024 * 1024 * 1024: return "%s MB" % pretty((bytes / (1024 * 1024)))
    if bytes < 1024 * 1024 * 1024 * 1024: return "%s GB" % pretty((bytes / (1024 * 1024 * 1024)))
    if bytes < 1024 * 1024 * 1024 * 1024 * 1024: return "%s TB" % pretty((bytes / (1024 * 1024 * 1024 * 1024)))
    return "%s PB" % pretty((bytes / (1024 * 1024 * 1024 * 1024 * 1024)))


class PlaylistFile(object):

    @staticmethod
    def read():
        try:
            # Read an existing file
            with open( Config.datapath, 'rb' ) as picklef:
                data = pickle.load( picklef )
                assert type(data) == dict
        except:
            # File non-existent or corrupt.
            PlaylistFile.truncate()
            return {}

        return data

    @staticmethod
    def truncate():
        try:
            open(Config.datapath, 'wb')
            return True
        except Exception, e:
            log.exception(e)
        return False

    @staticmethod
    def save(data):
        try:
            with open( Config.datapath, 'wb') as picklef:
                pickle.dump(data, picklef)
            return True
        except Exception, e:
            log.exception(e)
        return False


def crunch(path):
    log.info( path )
    return Song(path)
pool = Pool()

class Playlist(object):

    def __init__(self, port):


        # get data from manager (see lib/server.py)
        DataManager.register('get_data')

        # manager port is one higher than listen port
        manager = DataManager(address=(Config.hostname, port + 1),
                authkey=Config.authkey)
        manager.connect()
        self.data = manager.get_data()

        playlist_data = None
        try:                playlist_data = self.data['playlist']
        except KeyError:    playlist_data = PlaylistFile.read()

        if playlist_data is None:
            playlist_data = PlaylistFile.read()

        # set default playlist data
        default_data = {
                'playlist'      : playlist_data,
                'continue'      : False,
                'repeat'        : False,
                'shuffle'       : False,
                'status'        : 'stopped',
                'index'         : 0,
                'song'          : None,
                'skip'          : False,
                'sum_bytes'     : 0,
                'progress'      : 0,
                'elapsed'       : 0,
        }
        for k, v in default_data.items():
            try:
                if self.data[k] is None:
                    self.data[k] = default_data[k]
            except KeyError:
                self.data[k] = default_data[k]

    def __str__(self):
        index   = self.data['index']
        pl      = self.data['playlist']
        new_pl  = []
        pl_len  = len(pl)
        if pl_len > 0:
            pad_digits = int(math.log10(pl_len)) + 1
        else:
            pl_len = 0
        for i, song in pl.iteritems():
            try:
                pre = post = " "
                if int(i) == index:
                    pre     = "*" * len(pre)
                    post    = " "
                new_pl.append(' '.join([
                    pre,
                    '%*d' % (pad_digits, i + 1),
                    "[", song.mimetype, "]",
                    unicode(song),
                    post
                ]))
            except:
                log.exception(song)
        return '\n'.join(new_pl)

    def __getattr__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def get_song(self):
        song    = None
        index   = self.data['index']
        if index == -1: return None
        try:                song = self.song()
        except KeyError:    return None

        self.data['status'] = 'playing'
        self.data['song']   = song

        return song

    def enqueue_list(self, path):
        results = []
        for base, dirs, files in walk(path):
            results.extend( realpath( join(base, f) ) for f in files )
        return results

    def enqueue(self, args):
        tracks  = streams = 0
        pl      = self.data['playlist']

        for arg in args:

            elist = relay = None

            if isfile( arg ):
                elist = [ realpath( arg ) ]
            elif is_stream( arg ):
                raise NotImplementedError # TODO
            else:
                assert isdir( arg )
                elist = self.enqueue_list( arg )
                elist.sort()

            if elist is not None:
                track_count = int(len(pl))
                if track_count == 0:    last = 0
                else:                   last = sorted(pl.keys())[-1] + 1

                songs = pool.map(crunch, elist)

                for i, song in enumerate( songs ):
                    if song.corrupt: continue
                    pl[i + last] = song
                tracks += int(len(pl)) - track_count

        try:
            self.data['playlist'] = pl
        except Exception, e:
            log.exception(e)

        # reached end of playlist, reset index
        if self.data['status'] == 'stopped' and int(self.data['index']) == - 1:
            self.data['index'] = 0

        return "Enqueued %s tracks in %s directories (%s streams)." % (tracks,
                                                                       len(args), streams)

    def remove(self):
        index = int(self.data['index'])
        pl = self.data['playlist']
        del pl[index]
        self.data['playlist'] = pl
        self.next()

    # TODO clear() should call remove(); cli should call remove to strip
    # would also be nice to return a list of *artists* whose tracks were
    # removed
    # by int
    def clear(self, regex=None):

        try:

            removed = []
            if regex:           # user passed in a regex
                regex           = re.compile(regex, re.IGNORECASE)
                data            = self.data
                old_playlist    = data['playlist']
                pl_keys         = sorted(old_playlist.keys())
                old_index       = data['index']
                new_playlist    = {}

                i = 0
                for pl_key in pl_keys:
                    old_song = old_playlist[pl_key]

                    # If the track does not match the removal regex (i.e.,
                    # should be kept), then append it and increment the
                    # index
                    if not re.search(regex, unicode(old_song)):
                        new_playlist[i] = old_playlist[pl_key]
                        i = i + 1
                    else:
                        removed.append(pl_key)
                        print "x ",
                        sys.stdout.flush()

                if len(removed) > 0:
                    # Then we may need to adjust now-playing pointer.  There
                    # are a few possibilities for mutating the playlist:
                    #
                    #   1) We clobbered the track at the index.  Reset
                    #   now-playing to the beginning of the playlist.
                    #
                    if old_index in removed:
                        data['index'] = 0
                        data['status'] = 'stopped'
                        data['song'] = ''
                        data['skip'] = True
                    else:
                    #
                    #   2) We removed n tracks coming before the index.
                    #   Shift now-playing index back n indices.
                    #   list or if we clobbered whatever it was pointing to in the
                    #   middle of the list.
                        data['index'] = (old_index) - len([t for t in removed if t < old_index])
                    #
                    #   3) We removed n tracks coming after the index.
                    #   No re-ordering necessary

                data['playlist'] = new_playlist
                self.data = data

            else:
                # clear everything
                self.data['playlist'] = {}

            return "%s tracks removed." % len(removed)

            # index           = self.data['index'] + 1
            # pl_len          = len(self.data['playlist'])
            # shuffle         = label_bool[self.data['shuffle']]
            # repeat          = label_bool[self.data['repeat']]
            # kontinue        = label_bool[self.data['continue']]
            # pad             = (72 - len(name) + 1) * '*'
            # Self            = unicode(self)
            # if self.status == "playing":
            #     percentage = int(( / song.size) / 100.0)
            # else:
            #     percentage = 0
        except:
            print type(old_song)
            print(old_song is None)

    def query(self):
        name            = "riddim"
        uptime          = self.uptime()
        status_symbol   = label_status[ self.status ]
        song            = self.get_song()
        #
        width           = 72
        fill            = '='
        blank           = '.'
        step            = 100 / float(width)
        #
        q               = []
        q.append("%s up %s sent %s total continue %s shuffle %s repeat %s index %s" % (name, uptime,
            filesizeformat(self.data["sum_bytes"]),
            self.data["continue"],
            self.data["shuffle"],
            self.data["repeat"],
            self.data["index"]
        ))
        q.append("%s %s" % (status_symbol, song))
        if self.status == "playing":
            percentage      = int(self.data["progress"] / step)
            fill            = percentage * '='
            blank           = (width - percentage) * '.'
            seconds_to_time = lambda x: time.strftime('%H:%M:%S', time.gmtime(x))
            q.append("%s %s [%s>%s] %s%%" %
                    (seconds_to_time(self.data["elapsed"]), seconds_to_time(song.length), fill, blank, percentage))
            q.append("%s" % (self))
        return '\n'.join( q )

    def index(self, index):

        if index == "+1":  # corresponds to option -n with no argument
            self.next()
        else:
            try:
                new_index   = int(index) - 1
                (first_index, last_index) = self.index_bounds()
                if new_index > last_index:      new_index = last_index
                elif new_index < first_index:   new_index = first_index
                self.data['index'] = new_index
            except ValueError:
                return "``%s'' is not an integer" % index

        if self.data['status'] == 'playing':
            self.data['skip'] = True

        return self.query()

    def index_bounds(self):
        sorted_indices = sorted(self.data['playlist'].keys())
        try:
            return (sorted_indices[0], sorted_indices[-1])
        except IndexError:
            return (0, 0)

    def uptime(self):
        delta = datetime.now() - self.data['started_at']
        hours, _ = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(_, 60)
        return "%sd %02dh %02dm %02ds" % \
               (delta.days, hours, minutes, seconds)

    def kontinue(self):
        self.toggle('continue')
        return self.query()

    def song(self):
        return self.data['playlist'][self.data['index']]

    def next_album(self):
        album_this = self.song().album
        while True:
            self.next()
            album_next = self.song().album
            if album_this != album_next: break
        return self.query()

    def next_artist(self):
        artist_this = self.song().artist.lower()
        while True:
            self.next()
            artist_next = self.song().artist.lower()
            if artist_this != artist_next: break
        return self.query()

    def repeat(self):
        self.toggle('repeat')
        return self.query()

    def shuffle(self):
        self.toggle('shuffle')
        return self.query()

    def next(self):
        if self.data['shuffle']:
            self.data['index'] = random.choice( self.data['playlist'].keys() )
        elif self.data['repeat']:
            pass
        else:
            new_index = int(self.data['index'] + 1)
            if not self.data['continue']:
                # prevent rollover
                first_index, last_index = self.index_bounds()
                if new_index > last_index:
                    self.data['index'] = 0
                    return
            self.data['index'] = new_index

    def toggle(self, key):
        self.data[key] = not(bool(self.data[key]))

    def save(self):
        PlaylistFile.save( self.data['playlist'] )
        # TODO
        #PlaylistFile.save( self.data )
