## Use the shell script to convert Sentinel-1 EW scenes to GeoTiff image
Convert a Sentinel-1 EW scene in a calibrated GeoTiff:
```console
python apply_clibration.py -i <input> -o <output>
```

## Requirements
The following python packages are needed:
* numpy
* scipy
* gdal
* pillow

Use conda to install the required libraries:
```sh
conda install numpy scipy gdal pillow
```


## How to use routines in python:
  * read a Sentinel-1 EW scene (zipped or unzipped):
    ```python
    from sentinel1_routines.reader import Sentinel1Product
    scene = Sentinel1Product(<path_to_scene>)
    scene.read_data()
    ```
    Now ```scene.HH.data``` and ```scene.HV.data``` are 2D arrays with calibrated HH and HV band backscatter values (in dB) of the scene.
  * let's calculate something, for example:
    ```python
    result = scene.HV.data - scene.HH.data
    ```
    and decrease resolution two times:
    ```python
    result = result[::2, ::2]
    ```
  * write results in a GeoTiff with the same GCPs as the corresponding original scene
    ```python
    from sentinel1_routines.writer import write_data_geotiff
    write_data_geotiff(result, <output_path>, scene.gdal_data, dec=2, nodata_val=<nodata value>)
    ```
    where decrement is ratio of dimentions: ```scene.HH.data.shape``` to ```result.shape```. So decrement is how many times resolution of the result is smaller that the resolution of the origina scene.
    <output_path> is now a geotiff with same Ground Control Points (GCPs) as the original and contains a four times smaller image (```result```).