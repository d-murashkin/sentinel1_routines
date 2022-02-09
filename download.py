"""
Script for searching and downloading data from sentinel satellites.
dhusget.sh script from the Copernicus web-page is used.
Single scenes can be downloaded from https://datapool.asf.alaska.edu
"""

__author__ = 'Dmitrii Murashkin'
__email__ = 'murashkin@uni-bremen.de'

import os
import subprocess
import datetime
import shutil
import stat

import pandas as pd

from .scene_management import get_scene_folder
from .scene_management import get_date_folder


def set_dir(dir_path):
    """ Set folder. Create it if it does not exist. """
    if not os.path.exists(dir_path):
        os.mkdir(dir_path)
    return dir_path


def create_list_of_products(llcrnrlon, llcrnrlat, urcrnrlon, urcrnrlat, start_date, end_date, login, password, lock_folder='', return_path=False):
    """ Return list of products that fit the specified rectangle and sensing date.
    """
    """ Ensure that time variables are of the datetime.date type. """
    if not ((type(start_date) == datetime.date) or (type(start_date) == datetime.datetime)) and ((type(end_date) == datetime.date) or (type(end_date) == datetime.date)):
        print('start_date and end_date are expected to be of the datetime.date type.')
        return False

    list_of_products = []
    page = 1
    while True:
        subprocess.call(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'dhusget.sh') + ' -u {7} -p {8} -L {9} -m Sentinel-1 -c {0},{1}:{2},{3} -T GRD -F "*_GRDM_*" -S {5}T00:00:00.000Z -E {6}T00:00:00.000Z -l 100 -P {4}'.format(llcrnrlon, llcrnrlat, urcrnrlon, urcrnrlat, page, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), login, password, lock_folder), shell=True)
        try:
            df = pd.read_csv('products-list.csv', header=None, names=['name', 'address'])
        except:
            break
        if df.empty:
            break
        list_of_products.append(df)
        page += 1
    result = pd.concat(list_of_products)
    if return_path:
        return [{'name': name, 'address': address} for name, address in zip(result['name'].tolist(), result['address'].tolist())]
    return result['name'].tolist()


def download_products(fld, llcrnrlon, llcrnrlat, urcrnrlon, urcrnrlat, start_date, end_date, login, password, lock_folder='', n=2):
    """ Deprecated.
        Ensure that time variables are of the datetime.date type. """
    if not ((type(start_date) == datetime.date) or (type(start_date) == datetime.datetime)) and ((type(end_date) == datetime.date) or (type(end_date) == datetime.date)):
        print('start_date and end_date are expected to be of the datetime.date or the datetime.datetime type.')
        return False
    
    if not lock_folder:
        lock_folder = './dhusget_lock/'
    print('lock folder: {0}'.format(lock_folder))
    
    dhusget = os.path.join(fld, 'dhusget.sh')
    shutil.copyfile(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'dhusget.sh'), dhusget)
    st = os.stat(dhusget)
    try:
        os.chmod(dhusget, st.st_mode | stat.S_IEXEC)
    except:
        "If Marcus owns the files, it's fine. Otherwise there is a problem with chmod."
        pass
    current_fld = os.getcwd()
    os.chdir(fld)
    if os.path.exists(os.path.join(fld, 'PRODUCT')):
        for item in os.listdir(os.path.join(fld, 'PRODUCT')):
            pth = os.path.join(fld, 'PRODUCT', item)
            if os.stat(pth).st_size == 0:
                os.remove(pth)
    page = 1
    while True:
        subprocess.call('./dhusget.sh -u {7} -p {8} -L {9} -m Sentinel-1 -c {0},{1}:{2},{3} -T GRD -F "*_GRDM_*" -S {5}T00:00:00.000Z -E {6}T00:00:00.000Z -l 100 -P {4} -n {10} -o product -D'.format(llcrnrlon, llcrnrlat, urcrnrlon, urcrnrlat, page, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), login, password, lock_folder, n), shell=True)
        try:
            df = pd.read_csv('products-list.csv', header=None, names=['name', 'address'])
        except:
            break
        if df.empty:
            break
        page += 1
    os.chdir(current_fld)
    print("Download complete.")
    return True


