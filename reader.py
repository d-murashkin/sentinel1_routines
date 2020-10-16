"""
Sentinel-1 EW reader.
The script provides Sentinel1Product and Sentinel1Band classes.
Sentinel1Product class describes the product and consists of two Sentinel1Band classes, landmask
information (and function to find it), location of borders (x_min and x_max).
Sentinel1Band class describes a band of Sentinel-1 product.
In addition to band data, the class includes information about noise, calibration parameters,
geolocation grid and functions to calculate these parameters.
NOTE: currently incidence angle correction can not be turned off for HH band.

@author: Dmitrii Murashkin
"""
import os
import zipfile
from xml.etree import ElementTree
from datetime import datetime
from multiprocessing.pool import ThreadPool
from io import BytesIO
from functools import partial

import numpy as np
from scipy.interpolate import RectBivariateSpline
from scipy.interpolate import griddata
from scipy.interpolate import interp1d
from PIL import Image

from sentinel1_routines.utils import scene_time

Image.MAX_IMAGE_PIXELS = None   # turn off the warning about large image size


class Sentinel1Band(object):
    """ Represents a Sentinel-1 band of a Sentinel-1 product.
        It is initialized with paths for data, annotation, calibration and noise files as well as with the band name.
        It has the following attributes:
            des - band designator or short name: 'hh' or 'hv'
            data_path - path to the tiff file that contains band data (or a ZipExtFile instance)
            noise_path - path to the xml file that contains noise LUT (or a ZipExtFile instance)
            calibration_path - path to the xml file thant containes calibration parameters LUT (or a ZipExtFile instance)
            annotation_path - path to the xml file with annotation (or a ZipExtFile instance)
            denoised - flag, showing if data has been denoised (to prevent double noise removal)
            Image band max and min values are taken from kmeans cluster analysis of a set of images.
                For more information look into 'gray_level_reduction.py'
        The following methods are available:
            read_data() -- should be executed first
            read_noise()
            read_calibration()
            subtract_noise()
            incidence_angle_correction(elevation_angle)
    """
    def __init__(self, data_path, annotation_path, calibration_path, noist_path, band_name):
        self.des = band_name.lower()
        self.img_max = 4 if self.des == 'hh' else -15
        self.img_min = -29 if self.des == 'hh' else -32
        self.incidence_angle_correction_coefficient = 0.213 if self.des == 'hh' else 0.053
        self.data_path = data_path
        self.noise_path = noist_path
        self.calibration_path = calibration_path
        self.annotation_path = annotation_path
        self.denoised = False

    def read_data(self):
        if type(self.data_path) is str:
            data = Image.open(self.data_path)
        else:
            unziped_bytes = BytesIO(self.data_path.read())
            data = Image.open(unziped_bytes)
        self.data = np.array(data, dtype=np.float32)
        self.denoised = False
        self.X, self.Y = self.data.shape
        self.nodata_mask = np.where(self.data == 0, True, False)

    def read_noise(self, azimuth_noise=True):
        """ Read noise table from the band noise file, interpolate it for the entire image.
            self.noise has same shape as self.data
        """
        if not hasattr(self, 'X') or not hasattr(self, 'Y'):
            print('Read data first.')
            return False

        """ First, deal with noise in the range direction. """
        noise_file = ElementTree.parse(self.noise_path).getroot()
        noise = np.array([j for i in noise_file[1] for j in i[3].text.split(' ')], dtype=np.float32)
        noise_y = np.array([j for i in noise_file[1] for j in i[2].text.split(' ')], dtype=np.int16)
        noise_x = np.array([i[1].text for i in noise_file[1] for j in range(int(i[2].get('count')))], dtype=np.int16)
        """
            2D interpolation:
                RectBivariateSpline can be used for regular grid only, this is not the option for
                    Sentinel-1 since noise data can contain differend number of values for each row.
                interp2d introduces horisontal stripes into noise data
                griddata seems to be the best solution
        """
        x_new = np.arange(0, self.X, 1, dtype=np.int16)
        y_new = np.arange(0, self.Y, 1, dtype=np.int16)
        xx, yy = np.meshgrid(y_new, x_new)
        self.noise = griddata(np.vstack((noise_y, noise_x)).transpose(), noise, (xx, yy),
                              method='linear', fill_value=0).astype(np.float32)
        """ if noise data has incorrect units (before July 2015) than scale it:
            noise_scaled = noise * k_noise * DN
            where k_noise is 56065.87 (given at a ESA document),
            DN is given in the band calibration file (index 6)
        """
        if self.noise.max() < 1:
            cf = ElementTree.parse(self.calibration_path).getroot()
            DN = float(cf[2][0][6].text.split(' ')[0])
            self.noise *= 56065.87 * DN
        
        """ Second, take into account noise in the azimuth direction (if possible).
            According https://qc.sentinel1.eo.esa.int/ipf/ only products taken after 13 March 2018 containg this information. """
        if azimuth_noise:
            try:
                self._read_azimuth_noise(noise_file)
                self.noise *= self.azimuth_noise
            except:
                print('Failed to read azimuth noise (this is normal for Sentinel-1 scenes taken before 13 March 2018).')
    
    def _read_azimuth_noise(self, noise_file):
        """ Read scalloping noise data.
            The noise file should be passed here for support of zip-archives.
            If .SAFE folder is used as input for the Sentinel1Product then noise_file can be taken from self.noise_file.
        """
        self.scalloping_lut = [{'line_min': int(i[1].text), 'line_max': int(i[3].text), 'sample_min': int(i[2].text), 'sample_max': int(i[4].text),
                                'lines': np.array(i[5].text.split(' '), dtype=np.int16), 'noise': np.array(i[6].text.split(' '), dtype=np.float32)} for i in noise_file[2]]

        """ Interpolate scalloping noise """
        self.azimuth_noise = np.zeros((self.X, self.Y), dtype=np.float32)
        for patch in self.scalloping_lut:
            scalloping = interp1d(patch['lines'], patch['noise'], kind='linear', fill_value='extrapolate')
            noise_line = scalloping(np.arange(patch['line_min'], patch['line_max'] + 1))
            self.azimuth_noise[patch['line_min']:patch['line_max'] + 1, patch['sample_min']:patch['sample_max'] + 1] = noise_line[:, np.newaxis]

    def read_calibration(self):
        """ Read calibration table from product folder.
            cal_par - calibration parameter number: 3 - SigmaNought, 4 - BetaNought,
            5 - gamma, 6 - dn. These parameters are given in the band calibration file
            self.calibration has same shape as self.data
            All 4 parameters are read, than only sigma is interpolated for entire image.
        """
        if not hasattr(self, 'X') or not hasattr(self, 'Y'):
            print('Read data first.')
            return False

        calibration_file = ElementTree.parse(self.calibration_path).getroot()
        calibration_x = int(calibration_file[2].get('count'))
        calibration_y = int(calibration_file[2][0][2].get('count'))
        result = []
        for cal_par in [3, 4, 5, 6]:
            calibration = np.array([i[cal_par].text.split(' ') for i in calibration_file[2]], dtype=np.float32).ravel()
            result.append(np.array(calibration).reshape(calibration_x, calibration_y))
        self.sigma0, self.beta0, self.gamma, self.dn = result

        self.calibration_azimuth_list = [int(i) for i in calibration_file[2][0][2].text.split(' ')]
        self.calibration_range_list = [int(i) for i in [j[1].text for j in calibration_file[2]]]

        gamma_interp = RectBivariateSpline(self.calibration_range_list, self.calibration_azimuth_list, self.gamma, kx=1, ky=1)
        x_new = np.arange(0, self.X, 1, dtype=np.int16)
        y_new = np.arange(0, self.Y, 1, dtype=np.int16)
        self.calibration = gamma_interp(x_new, y_new).astype(np.float32)

    def subtract_noise(self):
        """ Calibrated and denoised data is equal to
            (data**2 - Noise) / Calibration**2
        """
        if not hasattr(self, 'data'):
            print('Read data first.')
            return False
        elif not hasattr(self, 'noise'):
            print('Read noise first.')
            return False
        elif not hasattr(self, 'calibration'):
            print('Read calibration first.')
            return False

        if not self.denoised:
            self.data = self.data**2 - self.noise
            self.data = self.data / self.calibration**2
            threshold = 1 / self.calibration.max()
            self.data[self.data < threshold] = threshold
            self.data = np.log10(self.data) * 10
            self.denoised = True
        else:
            print('Product is already denoised.')

    def normalize(self, output_range=[0, 1], extend=True):
        """ Scale data to output_range.
        """
        """ Normalize """
        if extend:
            self.data -= self.data.min()
            self.data /= self.data.max()
        else:
            self.data -= self.img_min
            self.data /= self.img_max - self.img_min
        """ Scale to output_range """
        self.data = self.data * (output_range[1] - output_range[0]) + output_range[0]

    def clip_normalize(self, output_range=[0, 1], extend=True):
        """ Clip data and normalize it
        """
        self.clip()
        self.normalize(output_range=output_range, extend=extend)

    def clip(self):
        self.data[self.data > self.img_max] = self.img_max
        self.data[self.data < self.img_min] = self.img_min

    def extend(self):
        """ Return normalized band data to clipped or original
        """
        self.data *= (self.img_max - self.img_min)
        self.data += self.img_min

    def incidence_angle_correction(self, elevation_angle):
        self.data = self.data + self.incidence_angle_correction_coefficient * (elevation_angle - elevation_angle.min())

    def remove_useless_data(self):
        self.calibration = None
        self.noise = None
        self.elevation_angle = None


