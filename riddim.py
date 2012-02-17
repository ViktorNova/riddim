#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
riddim.py Copyright (©) <2012> <Noah K. Tilton> <noahktilton@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""

import sys, codecs, socket

from lib.logger import log
from lib.args import Args
from lib.control import Control
from lib.playlist import Playlist

# needed if LANG=en_US.UTF-8
sys.stdout = codecs.getwriter('utf8')( sys.stdout )

if __name__ == "__main__":

    args = Args()

    if args.signal:
        {
                "start"     : Control().start,
                "stop"      : Control().stop,
        }[ args.signal ]()

    else:
        playlist = Playlist()
        if args.query:
            print playlist.query()
        elif args.shuffle:
            print playlist.shuffle()
        else:
            for action, arg in args.args_dict.items():
                    print {
                        "clear"         : playlist.clear,
                        "index"         : playlist.index,
                        "query"         : playlist.query,
                        "enqueue"       : playlist.enqueue,
                        "repeat"        : playlist.repeat,
                        "continue"      : playlist.kontinue,
                        "shuffle"       : playlist.shuffle
                    }[ action ]( arg )
    sys.exit(0)
