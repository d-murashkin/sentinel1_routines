""" Apply calibration and noise correction to a Sentinel-1 scene.
    result is a GeoTiff with RGB (HH, HV, band ratio) / single band grayscale / two-band in dB (default).
"""
import argparse
import sys

from to_geotiff import rgb, grayscale, calibrated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='create a GeoTiff from a Sentinel-1 scene with applied calibration.')
    parser.add_argument('-t', help='type of the output: RGB / grayscale / dB (default)')
    parser.add_argument('-i', help='input file (Sentinel-1 scene)')
    parser.add_argument('-o', help='output GeoTiff')
    parser.add_argument('-b', help='band (hh or hv) if grayscale type is chosen')
    parser.add_argument('-f', help='apply speckle noise filter (bilateral fiter, 5 pixel size)', action='store_true')
    parser.add_argument('-iac', help='apply incidence angle correction (for sea ice)', action='store_true')
    args = parser.parse_args()
    if not args.i:
        print('Please, specify input Sentinel-1 scene with -i key.')
        sys.exit()
    if not args.o:
        print('Please, specify output GeoTiff file with -o key.')
        sys.exit()
    
    filt = True if args.f else False
    inc_angle_corr = True if args.iac else False
    if not args.t:
        tp = 'db'
    else:
        tp = args.t.lower()
    
    if tp == 'rgb':
        rgb(args.i, args.o, speckle_filter=filt, incidence_angle_correction=inc_angle_corr)
    elif tp == 'grayscale':
        if not args.b:
            print('Specify band with -b option: hh or hv')
            sys.exit()
        grayscale(args.i, args.o, band=args.b.lower(), speckle_filter=filt, incidence_angle_correction=inc_angle_corr)
    elif tp == 'db':
        calibrated(args.i, args.o, speckle_filter=filt, incidence_angle_correction=inc_angle_corr)
    else:
        print('Unrecognised type "{0}". Possible options are "RGB", "grayscale", "dB".'.format(tp))
