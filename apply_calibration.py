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
    parser.add_argument('-t', default='db', help='type of the output: RGB / grayscale / dB (default)')
    parser.add_argument('-i', required=True, help='input file (Sentinel-1 scene)')
    parser.add_argument('-o', default='', help='output folder')
    parser.add_argument('-c', default='both', help='channel, "both" (default), hh or hv, if grayscale type is chosen')
    parser.add_argument('-f', action='store_true', help='apply speckle noise filter (bilateral fiter, 5 pixel size)')
    parser.add_argument('-iac', action='store_true', help='apply incidence angle correction (for sea ice)')
    parser.add_argument('-p', action='store_true', help='parallel=True')
    parser.add_argument('--root_folder', default=os.environ['S1PATH'], help='path to sentinel-1 scene storage')
    parser.add_argument('--rf_ef', default='', help='extra folder for get_scene_folder (most likely not required)')
    parser.add_argument('--scale_noise', action='store_true')
    parser.add_argument('--save_oceanmask', action='store_true', help='save oceanmask as an extra layer (not applicable to "grayscale" output type)')
    parser.add_argument('--save_incidence_angle', action='store_true', help='save incidence angles as an extra layer (only for "dB" output type)')
    parser.add_argument('--clip_normalize', default=False, nargs=2, type=float, help='if provided, should be a two-value tuple, clip high and low values and normalize to the given range')
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

    output = os.path.join(args.o, os.path.splitext(os.path.basename(path_to_scene))[0] + '.tiff')

    print('Processing...')
    t = time.time()
    match args.t.lower():
        case 'rgb':
            rgb(path_to_scene,
                output,
                speckle_filter=args.f,
                incidence_angle_correction=args.iac,
                parallel=args.p,
                correct_hv=False,
                scale_noise=args.scale_noise,
                save_oceanmask=args.save_oceanmask,
                )
        case 'grayscale':
            grayscale(path_to_scene,
                      output,
                      band=args.c.lower(),
                      speckle_filter=args.f,
                      incidence_angle_correction=args.iac,
                      parallel=args.p,
                      correct_hv=False,
                      scale_noise=args.scale_noise,
                      )
        case 'db':
            calibrated(path_to_scene,
                       output,
                       channel=args.c,
                       speckle_filter=args.f,
                       incidence_angle_correction=args.iac,
                       parallel=args.p,
                       correct_hv=False,
                       scale_noise=args.scale_noise,
                       save_oceanmask=args.save_oceanmask,
                       save_incidence_angle=args.save_incidence_angle,
                       clip_normalize=args.clip_normalize,
                       )
        case _:
            print('Unrecognised type "{0}". Possible options are "RGB", "grayscale", "dB".'.format(args.t))
    print('... is done in {0} seconds.'.format(int(time.time() - t)))
