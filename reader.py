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
import tempfile
from zipfile import ZipFile
from xml.etree import ElementTree
from datetime import datetime, timedelta
from multiprocessing.pool import ThreadPool

import numpy as np
from scipy.interpolate import RectBivariateSpline, griddata, interp1d
from PIL import Image
Image.MAX_IMAGE_PIXELS = None   # turn off the warning about large image size


class Sentinel1Band(object):
    """ Represents a Sentinel-1 band of a Sentinel-1 product.
        It has the following attributes:
            product_folder
            band_name - full band name (filename containing the band without extention)
            des - band designator or short name: 'hh' or 'hv'
            data_path - path to the tiff file that contains band data
            noise_path - path to the xml file that contains noise LUT
            calibration_path - path to the xml file thant containes calibration parameters LUT
            annotation_path - path to the xml file with annotation
            denoised - if data has been denoised (to prevent double noise removal)
            P - Period of scalloping noise in pixel. Probably, useless information.
            Image band max and min values are taken from kmeans cluster analysis of a set of images.
                For more information look into 'gray_level_reduction.py'
        It has the following methods:
            read_data(self) -- should be executed first
            read_noise(self)
            read_calibration(self)
            subtract_noise(self)
            scalloping_noise(self) -- not completed yet
    """
    def __init__(self, product_path, band_name):
        self.product_folder = product_path
        self.band_name = band_name
        self.des = 'hh' if '-hh-' in band_name.lower() else 'hv'
        self.img_max = 0.9541868 if self.des == 'hh' else -0.13850354
        self.img_min = -6.71286583 if self.des == 'hh' else -7.38279407
        self.data_path = self.product_folder + 'measurement/' + self.band_name + 'tiff'
        self.noise_path = self.product_folder + 'annotation/calibration/noise-' + self.band_name + 'xml'
        self.calibration_path = self.product_folder + 'annotation/calibration/calibration-' + self.band_name + 'xml'
        self.annotation_path = self.product_folder + 'annotation/' + self.band_name + 'xml'
        self.denoised = False
        self.P = 502

    def read_data(self):
 #        self.data = imread(self.data_path, mode='I').astype(np.float32)
        self.data = np.array(Image.open(self.data_path), dtype=np.float32)
        print(self.data.shape)
        self.X, self.Y = self.data.shape
        self.nodata_mask = np.where(self.data == 0, True, False)

    def read_noise(self):
        """ Read noise table from the band noise file, interpolate it for entire image.
            self.noise has same shape as self.data
        """
        if not hasattr(self, 'X') or not hasattr(self, 'Y'):
            print('Read data first.')
            return False

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

    def read_geolocation_grid(self):
        """ Read Geolocation Grid. For each grid cell the following parameters are given:
            [azimuth time, slant range time, line, pixel, latitude, longitude, height,
            incidence angle, elevation angle]
        """
        annotation_file = ElementTree.parse(self.annotation_path).getroot()
        self.geolocation_grid = [{'azimuth_time': datetime.strptime(i[0].text, "%Y-%m-%dT%H:%M:%S.%f"),
                                  'slant_range_time': float(i[1].text),
                                  'line': int(i[2].text),
                                  'pixel': int(i[3].text),
                                  'latitude': float(i[4].text),
                                  'longitude': float(i[5].text),
                                  'height': float(i[6].text),
                                  'incidence_angle': float(i[7].text),
                                  'elevation_angle': float(i[8].text),
                                  } for i in annotation_file[7][0]]

    def interp_elevation_angle(self):
        """ Interpolate elevation angle information from annotation for entire image.
            Grid is assumed to be rectangular, 21 cell in width
        """
        if not hasattr(self, 'geolocation_grid'):
            print('Read Geolocation Grid first.')
            return False

        line_list = np.array([i['line'] for i in self.geolocation_grid])
        pixel_list = np.array([i['pixel'] for i in self.geolocation_grid])
        elevation_angle = np.array([i['elevation_angle'] for i in self.geolocation_grid])
        lines = line_list[::21]
        pixels = pixel_list[:21]
        elevation_angle_interp = RectBivariateSpline(lines, pixels, elevation_angle.reshape((len(lines), len(pixels))), kx=1, ky=1)
        self.elevation_angle = elevation_angle_interp(np.arange(self.X), np.arange(self.Y)).astype(np.float32)

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
            self.data = np.log(self.data)
            self.denoised = True
        else:
            print('Product is already denoised.')

    def normalize(self):
        """ Data normalization: [0; 1]
        """
        self.data -= self.data.min()
        self.data /= self.data.max()

    def clip_normalize(self):
        """ Clip data and normalize it
        """
        self.data[self.data > self.img_max] = self.img_max
        self.data[self.data < self.img_min] = self.img_min
        self.data -= self.img_min
        self.data /= (self.img_max - self.img_min)

    def clip(self):
        self.data[self.data > self.img_max] = self.img_max
        self.data[self.data < self.img_min] = self.img_min

    def extend(self):
        """ Return normalized band data to clipped or original
        """
        self.data *= (self.img_max - self.img_min)
        self.data += self.img_min

    def incidence_angle_correction(self):
        self.data = self.data + 0.049 * (self.elevation_angle - self.elevation_angle.min())

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
        """ Init function.
            Unzip the specied Sentinel-1 scene if needed.
            Paths to auxilary data are set.
            Band object(s) is(are) created.
        """

        """ If *product_path* is a folder, set path to data and auxilary data,
            otherwise unpack it first (create tmp_folder if it does not exist)
        """
        if os.path.isdir(product_path):
            self.product_folder = os.path.abspath(product_path) + '/'
        elif os.path.isfile(product_path):
            self.tmp_folder = tempfile.TemporaryDirectory()
            try:
                zipdata = ZipFile(product_path)
                zipdata.extractall(self.tmp_folder.name)
                self.product_folder = os.path.join(self.tmp_folder.name, zipdata.namelist()[0])
            except:
                print('Zip file reading/extracting error.')
                return False
        else:
            print('File {0} does not exist.'.format(product_path))
            return False

        """ Read in-product file names """
        files = os.listdir(self.product_folder + 'measurement/')
        if '-hh-' in files[0] and '-hv-' in files[1]:
            band_name_list = [files[0][:-4], files[1][:-4]]
        elif '-hh-' in files[1] and '-hv-' in files[0]:
            band_name_list = [files[1][:-4], files[0][:-4]]
        else:
            print('Unable to recognize HH and HV bands.')

        """ Create 2 bands: HH and HV """
        self.HH = Sentinel1Band(self.product_folder, band_name_list[0])
        self.HV = Sentinel1Band(self.product_folder, band_name_list[1])

        """ Create datetime object """
        try:
            self.timestamp = datetime.strptime(band_name_list[0].split('-')[4], "%Y%m%dt%H%M%S")
        except:
            self.timestamp = False

        """ Flags show if top or bottom of the product should be cut. (probably not needeed anymore)"""
        self.cut_bottom = False
        self.cut_top = False

    def detect_borders(self):
        """ NOT CHECKED """
        """ Detect noise next to the vertical borders of a given image.
            Set different thresholds for HH and HV bands since amplitude of measurements is different.
            Return border coordinates, that can be used for slising: img[min_lim:max_lim] returns
            image without border noise.
        """
        """ Set thresholds to 100 for HH and 40 for HV band, check 200 columns from edges """
        if hasattr(self.HH, 'data'):
            HH_mean = self.HH.data.mean(axis=0)
            try:
                HH_min_lim = np.where(HH_mean[:200] < 100)[0][-1]
            except:
                HH_min_lim = None
            try:
                HH_max_lim = HH_mean.shape[0] - 200 + np.where(HH_mean[-200:] < 100)[0][0]
            except:
                HH_max_lim = None
        else:
            HH_min_lim = HH_max_lim = None

        if hasattr(self.HV, 'data'):
            HV_mean = self.HV.data.mean(axis=0)
            try:
                HV_min_lim = np.where(HV_mean[:200] < 100)[0][-1]
            except:
                HV_min_lim = None
            try:
                HV_max_lim = HV_mean.shape[0] - 200 + np.where(HV_mean[-200:] < 100)[0][0]
            except:
                HV_max_lim = None
        else:
            HV_min_lim = HV_max_lim = None

        self.x_min = max(HH_min_lim, HV_min_lim)
        self.x_max = min(HH_max_lim, HV_max_lim)

    def read_GCPs(self):
        """ Parse Ground Control Points (GCPs) from the annotation file.
            Since GCPs should be same for all the bands within a product, only one band is used (default - HH, if available).
        """
        if hasattr(self.HH, 'data'):
            band = self.HH
        elif hasattr(self.HV, 'data'):
            band = self.HV
        else:
            print('Read HH or HV band data first.')
            return False
        coord_root = ElementTree.parse(band.annotation_path).getroot()
        self.GCPs = [{'line': int(i[2].text),
                      'pixel': int(i[3].text),
                      'latitude': float(i[4].text),
                      'longitude': float(i[5].text)} for i in coord_root[7][0]]
        return True
    
    def interpolate_geolocation_grid(self, gcps_per_line=21):
        """ Calculate coordinates for every pixel.
            Geolocation grid is interpolated linearly.
            Normally *gcps_per_line* should not be modified.
            Here it is assumed that there are always 21 geopoints per azimuth line.
        """
        if not hasattr(self, 'GCPs'):
            self.read_GCPs()
        if self.GCPs.shape[0] % gcps_per_line != 0:
            print("Number of GCPs is not multiple of {0}.".format(gcps_per_line))
            print("Please, specify a different value for *gcps_per_line*.")
            return False
        ran = int(len(self.GCPs) / gcps_per_line)
        xs = np.array([i['line'] for i in self.GCPs][::gcps_per_line])
        ys = np.array([i['pixel'] for i in self.GCPs][:gcps_per_line, 1])
        lats = np.array([i['latitude'] for i in self.GCPs])
        lons = np.array([i['longitude'] for i in self.GCPs])
        lat_spline = RectBivariateSpline(xs, ys, lats.reshape(ran, gcps_per_line), kx=1, ky=1)
        lon_spline = RectBivariateSpline(xs, ys, lons.reshape(ran, gcps_per_line), kx=1, ky=1)
        x_new = np.arange(0, self.HH.X, 1, dtype=np.int16)
        y_new = np.arange(0, self.HH.Y, 1, dtype=np.int16)
        self.lon_array = lon_spline(x_new, y_new)
        self.lat_array = lat_spline(x_new, y_new)
        return True

    def create_landmask(self):
        """ NOT CHECKED """
        """ Create a masked array with landmask for given image.
        """
        from mpl_toolkits.basemap import maskoceans
        if hasattr(self.HH, 'data'):
            band = self.HH
        elif hasattr(self.HV, 'data'):
            band = self.HV
        else:
            print('Read HH or HV band data first.')
            return False
        result = maskoceans(self.lon_list, self.lat_list, band.data, resolution='f', grid=1.25)
        self.landmask = ~result.mask
        return True

    def is_shifted(self):
        """ NOT CHECKED """
        """ Check if first lines of swaths ara shifted relative to each other
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

    def read_data(self, band='both', incidence_angle_correction=True, keep_useless_data=True):
        """ NOT CHECKED """
        """ Shortcut for reading data, noise, calibration, preprocessing (borders removal and
            noise subtraction)
        """
        if band.lower() == 'both':
            band_list = [self.HH, self.HV]
        elif band.lower() == 'hh':
            band_list = [self.HH]
        elif band.lower() == 'hv':
            band_list = [self.HV]

        [_read_single_band(bnd) for bnd in band_list]
        _crop_product(self, keep_useless_data)
        return True

    def read_data_p(self, incidence_angle_correction=True, keep_useless_data=True):
        """ NOT CHECKED """
        """ Reading data in 2 threads (1 per band), works only with 2 bands, normalization is not
            supported (can be done manually after data is read, if needed)
        """
        band_list = [self.HH, self.HV]

        pool = ThreadPool(2)
        pool.map(_read_single_band, band_list)
        pool.close()
        pool.join()

        _crop_product(self, keep_useless_data)
        return True


def _read_single_band(band):
    """ NOT CHECKED """
    band.read_data()
    band.read_noise()
    band.read_calibration()
    band.read_geolocation_grid()
    band.interp_elevation_angle()
    band.subtract_noise()
    if band.des.lower() == 'hh':
        band.incidence_angle_correction()
    band.nofinite_data_mask = np.where(np.isfinite(band.data), False, True)
    nofinite_data_val = -4.6
    band.data[band.nofinite_data_mask] = nofinite_data_val
    return True


def _crop_product(product, keep_useless_data):
    """ NOT CHECKED """
    product.parse_lat_lon()
    product.detect_borders()
    product.lat_list = product.lat_list[:, product.x_min:product.x_max]
    product.lon_list = product.lon_list[:, product.x_min:product.x_max]

    for band in [product.HH, product.HV]:
        if not keep_useless_data:
            band.remove_useless_data()
        else:
            band.noise = band.noise[:, product.x_min:product.x_max]
            band.calibration = band.calibration[:, product.x_min:product.x_max]
            band.elevation_angle = band.elevation_angle[:, product.x_min:product.x_max]
        band.data = band.data[:, product.x_min:product.x_max]


if __name__ == '__main__':
    pass
    p = Sentinel1Product('/bffs01/group/users/mura_dm/sea_ice_classification_dataset/sentinel-1/products/zip/S1A_EW_GRDM_1SDH_20200107T033938_20200107T034038_030689_038489_92D9.zip')
    p.read_data_p()
