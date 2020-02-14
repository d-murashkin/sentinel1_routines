""" Create a geotiff with GCPs copied from the original Sentinel-1 scene.
"""
import gdal
import numpy as np


def write_data_geotiff(input_data, output_path, gdal_data, dec=1):
    X = gdal_data['X']
    Y = gdal_data['Y']
    proj = gdal_data['GCP_proj']
    gcps = gdal_data['GCPs']
    if len(input_data.shape) == 2:
        bands = 1
        data = input_data[:, :, np.newaxis]
    else:
        bands = input_data.shape[2]
        data = input_data

    driver = gdal.GetDriverByName('GTiff')
    out = driver.Create(output_path, X // dec + 1 if np.remainder(X, dec) else X // dec, Y // dec + 1 if np.remainder(Y, dec) else Y // dec, bands, gdal.GDT_Byte, options=['COMPRESS=DEFLATE'])
    for gcp in gcps:
        gcp.GCPLine /= dec
        gcp.GCPPixel /= dec
    out.SetGCPs(gcps, proj)

    for n, layer in enumerate(np.split(data, bands, axis=2)):
        band = out.GetRasterBand(n + 1)
        band.WriteArray(np.squeeze(layer))
    
    out.FlushCache()


if __name__ == "__main__":
    pass
