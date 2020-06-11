""" Create a geotiff with GCPs copied from the original Sentinel-1 scene.
"""
import gdal
import numpy as np


def write_data_geotiff(input_data, output_path, gdal_data, dec=1, nodata_val=0):
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
    print('write to geotiff: original scene size {0}x{1}, data size to write {2}x{3}'.format(X, Y, input_data.shape[0], input_data.shape[1]))

    datatype_mapping = {'uint8': gdal.GDT_Byte,
                        'uint16': gdal.GDT_UInt16,
                        'uint32': gdal.GDT_UInt32,
                        'int8': gdal.GDT_Byte,
                        'int16': gdal.GDT_Int16,
                        'int32': gdal.GDT_Int32,
                        'float32': gdal.GDT_Float32,
                        'float64': gdal.GDT_Float64,
                        'complex64': gdal.GDT_CFloat64,
                        }

    try:
        datatype = datatype_mapping[input_data.dtype.name]
    except:
        print('Unsupported datatype {0} for the input array.'.format(input_data.dtype))
        return False

    driver = gdal.GetDriverByName('GTiff')
    out_x = X // dec + 1 if np.remainder(X, dec) else X // dec
    out_y = Y // dec + 1 if np.remainder(Y, dec) else Y // dec
    out = driver.Create(output_path, out_x, out_y, bands, datatype, options=['COMPRESS=DEFLATE'])
    for gcp in gcps:
        gcp.GCPLine /= dec
        gcp.GCPPixel /= dec
    out.SetGCPs(gcps, proj)

    for n, layer in enumerate(np.split(data, bands, axis=2)):
        band = out.GetRasterBand(n + 1)
        if 'x_min' in gdal_data:
            data_to_write = np.full((out_y, out_x), nodata_val, dtype=input_data.dtype)
            data_to_write[:, gdal_data['x_min'] // dec:gdal_data['x_min'] // dec + layer.shape[1]] = np.squeeze(layer)
            band.WriteArray(data_to_write)
        else:
            band.WriteArray(np.squeeze(layer))
    
    out.FlushCache()


if __name__ == "__main__":
    pass
