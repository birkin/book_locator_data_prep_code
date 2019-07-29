# -*- coding: utf-8 -*-

"""
Book Locator logic.
"""
import os
import logging
import sys
logger = logging.getLogger('bibutils')
assert sys.version_info.major > 2

import bisect
import json


from callnumber import brown

DATA_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    'data',
    'index'
)

class LocateData(object):

    def __init__(self, location, index=False, meta=False):
        if (index is False) and (meta is False):
            raise Exception("Either index or meta must be true")
        self.location = location
        if index is True:
            self.prefix = 'index'
        else:
            self.prefix = 'meta'

    def _data_filename(self, prefix):
        fn = "{}_{}.json".format(self.location, self.prefix)
        return os.path.join(DATA_DIR, fn)

    def dump(self, data):
        fn = self._data_filename(self.location)
        with open(fn, 'wb') as pfile:
            json.dump(data, pfile)
        return True

    def load(self):
        fn = self._data_filename(self.location)
        with open(fn) as pfile:
            data = json.load(pfile)
        return data


class Locate(object):

    def __init___(self, normalized_callnumber, location):
        self.callnumber = normalized_callnumber
        self.location = location
        self.index = LocateData(location, index=True).load()
        self.meta = LocateData(location, meta=True).load()

    def locate_call(self):
        position = bisect.bisect(self.index, self.callnumber)
        return self.index[position]

    def locate(self):
        normal_start = self.locate_call()
        #Get the full metadata about the item
        return self.meta.get(normal_start)
        # return {
        #     'floor': None,
        #     'aisle': None,
        #     'side': None,
        #     #Flag as to whether this item was found.
        #     'located': None,
        # }

def run(callnumber, location):
    # lower case location
    location = location.strip().lower()
    # upcase call numbers
    callnumber = callnumber.strip().upper()
    try:
        normalized_callnumber = brown.normalize(callnumber, location).upper()
    except AttributeError:
        log.info("Could not normalize callnumber {}.".format(callnumber))
        return None
    try:
        index = LocateData(location, index=True).load()
        meta = LocateData(location, meta=True).load()
    except IOError:
        log.error("Could not load meta or index for {}.".format(location))
        return None
    position = bisect.bisect(index, normalized_callnumber)
    meta_key = index[position - 1]
    loc_data = meta.get(meta_key)
    located = False
    if loc_data is not None:
        located = True
    aisle = loc_data.get('aisle').upper()
    return {
        'floor': unicode(loc_data.get('floor')).upper(),
        'aisle': aisle,
        # For display we will split out aisle and side.
        'display_aisle': "".join(aisle[:-1]),
        # Side is included in aisle as last character.
        'side': aisle[-1].upper(),
        'location': location,
        #Flag as to whether this item was found.
        'located': located,
        }

class ServiceLocator(object):
    """
    Class for use in web app or script calling locator
    repeatedly.
    """

    def __init__(self):
        self.locations = ['sci', 'rock', 'rock-chinese', 'rock-korean', 'rock-japanese']
        for loc in self.locations:
            try:
                setattr(
                    self,
                    "{}_index".format(loc),
                    LocateData(loc, index=True).load()
                )
                setattr(
                    self,
                    "{}_meta".format(loc),
                    LocateData(loc, meta=True).load()
                 )
            except IOError:
                log.error("Could not load meta or index for {}.".format(loc))

    def _data(self, normalized, location):
        index = getattr(self, "{}_index".format(location))
        meta = getattr(self, "{}_meta".format(location))
        position = bisect.bisect(index, normalized)
        meta_key = index[position - 1]
        loc_data = meta.get(meta_key)
        return loc_data

    def run(self, callnumber, location):
        if location not in self.locations:
            log.debug("Location not in possbile locations.")
        # lower case location
        location = location.strip().lower()
        # upcase call numbers
        callnumber = callnumber.strip().upper()
        try:
            normalized_callnumber = brown.normalize(callnumber, location).upper()
        except AttributeError:
            log.info("Could not normalize callnumber {}.".format(callnumber))
            return None
        loc_data = self._data(normalized_callnumber, location)
        located = False
        if loc_data is not None:
            located = True
        aisle = loc_data.get('aisle').upper()
        return {
            'floor': unicode(loc_data.get('floor')).upper(),
            'aisle': aisle,
            # For display we will split out aisle and side.
            'display_aisle': "".join(aisle[:-1]),
            # Side is included in aisle as last character.
            'side': aisle[-1].upper(),
            'location': location,
            #Flag as to whether this item was found.
            'located': located,
            }
import sys
if __name__ == u'__main__':
    bk = ServiceLocator()
    lookup = 'PS3568.U812 R57x 1994'
    if len(sys.argv)>1:
      lookup = sys.argv[1]
    print json.dumps(
        bk.run(lookup, 'rock'),
        indent=2
    )
