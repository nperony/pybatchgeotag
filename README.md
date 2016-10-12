# pybatchgeotag
Python script to geotag a collection of pictures by interpolating geographic coordinates coming from an external source (for example the location history of a smartphone).

This tool relies on [pexif](https://github.com/bennoleslie/pexif) to extract and modify EXIF data in JPEG files, and on [pandas](http://pandas.pydata.org/) for fast interpolation of timeseries data.

## Compatibility

Python2 only for now, as pexif is not Python3-compatible.

## Requirements

* pexif (bundled)
* pandas >= 0.18.0

## Important to know

* The program takes as input a CSV file containing a list of coordinates with a corresponding time stamp
* You can generate the coordinates file manually, or use the `convert` mode to extract a clean list of coordinates from a Google location history file (download from [Google Takeout](https://takeout.google.com/settings/takeout)).
* During conversion of a location history file, the coordinates will be given a time stamp in your local time zone.
* Files with a time stamp outside the range of the coordinates file will be ignored during the geotagging process.
* For geotagging, the series of coordinates will be linearly interpolated at a high temporal resolution (by default one location every minute), and each picture will be assigned the location of the nearest interpolated location.

After conversion or manual creation, your location file should look like this (the time stamp may or may not include timezone information). Headers are unimportant (use `--no-header` if they are absent), but the order of the columns should be `datetime, latitude, longitude`.
```
dt,latitude,longitude
2016-03-27 05:00:27.380000+00:00,47.3915287,8.5388783
2016-03-27 05:01:04.280000+00:00,47.3915245,8.5388878
2016-03-27 05:10:41.796000+00:00,47.3915511,8.5389044
```

## How to use

Download the script (`pygeobatch.py`) and the EXIF library (`pexif.py`), and run with `python pybatchgeotag.py`.

### Converting a location history file
```
python pybatchgeotag.py convert -l LocationHistory.json -a 200 -s 2016-03-01 -e 2016-07-01
```
Parses the file `LocationHistory.json` (usually downloaded from [Google Takeout](https://takeout.google.com/settings/takeout)), and writes the locations recorded between 2016-03-01 and 2016-07-01 with a minimum positioning accuracy of 200 metres to the new file `locations.csv`.

### Geotagging a picture collection
```
python geotag -c locations.csv -f pictures/ -r
```
Scans the folder "pictures" recursively, and applies to each image that does not already have one a geotag inferred from a linear interpolation of the coordinates contained in `locations.csv`.

Full call syntax:
```
usage: pybatchgeotag.py [-h] [-l LOCATION_HISTORY] [-s START_DATE]
                        [-e END_DATE] [-a ACCURACY] [-c COORDINATES] [-n]
                        [-f FOLDER] [-o] [-r] [-rs RESAMPLING_FREQUENCY]
                        [-v {1,2,3}]
                        {convert,geotag}

positional arguments:
  {convert,geotag}      "convert mode": creates a clean locations.csv file
                        from a Google LocationHistory.jsonfile. Geotagging
                        arguments will be ignored. "geotag" mode: uses the
                        coordinates file passed as argument to geotag all the
                        JPEG pictures in the target folder. Conversion
                        arguments will be ignored.

optional arguments:
  -h, --help            show this help message and exit
  -l LOCATION_HISTORY, --location-history LOCATION_HISTORY
                        (convert mode) Google location history file (usually
                        LocationHistory.json)
  -s START_DATE, --start-date START_DATE
                        (convert mode) Start date (inclusive) for conversion,
                        format YYYY-MM-DD
  -e END_DATE, --end-date END_DATE
                        (convert mode) End date (inclusive) for conversion,
                        format YYYY-MM-DD
  -a ACCURACY, --accuracy ACCURACY
                        (convert mode) Minimum accuracy of a location for it
                        to be considered valid (default 100 metres)
  -c COORDINATES, --coordinates COORDINATES
                        (geotag mode) Coordinates file (datetime, latitude,
                        longitude)
  -n, --no-header       (geotag mode) Coordinates file has no header line
                        (default false)
  -f FOLDER, --folder FOLDER
                        (geotag mode) Folder where images are located (images
                        will be overwritten!)
  -o, --overwrite       (geotag mode) Overwrite geodata for images that
                        already have coordinates in EXIF (default false)
  -r, --recursive       (geotag mode) Browse folder recursively (default
                        false)
  -rs RESAMPLING_FREQUENCY, --resampling_frequency RESAMPLING_FREQUENCY
                        (geotag mode) Resampling frequency of the coordinates
                        time series, in seconds (default 60)
  -v {1,2,3}, --verbosity {1,2,3}
                        Verbosity level (1-3, default 2)
```

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Acknowledgments

* Thanks to [Ben Leslie](https://github.com/bennoleslie/) for creating the pexif library used to manipulate EXIF data.
