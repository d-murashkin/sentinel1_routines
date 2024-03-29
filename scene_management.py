"""
Handling Sentinel-1 scenes in a *root_folder* storage.
"""

__author__ = 'Dmitrii Murashkin'

import os
import re
import shutil

from .utils import scene_time


def get_scene_folder(scene_name, root_folder, ensure_existence=True, extra_folder=''):
    """ Find path to the scene in the *root_folder* storage
        and optionally ensure its existence (create folders if needed).
    """
    scene_name = scene_name.split('.')[0]
    try:
        date = scene_time(scene_name)
    except Exception:
        print('Could not recognize timestamp for {0}'.format(scene_name))
        return False

    return get_date_folder(date, root_folder, ensure_existence, extra_folder)


def get_date_folder(date, root_folder, ensure_existence=True, extra_folder=''):
    year = date.strftime('%Y')
    month = date.strftime('%m')
    day = date.strftime('%d')
    scene_folder = os.path.join(root_folder, year, month, day, extra_folder)

    if ensure_existence:
        try:
            if not os.path.exists(scene_folder):        # for python2 compatibility
                os.makedirs(scene_folder)               #
#            os.makedirs(scene_folder, exist_ok=True)
        except Exception:
            print('Could not create folders in {0}.'.format(root_folder))
            return False

    return scene_folder


def arrange_scene(scene_path, root_folder, copy=False, extra_folder=''):
    scene_name = os.path.basename(scene_path)
    if not re.search('^S1(A|B)', scene_name.split('_')[0]):
        """ This is not a Sentinel-1 product file. """
        return False
    elif scene_name.split('_')[-1][-4:] != '.zip':
        """ This is not a zip archive, skip it. """
        return False

    scene_folder = get_scene_folder(scene_name, root_folder, ensure_existence=True, extra_folder=extra_folder)
    try:
        if copy:
            shutil.copy(scene_path, scene_folder)
        else:
            shutil.move(scene_path, scene_folder)
    except Exception:
        return False
    return True


def is_available(scene_name, root_folder):
    """ Check *scene* existence in the *root_folder* storage.
    """
    scene_name = scene_name.split('.')[0]
    scene_folder = get_scene_folder(scene_name, root_folder, ensure_existence=False)
    scene_path = os.path.join(scene_folder, scene_name)
    if os.path.exists(scene_path):
        return True
    return False


if __name__ == '__main__':
    pass
