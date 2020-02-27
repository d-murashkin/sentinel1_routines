""" Create a calibrated geotiff image.
"""
import numpy as np

from reader import Sentinel1Product
from writer import write_data_geotiff


def grayscale(input_path, output_path, band='hh', speckle_filter=True):
    """ Create a calibrated geotiff image for the specified Sentinel-1 product and band.
    """
    p = Sentinel1Product(input_path)
    p.read_data(parallel=True, keep_useless_data=False, crop_borders=False)
    if band.lower() == 'hh':
        p.HH.clip_normalize()
        img = p.HH.data
    elif band.lower() == 'hv':
        p.HV.clip_normalize()
        img = p.HV.data
    if speckle_filter:
        try:
            import cv2
            img = cv2.bilateralFilter(img, 25, 15, 15)
        except:
            print('Failed to apply speckle filter (bilateral filter from opencv).')
    img *= 255
    img = img.astype(np.uint8)
    write_data_geotiff(img, output_path, p.gdal_data)


def rgb(input_path, output_path, speckle_filter=True):
    p = Sentinel1Product(input_path)
    p.read_data(parallel=True, keep_useless_data=False, crop_borders=False)
    p.HH.clip_normalize()
    p.HV.clip_normalize()
    ratio = p.HV.data - p.HH.data
    ratio -= ratio.min()
    ratio /= ratio.max()
    img = np.stack([p.HH.data, p.HV.data, ratio], axis=2)
    if speckle_filter:
        try:
            import cv2
            img = cv2.bilateralFilter(img, 25, 15, 15)
        except:
            print('Failed to apply speckle filter (bilateral filter from opencv).')
    img *= 255
    img = img.astype(np.uint8)
    write_data_geotiff(img, output_path, p.gdal_data)


if __name__ == "__main__":
    pass