def download_single_scene(scene_name, root_folder=False, output_folder='./', show_progress=True):
    scene_name = scene_name.split('.')[0]
    '''
    if root_folder:
        try:
            root_folder = os.environ['S1PATH']
            download_path = get_scene_folder(scene_name, root_folder)
        except:
            download_path = output_folder
    else:
        download_path = output_folder
    '''
    if not root_folder:
        download_path = output_folder
    else:
        if root_folder is True:
            try:
                root_folder = os.environ['S1PATH']
            except:
                print('Could not read $S1PATH environment variable.')
                return False
        download_path = get_scene_folder(scene_name, root_folder)
    
    try:
        asf_credentials = os.environ['ASF_CREDENTIALS']
        with open(asf_credentials) as f:
            username = f.readline()[:-1]
            passwd = f.readline()[:-1]
    except:
        print('No credentials provided.')
        return False

    cwd = os.getcwd()
    os.chdir(download_path)
    if show_progress:
        subprocess.call('wget -c -q --show-progress --http-user={0} --http-password={1} "https://datapool.asf.alaska.edu/GRD_MD/S{2}/{3}.zip"'.format(username, passwd, scene_name[2], scene_name), shell=True)
    else:
        """ Turn off --show-progress option for wget older then 1.16"""
        subprocess.call('wget -c -q --http-user={0} --http-password={1} "https://datapool.asf.alaska.edu/GRD_MD/S{2}/{3}.zip"'.format(username, passwd, scene_name[2], scene_name), shell=True)
    os.chdir(cwd)
    return True


def download_single_day(date, root_folder=False, output_folder='./', extra_folder=''):
    if not (type(date) is datetime.datetime) or (type(date) is datetime.date):
        print('input should be a datetime.datetime or datetime.date instance.')
        return False
    
    if not root_folder:
        download_path = output_folder
    else:
        if root_folder is True:
            try:
                root_folder = os.environ['S1PATH']
            except:
                print('Could not read $S1PATH environment variable.')
                return False
        download_path = get_date_folder(date, root_folder, extra_folder=extra_folder)
            
    try:
        asf_credentials = os.environ['ASF_CREDENTIALS']
        with open(asf_credentials) as f:
            username = f.readline()[:-1]
            passwd = f.readline()[:-1]
    except:
        print('No credentials provided.')
        return False

    cwd = os.getcwd()
    os.chdir(download_path)
    search_string = 'https://api.daac.asf.alaska.edu/services/search/param?'
    search_string += 'platform=S1'
    search_string += '&beamSwath=EW'
    search_string += '&processingLevel=GRD_MD'
    search_string += '&start={0}'.format(date.strftime('%Y-%m-%dT00:00:00UTC'))
    search_string += '&end={0}'.format(date.strftime('%Y-%m-%dT23:59:59UTC'))
    search_string += '&output=metalink'
    search_string += '&intersectsWith=polygon((-160.6349 60.8024,-156.8663 69.0027,-128.1877 67.8319,-24.5383 80.8176,-36.4015 66.743,-19.1937 64.2656,36.6742 67.6532,64.5098 66.8212,121.018 70.5129,148.6526 69.0332,-160.6349 60.8024))'.replace('(', '%28').replace(')', '%29').replace(',', '%2C').replace(' ', '+')
#    subprocess.call('aria2c --http-auth-challenge=true --http-user={0} --http-passwd={1} --continue=true --check-integrity=true --max-tries=0 --max-concurrent-downloads=3 "{2}"'.format(username, passwd, search_string), shell=True)
    subprocess.call('aria2c --http-auth-challenge=true --http-user={0} --http-passwd={1} --check-integrity=true --max-tries=0 --max-concurrent-downloads=3 "{2}"'.format(username, passwd, search_string), shell=True)

    os.chdir(cwd)
    return True


if __name__ == "__main__":
    pass
