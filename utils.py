""" Some small utils for Sentinel-1 scenes.
"""
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
    try:
        timestamp = scene_name.split('_')[4]
    except IndexError:
        return False
    return(datetime.datetime.strptime(timestamp, '%Y%m%dt%H%M%S'))
