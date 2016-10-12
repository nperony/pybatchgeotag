#!/usr/bin/env python

from __future__ import division
from builtins import input
import sys
import os
import glob
import logging
import datetime
import numpy as np
import pandas as pd
from argparse import ArgumentParser
from pexif import JpegFile

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
    arg_parser.add_argument('-c', '--coordinates', help='Coordinates file (datetime, latitude, longitude)')
    arg_parser.add_argument('-n', '--no-header', action='store_true', default=False,
                            help='Coordinates file has no header line (default false)')
    arg_parser.add_argument('-f', '--folder', help='Folder where images are located (images will be overwritten!)')
    arg_parser.add_argument('-o', '--overwrite', action='store_true', default=False,
                            help='Overwrite geodata for images that already have coordinates in EXIF (default false)')
    arg_parser.add_argument('-r', '--recursive', action='store_true', default=False,
                            help='Browser folder recursively (default false)')
    arg_parser.add_argument('-rs', '--resampling_frequency', type=int, default=60,
                            help='Resampling frequency in seconds (default 60)')
    arg_parser.add_argument('-v', '--verbosity', type=int, default=2, choices=range(1, 4),
                            help='Verbosity level (1-3, default 2)')
    argv = argv[1:]
    args = arg_parser.parse_args(argv)
    if not argv:  # no arguments given
        arg_parser.print_help()
        sys.exit(1)

    verbosity_logger = {1: logging.ERROR, 2: logging.INFO, 3: logging.DEBUG}
    log_level = verbosity_logger[args.verbosity]
    sh = logging.StreamHandler(stream=sys.stdout)  # logging to stdout
    lf = logging.Formatter('%(levelname)s\t%(message)s')
    sh.setFormatter(lf)
    logger = logging.getLogger()
    logger.addHandler(sh)
    logger.setLevel(log_level)

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

    logging.debug('Opened coordinates file "%s", %d locations found' % (args.coordinates, len(dfloc)))
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
            logger.debug('Read DateTime for %s' % img)
        except:
            try:
                img_dt = exif.ExtendedEXIF.DateTimeOriginal
                logger.debug('Read DateTimeOriginal for %s' % img)
            except:
                try:
                    img_dt = exif.ExtendedEXIF.DateTimeDigitized
                    logger.debug('Read DateTimeDigitized for %s' % img)
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
        logger.debug('Parsed datetime information for %s with format "%s": %s' %
                     (img, dtf, img_dt.strftime('%Y-%m-%d %H:%M:%S%z')))

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
