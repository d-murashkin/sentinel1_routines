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
        p.read_data(keep_calibration_data=False, crop_borders=True, **kwargs)
    except Exception:
        return False
    
    imgs = []
    if (band.lower() == 'both') or (band.lower() == 'hh'):
        p.HH.clip_normalize(extend=False)
        imgs.append(p.HH.data)
    if (band.lower() == 'both') or (band.lower() == 'hv'):
        p.HV.clip_normalize(extend=False)
        imgs.append(p.HV.data)
    
    if speckle_filter:
        try:
            import cv2
            for img in imgs:
                img = cv2.bilateralFilter(img, 5, 15, 15)
        except Exception:
            print('Failed to apply speckle filter (bilateral filter from opencv).')
    for img in imgs:
        img *= 250
        img = img.astype(np.uint8) + 1
    write_data_geotiff(np.stack(imgs, axis=-1), output_path, p.gdal_data, nodata_val=nodata_value)
    return True


def rgb(input_path, output_path, speckle_filter=True, scale_noise=False, nodata_value=0, save_oceanmask=False, **kwargs):
    """ Create an RBG image from calibrated HH, HV and HV/HH bands of the specified Sentinel-1 product.
    """
    try:
        p = Sentinel1Product(input_path, scale_noise=scale_noise)
        p.read_data(keep_calibration_data=False, crop_borders=True, **kwargs)
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
    
    img = np.dstack([p.HH.data, p.HV.data, ratio])

    if speckle_filter:
        try:
            import cv2
            img = cv2.bilateralFilter(img, 5, 15, 15)
        except Exception:
            print('Failed to apply speckle filter (bilateral filter from opencv).')
    img *= 250
    img = img.astype(np.uint8) + 1

    if save_oceanmask:
        p.mask_land()
        img = np.dstack([img, ~p.landmask])
    write_data_geotiff(img, output_path, p.gdal_data, nodata_val=nodata_value)
    return True


def calibrated(input_path, output_path, scale_noise=False, speckle_filter=False, save_incidence_angle=False, channel='both', save_oceanmask=False, clip_normalize=False, **kwargs):
    """ Create a geotiff with calibrated data (in dB).
        If clip_normalize consists of two values, the output is normalized to the range.
    """
    try:
        p = Sentinel1Product(input_path, scale_noise=scale_noise)
        print(kwargs)
        p.read_data(keep_calibration_data=True, crop_borders=True, **kwargs)
    except Exception:
        print('Error reading {0}'.format(input_path))
        return False
    
    match channel.lower():
        case 'both':
            channels = [p.HH, p.HV]
        case 'hh':
            channels = [p.HH]
        case 'hv':
            channels = [p.HV]
        case _:
            print('Wrong channel type: {0}.'.format(channel))
            print('Choose one of the following: both, hh, hv.')
    
    if clip_normalize:
        [channel.clip_normalize(clip_normalize) for channel in channels]

    if speckle_filter:
        try:
            import cv2
            data = [cv2.bilateralFilter(channel.data, 5, 15, 15) for channel in channels]
        except Exception:
            data = [channel.data for channel in channels]
            print('Failed to apply speckle filter (bilateral filter from opencv).')
    else:
        data = [channel.data for channel in channels]
    
    data = np.dstack(data)

    if save_incidence_angle:
        p.interpolate_incidence_angle()
        data = np.dstack([data, p.incidence_angle])

    if save_oceanmask:
        p.mask_land()
        data = np.dstack([data, ~p.landmask])

    write_data_geotiff(data, output_path, p.gdal_data, nodata_val=np.nan)
    return True


if __name__ == "__main__":
    pass
