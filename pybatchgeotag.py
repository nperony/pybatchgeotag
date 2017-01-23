#!/usr/bin/env python

from __future__ import division
from builtins import input
import sys
import os
import glob
import logging
import datetime
import pytz
import numpy as np
import pandas as pd
from argparse import ArgumentParser
from pexif import JpegFile
from tzlocal import get_localzone

# we need to manually specify datetime formats because date is often weirdly written, like "2016:12:31"
# this confuses automatic parsers such as python-dateutil's
datetime_formats = ['%Y:%m:%d %H:%M:%S',
                    '%Y:%m:%d %H:%M:%S%Z',
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d %H:%M:%S%Z',
                    '%Y/%m/%d %H:%M:%S',
                    '%Y/%m/%d %H:%M:%S%Z']


def list_jpegs(folder='.', recursive=False):
    file_extensions = ['jpg', 'JPG', 'jpeg', 'JPEG']
    matched_files = []
    for fe in file_extensions:
        if not recursive:
            matched_files.extend(glob.glob(os.path.join(folder, '*.%s' % fe)))
        else:
            for root, folders, files in os.walk(folder):
                matched_files.extend(glob.glob(os.path.join(root, '*.%s' % fe)))
    return matched_files


def main(argv):
    arg_parser = ArgumentParser()
    arg_parser.add_argument('mode', choices=('convert', 'geotag'),
                            help=('"convert mode": creates a clean locations.csv file from a Google LocationHistory.json'
                                  'file. Geotagging arguments will be ignored. "geotag" mode: uses the coordinates file'
                                  ' passed as argument to geotag all the JPEG pictures in the target folder. Conversion'
                                  ' arguments will be ignored.'))
    arg_parser.add_argument('-l', '--location-history',
                            help='(convert mode) Google location history file (usually LocationHistory.json)')
    arg_parser.add_argument('-s', '--start-date', help='(convert mode) Start date (inclusive) for conversion, format YYYY-MM-DD')
    arg_parser.add_argument('-e', '--end-date', help='(convert mode) End date (inclusive) for conversion, format YYYY-MM-DD')
    arg_parser.add_argument('-a', '--accuracy', type=int, default=100,
                            help='(convert mode) Minimum accuracy of a location for it to be considered valid (default 100 metres)')
    arg_parser.add_argument('-c', '--coordinates', help='(geotag mode) Coordinates file (datetime, latitude, longitude)')
    arg_parser.add_argument('-n', '--no-header', action='store_true', default=False,
                            help='(geotag mode) Coordinates file has no header line (default false)')
    arg_parser.add_argument('-f', '--folder', help='(geotag mode) Folder where images are located (images will be overwritten!)')
    arg_parser.add_argument('-tz', '--timezone',
                            help='(geotag mode) Time zone (e.g., "UTC", or "Europe/Zurich") of the camera. It will be converted to your local time zone prior to geotagging')
    arg_parser.add_argument('-o', '--overwrite', action='store_true', default=False,
                            help='(geotag mode) Overwrite geodata for images that already have coordinates in EXIF (default false)')
    arg_parser.add_argument('-r', '--recursive', action='store_true', default=False,
                            help='(geotag mode) Browse folder recursively (default false)')
    arg_parser.add_argument('-rs', '--resampling_frequency', type=int, default=60,
                            help='(geotag mode) Resampling frequency of the coordinates time series, in seconds (default 60)')
    arg_parser.add_argument('-v', '--verbosity', type=int, default=2, choices=range(1, 4),
                            help='Verbosity level (1-3, default 2)')
    argv = argv[1:]
    args = arg_parser.parse_args(argv)

    verbosity_logger = {1: logging.ERROR, 2: logging.INFO, 3: logging.DEBUG}
    log_level = verbosity_logger[args.verbosity]
    sh = logging.StreamHandler(stream=sys.stdout)  # logging to stdout
    lf = logging.Formatter('%(levelname)s\t%(message)s')
    sh.setFormatter(lf)
    logger = logging.getLogger()
    logger.addHandler(sh)
    logger.setLevel(log_level)

    if args.mode == 'convert':
        if args.location_history is None:
            logger.error('Required argument: location-history (-l)')
            return
        try:
            dfraw = pd.read_json(args.location_history)
            sraw = dfraw['locations']  # Series
            logger.debug('Read %s locations from %s' % (len(sraw), args.location_history))
            df = pd.DataFrame()
            df['ts'] = sraw.apply(lambda x: int(x['timestampMs']))
            df['dt'] = df['ts'].apply(lambda x: datetime.datetime.fromtimestamp(x / 1000))  # produces naive timestamps in local timezone
            df['longitude'] = sraw.apply(lambda x: x['longitudeE7'] / 10000000.0)
            df['latitude'] = sraw.apply(lambda x: x['latitudeE7'] / 10000000.0)
            df['accuracy'] = sraw.apply(lambda x: x['accuracy'])
            df.sort_values(by='ts', inplace=True)
            df.set_index('dt', inplace=True)
        except:
            logger.error('Could not open/parse location history file.')
            logger.error('Message: %s' % sys.exc_info()[1])
            return
        # filtering DataFrame based on start date, end date, location accuracy
        if args.start_date:
            try:
                print(args.start_date)
                df = df[df.index >= datetime.datetime.strptime(args.start_date, '%Y-%m-%d')]
                logger.debug('Filtered to %s locations from %s or later' % (len(df), args.start_date))
            except:
                logger.error('Could not filter location history file based on start date. Is the date in YYYY-MM-DD format?')
                logger.error('Message: %s' % sys.exc_info()[1])
                return
        if args.end_date:
            try:
                df = df[df.index <= datetime.datetime.strptime(args.end_date, '%Y-%m-%d') + datetime.timedelta(days=1)]
                logger.debug('Filtered to %s locations from %s or earlier' % (len(df), args.end_date))
            except:
                logger.error('Could not filter location history file based on end date. Is the date in YYYY-MM-DD format?')
                logger.error('Message: %s' % sys.exc_info()[1])
                return
        df = df[df.accuracy <= args.accuracy]
        logger.debug('Filtered to %s locations with minimum accuracy %s metres' % (len(df), args.accuracy))
        try:
            if os.path.isfile('locations.csv'):
                cont = input('WARNING: the file locations.csv exists. Do you want to overwrite it? [N/y] ')
                if cont not in ['y', 'Y', 'yes', 'YES']:
                    return
            df.to_csv('locations.csv', index=True, columns=['latitude', 'longitude'])
        except:
            logger.error('Could not export filtered locations to locations.csv')
            logger.error('Message: %s' % sys.exc_info()[1])
            return
        logger.info('Exported %d locations to locations.csv' % len(df))
        if len(df)>0:
            logger.info('Range of the exported time series of coordinates: %s to %s' %
                        (df.index.min().strftime('%Y-%m-%d %H:%M:%S%z'), df.index.max().strftime('%Y-%m-%d %H:%M:%S%z')))
        return

    if (args.coordinates is None) or (args.folder is None):
        logger.error('Required arguments: coordinates (-c) folder (-f)')
        return

    if args.timezone is not None:
        try:
            cam_tz = pytz.timezone(args.timezone)
        except:
            logger.error('Argument does not seem to be a valid timezone: %s' % args.timezone)
            return
    else:
        cam_tz = get_localzone()
    local_tz = get_localzone()

    imgs = list_jpegs(args.folder, args.recursive)

    if not imgs:  # no image files found during scan
        logging.info('No JPEG image file found during %sscan of folder %s' %
                     ('recursive ' if args.recursive else '', args.folder))
        return
    warn_msg = '''WARNING: There are %s JPEG image files in the target folder(s).
         If present, their EXIF information will be overwritten, which may result in irremediable loss of data.
         Do you want to continue? [N/y] ''' % len(imgs)
    cont = input(warn_msg)
    if cont not in ['y', 'Y', 'yes', 'YES']:
        return

    try:
        dfloc = pd.read_csv(args.coordinates,
                            names=['dt', 'latitude', 'longitude'],
                            parse_dates=['dt'],
                            skiprows=0 if args.no_header else 1,
                            dtype={'latitude': np.float64, 'longitude': np.float64})
    except:
        logger.error('Could not open/parse coordinates file. '
                     'Are you sure it is a CSV with 3 columns: datetime (str), latitude (float), longitude (float)?')
        logger.error('Message: %s' % sys.exc_info()[1])
        return

    logging.debug('Opened coordinates file "%s", %d locations found' % (args.coordinates, len(dfloc)))

    # localising timestamps to local time zone
    dfloc.dt = dfloc.dt.apply(lambda x: pytz.utc.localize(x).astimezone(local_tz).replace(tzinfo=None))
    dfloc.set_index('dt', inplace=True)
    dfloc.sort_index(inplace=True)

    # resampling time series by taking the mean of points falling within a time bin, and interpolating linearly.
    # This is very fast only because we use linear interpolation.
    len_ = len(dfloc)
    dfloc = dfloc.resample('%dS' % args.resampling_frequency).mean().interpolate()
    logger.debug('Resampled coordinates to %d-second frequency, went from %d positions to %d'
                 % (args.resampling_frequency, len_, len(dfloc)))

    dt_min = dfloc.index[0].to_pydatetime()
    dt_max = dfloc.index[-1].to_pydatetime()
    logger.info('Datetime range of resampled coordinates file: %s to %s' %
                (dt_min.strftime('%Y-%m-%d %H:%M:%S%z'), dt_max.strftime('%Y-%m-%d %H:%M:%S%z')))

    for img in imgs:
        logger.debug('Opening %s to read EXIF data' % img)
        try:
            jf = JpegFile.fromFile(img)
        except:
            logger.error('Could not open %s. This file does not appear to have a valid EXIF structure' % img)
            continue
        try:
            exif = jf.get_exif().get_primary()
        except:
            logger.info('Could not read EXIF data from %s. Skipping file' % img)
            continue
        try:
            img_dt = exif.DateTime
            logger.debug('Read DateTime for %s: %s' % (img, img_dt))
        except:
            try:
                img_dt = exif.ExtendedEXIF.DateTimeOriginal
                logger.debug('Read DateTimeOriginal for %s: %s' % (img, img_dt))
            except:
                try:
                    img_dt = exif.ExtendedEXIF.DateTimeDigitized
                    logger.debug('Read DateTimeDigitized for %s: %s' % (img, img_dt))
                except:
                    logger.info('No datetime information found in EXIF for %s. Skipping file' % img)
                    continue

        for dtf in datetime_formats:
            try:
                img_dt = datetime.datetime.strptime(img_dt, dtf)
                break
            except ValueError:
                pass
        if not isinstance(img_dt, datetime.datetime):  # parsing failed:
            logger.info('Could not parse valid datetime information from EXIF for %s. Skipping file' % img)
            continue

        # localising image to local timezone, since location timestamps are local
        img_dt = cam_tz.localize(img_dt).astimezone(local_tz).replace(tzinfo=None)

        if not (dt_min <= img_dt <= dt_max):
            logger.info('Datetime information for %s (%s) is outside of target range. Skipping file' %
                        (img, img_dt.strftime('%Y-%m-%d %H:%M:%S%z')))
            continue

        try:
            (lng, lat) = jf.get_geo()
            has_geo = True
        except:
            has_geo = False

        if has_geo and not args.overwrite:
            logger.info('Found existing geodata for %s. Skipping file' % img)
            continue

        # DatetimeIndex.asof() returns last index in the past, so we need to add half a period to get the nearest one
        idx = dfloc.index.asof(img_dt + datetime.timedelta(seconds=args.resampling_frequency//2))
        if not isinstance(idx, pd.tslib.Timestamp) and np.isnan(idx):
            logger.error('Could not interpolate time index for %s. Skipping file' % img)
        lat_ = dfloc.latitude[idx]
        lng_ = dfloc.longitude[idx]

        logger.info('Setting geodata for %s to (%0.6f, %0.6f)' % (img, lat_, lng_))
        jf.set_geo(lat_, lng_)
        jf.writeFile(img)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
