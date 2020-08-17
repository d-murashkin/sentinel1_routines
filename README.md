Sentinel-1 routines:
* reader (EW swath products only)
    ```python
    from sentinel1_routines.reader import Sentinel1Product
    scene = Sentinel1Product(<path_to_scene>)
    scene.read_data()
    ```
    Now ```scene.HH.data``` and ```scene.HV.data``` are 2D arrays with calibrated HH and HV band backscatter values (in dB) of the scene.
* writer:
  * convert original scene to a rgb/grayscale(hh or hv) calibrated GeoTiff
  * write results in a GeoTiff with the same GCPs as the corresponding original scene

Routines in plan:
* plotter (basemap, cartopy)
