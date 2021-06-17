#import os
import sys
import argparse
import datetime

from sentinel1_routines.download import download_single_day


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', help='date in format YYYY-MM-DD')
    parser.add_argument('-o', default='./', help='output folder')
    parser.add_argument('-rf', default=False, help='Sentinel-1 data root folder')
    parser.add_argument('-ef', default='', help='Create an extra folder with given name (only if root folder is specified).')
    args = parser.parse_args()

    if not args.d:
        print('Specify date with -d option')
        sys.exit()
    try:
        date = datetime.datetime.strptime(args.d, '%Y-%m-%d')
    except:
        print('Date {0} is not in the YYYY-MM-DD format.')
        sys.exit()

    download_single_day(date=date, root_folder=args.rf, output_folder=args.o, extra_folder=args.ef)