class Sentinel1Product(object):
    """ The main class that represents a Sentinel-1 EW product.
        It contains information about the scene and band data in Sentinel1Band objects (one object per band).
        Input is expected to be a path to a Sentinel-1 scene (both *.SAFE and *.zip are supported).
    """
    def __init__(self, product_path):
        """ Set paths to auxilary data.
            Create Sentinel1Band object for each band in the product.
            Parse date and time of the product into self.timestamp
        """
        """ If *product_path* is a folder, set path to data and auxilary data,
            otherwise unpack it first (create tmp_folder if it does not exist)
        """
        try:
            self.product_name = os.path.basename(product_path).split('.')[0]
            print(self.product_path)
        except:
            pass

        def _band_number(x):
            """ Function expects a .xml filename from Sentinel-1 product folder.
                It returns the band number (the last character before the file extention, *00<band_num>.xml or *00<band_num>.tiff)
            """
            return int(os.path.split(x)[1].split('.')[0][-1])

        if os.path.isdir(product_path):
            self.zip = False
            self.product_path = os.path.abspath(product_path)
            self.data_files = sorted([os.path.join(self.product_path, 'measurement', item) for item in os.listdir(os.path.join(self.product_path, 'measurement'))], key=_band_number)
            self.annotation_files = sorted([os.path.join(self.product_path, 'annotation', item) for item in os.listdir(os.path.join(self.product_path, 'annotation')) if '.xml' in item], key=_band_number)
            self.noise_files = sorted([os.path.join(self.product_path, 'annotation', 'calibration', item) for item in os.listdir(os.path.join(self.product_path, 'annotation', 'calibration')) if 'noise' in item], key=_band_number)
            self.calibration_files = sorted([os.path.join(self.product_path, 'annotation', 'calibration', item) for item in os.listdir(os.path.join(self.product_path, 'annotation', 'calibration')) if 'calibration' in item], key=_band_number)
        elif not os.path.isfile(product_path):
            print('File {0} does not exist.'.format(product_path))
            return False
        else:
            if not zipfile.is_zipfile(product_path):
                print('File {0} is not a zip file.'.format(product_path))
            try:
                self.zip = True
                zipdata = zipfile.ZipFile(product_path)
                data_files = sorted([item for item in zipdata.namelist() if 'measurement' in item and '.tif' in item], key=_band_number)
                xml_files = [item for item in zipdata.namelist() if '.xml' in item]
                annotation_files = sorted([item for item in xml_files if 'annotation' in item and 'calibration' not in item], key=_band_number)
                noise_files = sorted([item for item in xml_files if 'noise' in item], key=_band_number)
                calibration_files = sorted([item for item in xml_files if 'calibration' in item and 'noise' not in item], key=_band_number)
                self.data_files = [zipdata.open(item) for item in data_files]
                self.annotation_files = [zipdata.open(item) for item in annotation_files]
                self.noise_files = [zipdata.open(item) for item in noise_files]
                self.calibration_files = [zipdata.open(item) for item in calibration_files]
            except:
                print('Zip file reading error.')
                return False
        
        """ Create a Sentinel1Band object for each band in the product. """
        for d, a, c, n in zip(self.data_files, self.annotation_files, self.calibration_files, self.noise_files):
            if type(a) == str:
                name_string = a
            else:
                name_string = a.name
            band_name = os.path.split(name_string)[1].split('-')[3].upper()
            setattr(self, band_name, Sentinel1Band(d, a, c, n, band_name))

        """ Create datetime object """
        self.timestamp = scene_time(product_path)
        
        try:
            import gdal
            if self.zip:
                p_gdal = gdal.Open('/vsizip/' + os.path.join(product_path, data_files[0]))
            else:
                p_gdal = gdal.Open(self.data_files[0])
            self.gdal_data = {'X': p_gdal.GetRasterBand(1).XSize,
                              'Y': p_gdal.GetRasterBand(1).YSize,
                              'GCPs': p_gdal.GetGCPs(),
                              'GCP_proj': p_gdal.GetGCPProjection()}
        except:
            pass

    def detect_borders(self):
        """ Detect noise next to the vertical borders of a given image.
            Set different thresholds for HH and HV bands since amplitude of measurements is different.
            Return border coordinates, that can be used for slising: img[min_lim:max_lim] returns
            image without border noise.
        """
        """ Set thresholds to 100 for HH and 40 for HV band, check 200 columns from edges """
        if hasattr(self.HH, 'data'):
            hh_left_lim, hh_right_lim = self._find_border_coordinates(self.HH, 100)
        else:
            hh_left_lim = hh_right_lim = None

        if hasattr(self.HV, 'data'):
            hv_left_lim, hv_right_lim = self._find_border_coordinates(self.HV, 40)
        else:
            hv_left_lim = hv_right_lim = None

        self.x_min = max(hh_left_lim, hv_left_lim)
        self.x_max = min(hh_right_lim, hv_right_lim)
    
    def _find_border_coordinates(self, band_object, threshold_value):
        hh_vertical_means = self.HH.data.mean(axis=0)
        try:
            hh_left_lim = np.where(hh_vertical_means[:200] < threshold_value)[0][-1]
        except:
            hh_left_lim = None
        try:
            hh_right_lim = hh_vertical_means.shape[0] - 200 + np.where(hh_vertical_means[-200:] < 100)[0][0]
        except:
            hh_right_lim = None
        return hh_left_lim, hh_right_lim

    def read_GCPs(self):
        """ Parse Ground Control Points (GCPs) from the annotation file.
            Since GCPs should be same for all the bands within a product, only one band is used (default - HH, if available).
        """
        if hasattr(self.HH, 'data'):
            band = self.HH
        elif hasattr(self.HV, 'data'):
            band = self.HV
        else:
            print('Read HH or HV band data before reading GCPs.')
            return False
        annotation_file = ElementTree.parse(band.annotation_path).getroot()
        self.GCPs = [{'azimuth_time': datetime.strptime(i[0].text, "%Y-%m-%dT%H:%M:%S.%f"),
                      'slant_range_time': float(i[1].text),
                      'line': int(i[2].text),
                      'pixel': int(i[3].text),
                      'latitude': float(i[4].text),
                      'longitude': float(i[5].text),
                      'height': float(i[6].text),
                      'incidence_angle': float(i[7].text),
                      'elevation_angle': float(i[8].text),
                      } for i in annotation_file[7][0]]
        return True

    def interpolate_GCP_parameter(self, parameter, gcps_per_line=21):
        """ Calculate coordinates for every pixel.
            Geolocation grid is interpolated linearly.
            Normally *gcps_per_line* should not be modified.
            Here it is assumed that there are always 21 geopoints per azimuth line.
        """
        if not hasattr(self, 'GCPs'):
            self.read_GCPs()
        if len(self.GCPs) % gcps_per_line != 0:
            print("Number of GCPs is not multiple of {0}.".format(gcps_per_line))
            print("Please, specify a different value for *gcps_per_line*.")
            return False
        ran = int(len(self.GCPs) / gcps_per_line)
        xs = np.array([i['line'] for i in self.GCPs])[::gcps_per_line]
        ys = np.array([i['pixel'] for i in self.GCPs])[:gcps_per_line]
        
        gcp_data = np.array([i[parameter] for i in self.GCPs], dtype=np.float32)
        gcp_data_spline = RectBivariateSpline(xs, ys, gcp_data.reshape(ran, gcps_per_line), kx=1, ky=1)
        x_new = np.arange(0, self.HH.X, 1, dtype=np.int16)
        y_new = np.arange(0, self.HH.Y, 1, dtype=np.int16)
        result = gcp_data_spline(x_new, y_new).astype(np.float32)
        if 'x_min' in self.gdal_data:
            result = result[:, self.gdal_data['x_min']:self.gdal_data['x_max']]
        setattr(self, parameter, result)
        return True
    
    def interpolate_latitude(self, gcps_per_line=21):
        if hasattr(self, 'latitude'):
            print('Latitudes have already been interpolated.')
            return True
        self.interpolate_GCP_parameter('latitude', gcps_per_line=gcps_per_line)

    def interpolate_longitude(self, gcps_per_line=21):
        if hasattr(self, 'longitude'):
            print('Longitudes have already been interpolated.')
            return True
        self.interpolate_GCP_parameter('longitude', gcps_per_line=gcps_per_line)

    def interpolate_height(self, gcps_per_line=21):
        if hasattr(self, 'height'):
            print('Heights have already been interpolated.')
            return True
        self.interpolate_GCP_parameter('height', gcps_per_line=gcps_per_line)

    def interpolate_elevation_angle(self, gcps_per_line=21):
        if hasattr(self, 'elevation_angle'):
            print('Elevation angles have already been interpolated.')
            return True
        self.interpolate_GCP_parameter('elevation_angle', gcps_per_line=gcps_per_line)

    def interpolate_incidence_angle(self, gcps_per_line=21):
        if hasattr(self, 'incidence_angle'):
            print('Incidence angles have already been interpolated.')
            return True
        self.interpolate_GCP_parameter('incidence_angle', gcps_per_line=gcps_per_line)
    
    def is_shifted(self):
        """ Check if first lines of swaths ara shifted relative to each other (black steps on top or at the bottom of the image)
        """
        if hasattr(self.HH, 'data'):
            self.shifted = True if self.HH.data[:400, -1500:].mean() < 100 else False
        elif hasattr(self.HV, 'data'):
            self.shifted = True if self.HV.data[:400, -1500:].mean() < 40 else False
        else:
            print('Read data first.')
            return False

        self.HH.shifted = True if self.shifted else False
        self.HV.shifted = True if self.shifted else False
        return True

    def read_data(self, band='both', incidence_angle_correction=True, keep_calibration_data=True, parallel=False, crop_borders=True, correct_hv=False):
        """ Shortcut for reading data, noise, calibration, and noise subtraction)
        """
        if band.lower() == 'both':
            band_list = [self.HH, self.HV]
        elif band.lower() == 'hh':
            band_list = [self.HH]
        elif band.lower() == 'hv':
            band_list = [self.HV]
        
        _rsb = partial(_read_single_band, keep_calibration_data=keep_calibration_data)
        if not parallel:
            list(map(_rsb, band_list))
        else:
            pool = ThreadPool(2)
            pool.map(_rsb, band_list)
            pool.close()
            pool.join()
        
        """ Incidence angle correction. """
        if incidence_angle_correction:
            self.read_GCPs()
            self.interpolate_elevation_angle()
            if hasattr(self, 'HH'):
                self.HH.incidence_angle_correction(self.elevation_angle)
            if hasattr(self, 'HV') and (correct_hv):
                self.HV.incidence_angle_correction(self.elevation_angle)

        """ Replace infinits (that appears after noise subtraction and calibration) with nofinite_data_val. """
        nofinite_data_val = -32
        for band in band_list:
            band.nofinite_data_mask = np.where(np.isfinite(band.data), False, True)
            band.data[band.nofinite_data_mask] = nofinite_data_val
        
        """ Save nodata mask to self.gdal_data for further data writing. """
        self.gdal_data['nodata_mask'] = self.HH.nodata_mask
        
        if crop_borders:
            self.crop_borders()
        return True

    def crop_borders(self):
        """ Remove "dirty" pixels on the left and the right sides of the project.
            The pixels are cut on all of the following (if exists):
                * band data
                * latitude
                * longitude
                * elevation angle
                * incidence angle
                * height
            Therefore this function should be called after all the needed parameters are read and interpolated.
        """
        self.detect_borders()
        self.gdal_data['x_min'] = self.x_min
        self.gdal_data['x_max'] = self.x_max
        for item in ['latitude', 'longitude', 'elevation_angle', 'incidence_angle', 'height']:
            if hasattr(self, item):
                setattr(self, item, getattr(self, item)[:, self.x_min:self.x_max])
        for band in [self.HH, self.HV]:
            for item in ['data', 'noise', 'calibration']:
                if hasattr(band, item):
                    attr = getattr(band, item)
                    if type(attr) != np.ndarray:
                        continue
                    setattr(band, item, getattr(band, item)[:, self.x_min:self.x_max])
    
    def orbit_direction(self):
        annotation_file = ElementTree.parse(self.annotation_files[0]).getroot()
        return annotation_file[2][0][0].text.lower()
    

def _read_single_band(band, keep_calibration_data=True):
    band.read_data()
    band.read_noise()
    band.read_calibration()
    band.subtract_noise()
    if not keep_calibration_data:
        band.noise = False
        band.calibration = False
        if hasattr(band, 'azimuth_noise'):
            band.azimuth_noise = False
    return True


if __name__ == '__main__':
    pass
