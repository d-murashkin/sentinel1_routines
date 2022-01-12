""" Apply calibration and noise correction to a Sentinel-1 scene.
    result is a GeoTiff with RGB (HH, HV, band ratio) / single band grayscale / two-band in dB (default).
"""
import argparse
import os
import sys
import time

from sentinel1_routines.to_geotiff import rgb, grayscale, calibrated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='create a GeoTiff from a Sentinel-1 scene with applied calibration.')
    parser.add_argument('-t', help='type of the output: RGB / grayscale / dB (default)')
    parser.add_argument('-i', help='input file (Sentinel-1 scene)')
    parser.add_argument('-o', default='', help='output folder')
    parser.add_argument('-b', help='band (hh or hv) if grayscale type is chosen')
    parser.add_argument('-f', help='apply speckle noise filter (bilateral fiter, 5 pixel size)', action='store_true')
    parser.add_argument('-iac', help='apply incidence angle correction (for sea ice)', action='store_true')
    parser.add_argument('-p', action='store_true', help='parallel=True')
    args = parser.parse_args()
    if not args.i:
        print('Please, specify input Sentinel-1 scene with -i key.')
        sys.exit()
    
    filt = True if args.f else False
    inc_angle_corr = True if args.iac else False
    parallel = True if args.p else False
    output = os.path.join(args.o, os.path.basename(args.i).split('.')[0] + '.tiff')
    if not args.t:
        tp = 'db'
    else:
        tp = args.t.lower()
    
    print('Processing...')
    t = time.time()
    if tp == 'rgb':
        rgb(args.i, output, speckle_filter=filt, incidence_angle_correction=inc_angle_corr, parallel=parallel, correct_hv=False)
    elif tp == 'grayscale':
        if not args.b:
            print('Specify band with -b option: hh or hv')
            sys.exit()
        grayscale(args.i, output, band=args.b.lower(), speckle_filter=filt, incidence_angle_correction=inc_angle_corr, parallel=parallel, correct_hv=False)
    elif tp == 'db':
        calibrated(args.i, output, speckle_filter=filt, incidence_angle_correction=inc_angle_corr, parallel=parallel, correct_hv=False)
    else:
        print('Unrecognised type "{0}". Possible options are "RGB", "grayscale", "dB".'.format(tp))
    print('... is done in {0} seconds.'.format(int(time.time() - t)))
