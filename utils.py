""" Utils for Sentinel-1 scenes.
"""

__author__ = 'Dmitrii Murashkin'
import datetime
import os


def scene_time(scene_path):
    """ Reads scene time (beginnign of the acquisition) from the name of a scene.
        Returns a python datetime.datetime instance.
        The function should be convenient to use as a sorting function:
        sorted([item for item in os.listdir(<input_folder>)], key=scene_time)
        returns a sorted by time list of scenes in the <input_folder>.
    """
    scene_name = os.path.basename(scene_path)
    date_format = '%Y%m%dT%H%M%S'
    try:
        date_string = scene_name.split('_')[4]
        date = datetime.datetime.strptime(date_string, date_format)
    except IndexError:
        print('Date of "{0}" does not correspond to {1} format.'.format(scene_name, date_format))
        return False
    return date
