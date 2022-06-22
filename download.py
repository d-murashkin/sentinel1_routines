"""
Script for searching and downloading data from sentinel satellites.
dhusget.sh script from the Copernicus web-page is used.
Single scenes can be downloaded from https://datapool.asf.alaska.edu
"""

__author__ = 'Dmitrii Murashkin'
__email__ = 'murashkin@uni-bremen.de'

import os
import shutil
import subprocess
import datetime


from .scene_management import get_scene_folder
from .scene_management import get_date_folder


def set_dir(dir_path):
    """ Set folder. Create it if it does not exist. """
    if not os.path.exists(dir_path):
        os.mkdir(dir_path)
    return dir_path


"""
def download_single_scene(scene_name, root_folder=False, output_folder='./'):
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
            except Exception:
                print('Could not read $S1PATH environment variable.')
                return False
        download_path = get_scene_folder(scene_name, root_folder)

    try:
        asf_credentials = os.environ['ASF_CREDENTIALS']
        with open(asf_credentials) as f:
            username = f.readline()[:-1]
            passwd = f.readline()[:-1]
    except Exception:
        print('No credentials provided.')
        return False

    cwd = os.getcwd()
    os.chdir(download_path)
    subprocess.call('wget -c -q --show-progress --http-user={0} --http-password={1} "https://datapool.asf.alaska.edu/GRD_MD/S{2}/{3}.zip"'.format(username, passwd, scene_name[2], scene_name), shell=True)
    os.chdir(cwd)
    return True
"""


def download_single_scene(scene_name, root_folder=False, output_folder='./'):
    scene_name = scene_name.split('.')[0]
    if not root_folder:
        download_path = output_folder
    else:
        if root_folder is True:
            try:
                root_folder = os.environ['S1PATH']
            except Exception:
                print('Could not read $S1PATH environment variable.')
                return False
        download_path = get_scene_folder(scene_name, root_folder)

    try:
        asf_credentials = os.environ['ASF_CREDENTIALS']
        with open(asf_credentials) as f:
            username = f.readline()[:-1]
            passwd = f.readline()[:-1]
    except Exception:
        print('No credentials provided.')
        return False

    cwd = os.getcwd()
    os.chdir(download_path)
#    subprocess.call('wget -c -q --show-progress --http-user={0} --http-password={1} "https://datapool.asf.alaska.edu/GRD_MD/S{2}/{3}.zip"'.format(username, passwd, scene_name[2], scene_name), shell=True)
    search_string = 'https://api.daac.asf.alaska.edu/services/search/param?'
    scene_type = scene_name.split('_')[2]
    if len(scene_type) != 3:
        scene_type = '{0}_{1}{2}'.format(scene_type[:3], scene_type[3], scene_name.split('_')[3][2])
    search_string += 'product_list={0}-{1}'.format(scene_name, scene_type)
    print(search_string)
    call = f'aria2c --http-auth-challenge=true --http-user={username} --http-passwd={passwd} --check-integrity=true --max-tries=0 --max-concurrent-downloads=3 "{search_string}"'
    subprocess.call(call, shell=True)
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
            except Exception:
                print('Could not read $S1PATH environment variable.')
                return False
        download_path = get_date_folder(date, root_folder, extra_folder=extra_folder)

    try:
        asf_credentials = os.environ['ASF_CREDENTIALS']
        with open(asf_credentials) as f:
            username = f.readline()[:-1]
            passwd = f.readline()[:-1]
    except Exception:
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


def get_scene_from_storage(scene_name, output_folder, root_folder=False, extra_folder=''):
    if not root_folder:
        try:
            root_folder = os.environ['S1PATH']
        except KeyError:
            print('Specify root folder of the storage.')
            return False
    if not os.path.exists(root_folder):
        print(f'Root folder {root_folder} does not exist.')
        return False
    if not os.path.exists(output_folder):
        print(f'Output folder {output_folder} does not exist')
        return False

    scene_folder = get_scene_folder(scene_name, root_folder=root_folder, ensure_existence=False, extra_folder=extra_folder)

    name = '_'.join(scene_name.split('_')[:-1])
    scene_path = [os.path.join(scene_folder, item) for item in os.listdir(scene_folder) if name in item]
    if scene_path:
        shutil.copy(scene_path[0], os.path.join(output_folder, os.path.basename(scene_path[0])))
    return True


if __name__ == "__main__":
    pass
