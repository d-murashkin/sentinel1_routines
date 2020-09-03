""" Create a calibrated geotiff image.
"""
import numpy as np

from sentinel1_routines.reader import Sentinel1Product
from sentinel1_routines.writer import write_data_geotiff


def grayscale(input_path, output_path, band='hh', speckle_filter=True, incidence_angle_correction=True):
    """ Create a calibrated geotiff image for the specified Sentinel-1 product and band.
    """
    p = Sentinel1Product(input_path)
    p.read_data(parallel=True, keep_useless_data=False, crop_borders=False, incidence_angle_correction=incidence_angle_correction)
    if band.lower() == 'hh':
        p.HH.clip_normalize()
        img = p.HH.data
    elif band.lower() == 'hv':
        p.HV.clip_normalize()
        img = p.HV.data
    if speckle_filter:
        try:
            import cv2
            img = cv2.bilateralFilter(img, 5, 15, 15)
        except:
            print('Failed to apply speckle filter (bilateral filter from opencv).')
    img *= 255
    img = img.astype(np.uint8)
    write_data_geotiff(img, output_path, p.gdal_data)


def rgb(input_path, output_path, speckle_filter=True, incidence_angle_correction=True):
    """ Create an RBG image from calibrated HH, HV and HV/HH bands of the specified Sentinel-1 product.
    """
    try:
        p = Sentinel1Product(input_path)
    except:
        print('Error reading {0}'.format(input_path))
        return False
    p.read_data(parallel=True, keep_useless_data=False, crop_borders=False, incidence_angle_correction=incidence_angle_correction)
    p.HH.clip_normalize(extend=False)
    p.HV.clip_normalize(extend=False)
    ratio = p.HV.data - p.HH.data
    ratio *= 0.5
    ratio += 0.5
    ratio[ratio < 0] = 0
    ratio[ratio > 1] = 1
    
    img = np.stack([p.HH.data, p.HV.data, ratio], axis=2)
    if speckle_filter:
        try:
            import cv2
            img = cv2.bilateralFilter(img, 5, 15, 15)
        except:
            print('Failed to apply speckle filter (bilateral filter from opencv).')
    img *= 255
    img = img.astype(np.uint8)
    write_data_geotiff(img, output_path, p.gdal_data)


def calibrated(input_path, output_path, speckle_filter=True, save_incidence_angle=False, incidence_angle_correction=True):
    """ Create a geotiff with calibrated data (in dB).
    """
    p = Sentinel1Product(input_path)
    p.read_data(parallel=True, keep_useless_data=True, crop_borders=False, incidence_angle_correction=incidence_angle_correction)
    bands = [p.HH.data, p.HV.data]
    if save_incidence_angle:
        p.interpolate_incidence_angle()
        bands.append(p.incidence_angle)
    data = np.stack(bands, axis=2)
    write_data_geotiff(data, output_path, p.gdal_data)


if __name__ == "__main__":
    pass
