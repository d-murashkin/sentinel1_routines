#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Script for searching and downloading data from sentinel satellites.
dhusget.sh script from the Copernicus web-page is used.
"""

import os
import subprocess
import datetime
import shutil
import stat

import pandas as pd
from pandas import read_csv


def set_dir(dir_path):
    """ Set folder. Create it if it does not exist. """
    if not os.path.exists(dir_path):
        os.mkdir(dir_path)
    return dir_path


def create_day_folder(fld, date):
    """ Create the following folder structure in fld:
        fld/year/month/day/
        Return path to the date folder.
    """
    d_fld = fld + '{0}/{1}/{2}/'.format(date.year, date.strftime('%m'), date.strftime('%d'))
    if os.path.exists(d_fld):
        """ Folder already exists. """
        return d_fld
    try:
        y_fld = set_dir(fld + '{0}/'.format(date.year))
        m_fld = set_dir(y_fld + '{0}/'.format(date.strftime('%m')))
        d_fld = set_dir(m_fld + '{0}/'.format(date.strftime('%d')))
    except:
        print 'Could not create folders in {0}.'.format(fld)
        return False
    return d_fld


def create_list_of_products(llcrnrlon, llcrnrlat, urcrnrlon, urcrnrlat, start_date, end_date, login, password, lock_folder='', return_path=False):
    """ Return list of products that fit the specified rectangle and sensing date.
    """
    """ Ensure that time variables are of the datetime.date type. """
    if not ((type(start_date) == datetime.date) or (type(start_date) == datetime.datetime)) and ((type(end_date) == datetime.date) or (type(end_date) == datetime.date)):
        print 'start_date and end_date are expected to be of the datetime.date type.'
        return False

    list_of_products = []
    page = 1
    while True:
        subprocess.call('./dhusget.sh -u {7} -p {8} -L {9} -m Sentinel-1 -c {0},{1}:{2},{3} -T GRD -F "*_GRDM_*" -S {5}T00:00:00.000Z -E {6}T00:00:00.000Z -l 100 -P {4}'.format(llcrnrlon, llcrnrlat, urcrnrlon, urcrnrlat, page, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), login, password, lock_folder), shell=True)
        try:
            df = read_csv('products-list.csv', header=None, names=['name', 'address'])
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
    """ Ensure that time variables are of the datetime.date type. """
    if not ((type(start_date) == datetime.date) or (type(start_date) == datetime.datetime)) and ((type(end_date) == datetime.date) or (type(end_date) == datetime.date)):
        print 'start_date and end_date are expected to be of the datetime.date or the datetime.datetime type.'
        return False
    
    if not lock_folder:
        lock_folder = './dhusget_lock/'
    print 'lock folder:', lock_folder
    
    dhusget = fld + 'dhusget.sh'
    shutil.copyfile(os.path.dirname(os.path.realpath(__file__)) + '/dhusget.sh', dhusget)
    st = os.stat(dhusget)
    try:
        os.chmod(dhusget, st.st_mode | stat.S_IEXEC)
    except:
        "If Marcus owns the files, it's fine. Otherwise there is a problem with chmod."
        pass
    current_fld = os.getcwd()
    os.chdir(fld)
    if os.path.exists(fld + '/PRODUCT/'):
        for item in os.listdir(fld + '/PRODUCT/'):
            pth = fld + '/PRODUCT/' + item
            if os.stat(pth).st_size == 0:
                os.remove(pth)
    page = 1
    while True:
        subprocess.call('./dhusget.sh -u {7} -p {8} -L {9} -m Sentinel-1 -c {0},{1}:{2},{3} -T GRD -F "*_GRDM_*" -S {5}T00:00:00.000Z -E {6}T00:00:00.000Z -l 100 -P {4} -n {10} -o product -D'.format(llcrnrlon, llcrnrlat, urcrnrlon, urcrnrlat, page, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), login, password, lock_folder, n), shell=True)
        try:
            df = read_csv('products-list.csv', header=None, names=['name', 'address'])
        except:
            break
        if df.empty:
            break
        page += 1
    os.chdir(current_fld)
    print "Download complete."
    return True


def arrange_s1_file(inp_fld, out_fld, item):
    """ This function moves file *item* from input folder into year/month/day structure
        of the output folder.
        Output folder should be the root folder of the file structure.
    """
    name = item.split('_')
    if name[0][:2] != 'S1':
        """ Not a Sentinel-1 product file. """
        return False
    elif name[1] != 'EW':
        """ Not a product taken in Extra Wide swath mode. """
        return False
    elif name[2][:3] != 'GRD':
        """ Not a GRD product. """
        return False
    elif name[3] != '1SDH':
        """ Not a dual-band data product. """
        return False

    date = datetime.datetime.strptime(name[4], '%Y%m%dT%H%M%S')
    day_fld = create_day_folder(out_fld, date)
    path = set_dir(day_fld + 'PRODUCT/')
    if os.path.exists(path + item):
        return True
    shutil.move(inp_fld + item, path)
    return True


if __name__ == "__main__":
    pass
