# -*- coding: utf-8 -*-

"""
Create an index of the current data that will be used by the web app
to resolve locations.

Build two json for each location.
 - sorted list of call numbers
 - dictionary with full location information that can be used for display

"""
from datetime import datetime
from time import mktime
from time import strptime
import json
import logging
import pickle
import sys
assert sys.version_info.major > 2

from book_locator_data_prep_code import data_prep_settings as dp_settings
from booklocator.locate import LocateData
from callnumber.brown import Item
from oauth2client.client import SignedJwtAssertionCredentials
import gspread
import json


# Logging
logging.basicConfig(filename=dp_settings.LOG_FILENAME,
                    level=logging.DEBUG,
                    format='%(asctime)s %(message)s',
)
# Turn off other loggers
log = logging.getLogger("oauth2client").setLevel(logging.WARNING)


try:
    FORCE_REINDEX = sys.argv[1] == 'force'
    log.info("Forcing a book locator reindex")
except IndexError:
    FORCE_REINDEX = None

META_FILE = 'data/.meta.pkl'


#
# Setup Google Spreadsheet connection.
#
with open( dp_settings.gsheet_key_path ) as f:
    json_key = f.read()

scope='https://spreadsheets.google.com/feeds'
credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'].encode(), scope)

gc = gspread.authorize(credentials)


# List of gsheets and location codes that we will index.  These
# are the "locatable" locations.
groups = [
    {
        'location_code': 'rock',
        'gid': dp_settings.ROCK_GID
    },
    {
        'location_code': 'sci',
        'gid': dp_settings.SCI_GID
    },
    {
        'location_code': 'rock-chinese',
        'gid': dp_settings.ROCK_CHINESE,
        'worksheet': 'chinese'
    },
    {
        'location_code': 'rock-japanese',
        'gid': dp_settings.ROCK_JAPANESE,
        'worksheet': 'japanese'
    },
    {
        'location_code': 'rock-korean',
        'gid': dp_settings.ROCK_KOREAN,
        'worksheet': 'korean'
    },
]


def gget(d, k):
    """
    Function to get a cell from the gspread
    and return None rather than an empty string.

    :param d:
    :param k:
    :return:
    """
    val = d.get(k, None)
    if val is None:
        return None
    elif val.strip() == u"":
        return None
    else:
        return val

def build_item(location, begin):
    item = Item(begin, location)
    try:
        n = item.normalize()
        return n
    except ValueError:
        print>>sys.stderr, "Can't normalize", location, begin
        return None


def make_last_updated_date(raw):
    """
    Turn the Gspread updated date into a python datetime.
    """
    chunked = raw.split('T')
    yr, month, dy = chunked[0].split('-')
    hour, minute, _  = chunked[1].split(':')
    formatted_time = "{}-{}-{} {}:{}".format(yr, month, dy, hour, minute)
    upd = strptime(formatted_time, '%Y-%m-%d %H:%M')
    #Convert to datetime object
    dt = datetime.fromtimestamp(mktime(upd))
    return dt

def load_meta():
    try:
        with open(META_FILE) as inf:
            return pickle.load(inf)
    except IOError, ValueError:
        return None

def get_index_last_updated():
    meta = load_meta()
    if meta is not None:
        return meta.get('updated')

def set_index_last_updated(timestamp=datetime.utcnow()):
    meta = load_meta() or {}
    meta['updated'] = timestamp
    with open(META_FILE, 'wb') as outf:
        pickle.dump(meta, outf)

def check_last_update(worksheet):
    if FORCE_REINDEX is not True:
        spread_updated = make_last_updated_date(worksheet.updated)
        index_updated = get_index_last_updated()
        if (index_updated) and (spread_updated < index_updated):
            logging.info(
                "Skipping reindex because spreadsheet updated: {} and last index: {}"\
                .format(spread_updated, index_updated)
            )
            return False
    return True

def index_group(location_code, gid, worksheet):
    logging.info("Indexing location code: {}\nWith ID: {}".format(location_code, gid))
    try:
        spread = gc.open_by_key(gid)
    except Exception as e:
        logging.error("Error in {}\nMessage: {}".format(gid, e.message))
        raise e


    # If no worksheet is passed in, get all worksheets in spread.
    if worksheet is None:
        sheets = spread.worksheets()
    else:
        sheets = [spread.worksheet(worksheet)]

    locate_index = {}
    range_start_list = []

    has_changed = False

    # Go through each sheet and see if it has changed.
    # If any sheet in the set has changed, reindex.
    for worksheet in sheets:
        should_index = check_last_update(worksheet)
        if should_index is True:
            has_changed = True

    if has_changed is False:
        logging.info("Skipping location code {}. No data changed.".format(location_code))
        return

    # Actually index the sheet.
    for worksheet in sheets:
        logging.info("Indexing worksheet {}".format(worksheet.title))
        for rec in worksheet.get_all_records():
            aisle_meta = rec.copy()
            begin = gget(rec, 'begin')
            if begin is None:
                logging.warning("No begin range")
                continue
            normalized_range_start = build_item(location_code, begin)
            range_start_list.append(normalized_range_start)
            aisle_meta['normalized_start'] = normalized_range_start
            locate_index[normalized_range_start] = aisle_meta

    # Dump the metadata to the file system.
    ld = LocateData(location_code, meta=True)
    ld.dump(locate_index)

    # Dump the index, which is a sorted listed of normalized call numbers.
    range_start_list.sort()
    ld = LocateData(location_code, index=True)
    ld.dump(range_start_list)


def main():
    for grp in groups:
        index_group(grp['location_code'], grp['gid'], grp.get('worksheet'))
    set_index_last_updated()


if __name__ == "__main__":
    main()
