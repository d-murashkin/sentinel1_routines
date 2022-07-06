""" Apply calibration and noise correction to a Sentinel-1 scene.
    result is a GeoTiff with RGB (HH, HV, band ratio) / single band grayscale / two-band in dB (default).
"""
import argparse
import os
import sys
import time

from sentinel1_routines.to_geotiff import rgb, grayscale, calibrated
from sentinel1_routines.scene_management import get_scene_folder


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='create a GeoTiff from a Sentinel-1 scene with applied calibration.')
    parser.add_argument('-t', help='type of the output: RGB / grayscale / dB (default)')
    parser.add_argument('-i', required=True, help='input file (Sentinel-1 scene)')
    parser.add_argument('-o', default='', help='output folder')
    parser.add_argument('-b', help='band (hh or hv) if grayscale type is chosen')
    parser.add_argument('-f', help='apply speckle noise filter (bilateral fiter, 5 pixel size)', action='store_true')
    parser.add_argument('-iac', help='apply incidence angle correction (for sea ice)', action='store_true')
    parser.add_argument('-p', action='store_true', help='parallel=True')
    parser.add_argument('--root_folder', default=False, help='path to sentinel-1 scene storage')
    parser.add_argument('--rf_ef', default='', help='extra folder for get_scene_folder (most likely not required)')
    parser.add_argument('--scale_noise', action='store_true')
    args = parser.parse_args()

    if not os.path.exists(args.i):
        if not os.path.exists(args.root_folder):
            print('Enter full path to the scene or specify root_folder')
            sys.exit()
        path_to_scene = os.path.join(get_scene_folder(args.i, root_folder=args.root_folder, ensure_existence=False, extra_folder=args.rf_ef), args.i)
    else:
        path_to_scene = args.i

    if not os.path.exists(path_to_scene):
        print('Scene is not found (wrong path?)')
        sys.exit()

    filt = True if args.f else False
    inc_angle_corr = True if args.iac else False
    parallel = True if args.p else False
    output = os.path.join(args.o, os.path.splitext(os.path.basename(path_to_scene))[0] + '.tiff')
    if not args.t:
        tp = 'db'
    else:
        tp = args.t.lower()

    print('Processing...')
    t = time.time()
    if tp == 'rgb':
        rgb(path_to_scene, output, speckle_filter=filt, incidence_angle_correction=inc_angle_corr, parallel=parallel, correct_hv=False, scale_noise=args.scale_noise)
    elif tp == 'grayscale':
        if not args.b:
            print('Specify band with -b option: hh or hv')
            sys.exit()
        grayscale(path_to_scene, output, band=args.b.lower(), speckle_filter=filt, incidence_angle_correction=inc_angle_corr, parallel=parallel, correct_hv=False, scale_noise=args.scale_noise)
    elif tp == 'db':
        calibrated(path_to_scene, output, speckle_filter=filt, incidence_angle_correction=inc_angle_corr, parallel=parallel, correct_hv=False)
    else:
        print('Unrecognised type "{0}". Possible options are "RGB", "grayscale", "dB".'.format(tp))
    print('... is done in {0} seconds.'.format(int(time.time() - t)))
