""" Create a calibrated geotiff image.
"""
import numpy as np

from .reader import Sentinel1Product
from .writer import write_data_geotiff


def grayscale(input_path, output_path, band='hh', speckle_filter=True, scale_noise=False, nodata_value=0, **kwargs):
    """ Create a calibrated geotiff image for the specified Sentinel-1 product and band.
    """
    try:
        p = Sentinel1Product(input_path, scale_noise=scale_noise)
        p.read_data(keep_calibration_data=False, crop_borders=False, **kwargs)
    except Exception:
        return False
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
        except Exception:
            print('Failed to apply speckle filter (bilateral filter from opencv).')
    img *= 250
    img = img.astype(np.uint8) + 1
    write_data_geotiff(img, output_path, p.gdal_data, nodata_val=nodata_value)
    return True


def rgb(input_path, output_path, speckle_filter=True, scale_noise=False, nodata_value=0, **kwargs):
    """ Create an RBG image from calibrated HH, HV and HV/HH bands of the specified Sentinel-1 product.
    """
    try:
        p = Sentinel1Product(input_path, scale_noise=scale_noise)
        p.read_data(keep_calibration_data=False, crop_borders=False, **kwargs)
    except Exception:
        print('Error reading {0}'.format(input_path))
        return False
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
        except Exception:
            print('Failed to apply speckle filter (bilateral filter from opencv).')
    img *= 250
    img = img.astype(np.uint8) + 1
    write_data_geotiff(img, output_path, p.gdal_data, nodata_val=nodata_value)
    return True


def calibrated(input_path, output_path, save_incidence_angle=False, band='both', **kwargs):
    """ Create a geotiff with calibrated data (in dB).
    """
    try:
        p = Sentinel1Product(input_path)
        p.read_data(keep_calibration_data=True, crop_borders=False, **kwargs)
    except Exception:
        print('Error reading {0}'.format(input_path))
        return False

    if band.lower() == 'both':
        bands = [p.HH.data, p.HV.data]
    elif band.lower() == 'hh':
        bands = [p.HH.data]
    elif band.lower() == 'hv':
        bands = [p.HV.data]
    else:
        print('Wrong band type: {0}.'.format(band))
        print('Choose one of the following: both, hh, hv.')
    if save_incidence_angle:
        p.interpolate_incidence_angle()
        bands.append(p.incidence_angle)
    data = np.stack(bands, axis=2)
    write_data_geotiff(data, output_path, p.gdal_data)
    return True


if __name__ == "__main__":
    pass
