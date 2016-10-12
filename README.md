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
* You can generate the coordinates file manually, or use the `convert` option to extract a clean list of coordinates from a Google location history file (download from [Google Takeout](https://takeout.google.com/settings/takeout)).
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

Full call syntax:
```
usage: pybatchgeotag.py [-h] [-c COORDINATES] [-n] [-f FOLDER] [-o] [-r]
                        [-rs RESAMPLING_FREQUENCY] [-v {1,2,3}]

optional arguments:
  -h, --help            show this help message and exit
  -c COORDINATES, --coordinates COORDINATES
                        Coordinates file (datetime, latitude, longitude)
  -n, --no-header       Coordinates file has no header line (default false)
  -f FOLDER, --folder FOLDER
                        Folder where images are located (images will be overwritten!)
  -o, --overwrite       Overwrite geodata for images that already have
                        coordinates in EXIF (default false)
  -r, --recursive       Browser folder recursively (default false)
  -rs RESAMPLING_FREQUENCY, --resampling_frequency RESAMPLING_FREQUENCY
                        Resampling frequency in seconds (default 60)
  -v {1,2,3}, --verbosity {1,2,3}
                        Verbosity level (1-3, default 2)
```

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Acknowledgments

* Thanks to [Ben Leslie](https://github.com/bennoleslie/) for creating the pexif library used to manipulate EXIF data.
