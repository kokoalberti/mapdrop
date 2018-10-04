import os
import base64

import json
import time

import numpy as np
import numpy.ma as ma

import mercantile 
import matplotlib.cm as mpcm

import itertools

from osgeo import ogr, osr, gdal, gdal_array
from PIL import Image, ImageFont, ImageDraw
from io import BytesIO

from shapely.ops import transform
from shapely.geometry import box,Polygon,mapping
from shapely.wkt import loads

import pyproj

from flask import Response
from functools import partial
from datetime import datetime

from epsg_ident import EpsgIdent

from mapdrop import redis_store

from colour import Color

import matplotlib

from matplotlib.colors import LinearSegmentedColormap, ListedColormap


class Colormap(object):
    """
    Class that translates between our set of "mode", "ranges", and 
    "colormap" variables and the corresponding matplotlib color mapping.
    """

    def __init__(self, colormap='', ranges='', mode='', stats=None):
        self.stats = stats

        self.parse_mode(mode)
        self.parse_colormap(colormap)
        self.parse_ranges(ranges)

    def __repr__(self):
        return "<Colormap mode={} ranges={} colormap={}>".format(self.mode, self.ranges, self.colormap)

    def parse_mode(self, mode):
        if mode in ('discrete','linear','exact','rgb'):
            self.mode = mode
        else:
            raise Exception("Invalid mode")

    def parse_colormap(self, colormap):
        self.cmap = None
        self.colormap = colormap

        # Try to parse colormap as a matplotlib named colormap
        try:
            self.cmap = matplotlib.cm.get_cmap(colormap)
            return
        except:
            self.cmap = None

        # Apparently something else was passed. Only option is 
        # a list of individual colors. Lets parse that then.
        try:
            colorlist = []
            for c in colormap.split(","):
                colorlist.append(Color(c).rgb)

            if self.mode == 'exact':
                print('creating ListedColormap with colorlist:')
                print(colorlist)
                self.cmap = ListedColormap(colorlist, 'custom')
                return
            else:
                print('creating LinearSegmentedColormap with colorlist:')
                print(colorlist)
                if len(colorlist) < 2:
                    raise Exception("Need at least two colors in colormap.")
                else:
                    self.cmap = LinearSegmentedColormap.from_list('custom', colorlist, N=256)
                    return
        except:
            self.cmap = None

        # If all else fails, fall back to 'Spectral'
        self.cmap = matplotlib.cm.get_cmap('Spectral')
        return

    def parse_ranges(self, ranges):
        #TODO: check if stats are tehre
        self.ranges = []
        for r in ranges.split(","):
            print("r={}".format(r))
            if r == 'avg':
                self.ranges.append(self.stats.get("avg"))
            elif r == 'min':
                self.ranges.append(self.stats.get("min"))
            elif r == 'max':
                self.ranges.append(self.stats.get("max"))
            else:
                try:
                    self.ranges.append(float(r))
                except:
                    pass

    def rgba(self, array):
        """
        Apply the settings to an array
        """
        data = array
        if self.mode != 'rgb':
            data = array[:,:,0]

        if self.mode == 'discrete':
            print("discrete mode with ranges: {}".format(self.ranges))
            norm = matplotlib.colors.BoundaryNorm(boundaries=self.ranges, ncolors=256)
            sm = matplotlib.cm.ScalarMappable(norm=norm, cmap=self.cmap)
            rgba = sm.to_rgba(data, bytes=True)

        elif self.mode == 'linear':
            print("linear mode normalized between {} and {}".format(self.ranges[0],self.ranges[-1]))
            norm = matplotlib.colors.Normalize(self.ranges[0],self.ranges[-1])

            sm = matplotlib.cm.ScalarMappable(norm=norm, cmap=self.cmap)
            rgba = sm.to_rgba(data, bytes=True)            

        elif self.mode == 'exact':
            print("exact mode. mapping ranges {} to colors {}".format(self.ranges, self.colormap))
            norm = matplotlib.colors.NoNorm()

            sm = matplotlib.cm.ScalarMappable(norm=norm, cmap=self.cmap)

            # Copy and mask the entire array.
            reclassed = data.copy()
            reclassed.mask = True

            # For each category, assign values 1..n to the reclass mask
            for n,r in enumerate(self.ranges):
                ix = data == r
                reclassed[ix] = n
                reclassed.mask[ix] = False

            rgba = sm.to_rgba(reclassed, bytes=True)

        elif self.mode == 'rgb':
            sm = matplotlib.cm.ScalarMappable()
            rgba = sm.to_rgba(data, bytes=True)  

        else:
            raise Exception("Unknown mode")

        return rgba

class Dataset(object):
    def __init__(self, path):
        self.path = path
        self._metadata = None

    @property
    def metadata(self):
        path = self.path

        if self._metadata != None:
            return self._metadata

        #redis_store.delete(path)
        #redis_store.delete(path+'.lock')
        metadata = redis_store.get(path)

        if metadata == None:
            # Try and set the 'lock' key, if that works then we're in the
            # clear to create the metadata.
            metadata_lock_key = path+'.lock'
            metadata_lock_timestamp = datetime.utcnow()
            metadata_lock_result = redis_store.setnx(metadata_lock_key, metadata_lock_timestamp)
            if metadata_lock_result == True:
                # We have the lock, save the data.
                redis_store.expire(metadata_lock_key, 10)
                metadata = self.get_metadata()
                redis_store.set(metadata_lock_key, json.dumps(metadata))
                redis_store.rename(metadata_lock_key, path)
            else:
                # We do not have the lock, apparently someone else does. Lets
                # take a few seconds until the metadata has been generated and 
                # then keep going.
                for n in range(0, 5):
                    time.sleep(0.5)
                    metadata = redis_store.get(path)
                    if metadata != None:
                        break
                raise Exception("No metadata found.")
        else:
            metadata = json.loads(metadata)

        self._metadata = metadata
        return self._metadata

class Raster(Dataset):
    def __init__(self, path, ds):
        super().__init__(path)
        self.ds = ds

    def __repr__(self):
        return "<Raster>"

    def close(self):
        self.ds = None

    def get_metadata(self):
        """
        return metadata
        """
        metadata = {
            'crs':self.ds.GetProjectionRef(),
            'epsg':self.get_epsg(),
            'raster':{
                'geotransform':self.ds.GetGeoTransform(),
                'width':self.ds.RasterXSize,
                'height':self.ds.RasterYSize
            },
            'layers':self.get_layers(),
            'type':'raster'
        }
        metadata.update(self.get_extent())
        return metadata

    def get_layers(self):
        layers = []
        for b in range(1, self.ds.RasterCount+1):
            band = self.ds.GetRasterBand(b)
            raw = band.ReadAsArray()
            mask = np.where(raw == band.GetNoDataValue(), 1, 0)
            data = ma.masked_array(raw, mask=mask).compressed()
            layers.append({
                'datatype': band.DataType,
                'nodata': band.GetNoDataValue(),
                'name': 'b{}'.format(b),
                'stats':self.get_layer_stats(data)
            })
        return layers

    def get_epsg(self):
        """
        return epsg code
        """
        ident = EpsgIdent(prj=self.ds.GetProjectionRef())
        return ident.get_epsg()

    def get_extent(self):
        """
        return extent and envelope
        """
        srs = osr.SpatialReference()
        srs.ImportFromWkt(self.ds.GetProjectionRef())
        proj_init = srs.ExportToProj4()

        print(proj_init)

        project = partial(pyproj.transform, pyproj.Proj(proj_init), pyproj.Proj(init="epsg:4326"))

        

        (x_min, x_size, _, y_max, _, y_size) = self.ds.GetGeoTransform()
        (rows, cols) = self.ds.RasterYSize, self.ds.RasterXSize

        x_max = x_min + (x_size * cols)
        y_min = y_max + (y_size * rows)

        num_edge_points = 10

        points = []
        points.extend([(x, y_max) for x in np.linspace(x_min, x_max, num_edge_points, endpoint=False)])
        points.extend([(x_max, y) for y in np.linspace(y_max, y_min, num_edge_points, endpoint=False)])
        points.extend([(x, y_min) for x in np.linspace(x_max, x_min, num_edge_points, endpoint=False)])
        points.extend([(x_min, y) for y in np.linspace(y_min, y_max, num_edge_points, endpoint=False)])
        points.reverse()

        polygon = Polygon(points)

        extent = transform(project, polygon)
        envelope = box(*extent.bounds)

        return {
            'extent':extent.wkt,
            'envelope':envelope.wkt
        }

    def get_layer_stats(self, data):
        stats = {}
        stats.update({
            'max': data.max().item(),
            'min': data.min().item(),
            'avg': data.mean().item(),
            'q': np.percentile(data, q=range(0, 105, 5)).tolist()
        })
        return stats

    def tile_data(self, z, x, y, width=256, height=256):
        """
        Fetch tile data by warping into a tile.

        TODO: resampling algo
        """
        tile = mercantile.xy_bounds(x, y, z)

        ds = gdal.Warp('', 
                       self.ds, 
                       format='VRT', 
                       dstSRS='EPSG:3857',
                       outputType=self.metadata['layers'][0].get("datatype"), 
                       width=width, 
                       height=height, 
                       outputBounds=(tile.left, tile.bottom, tile.right, tile.top))

        dtype = gdal_array.GDALTypeCodeToNumericTypeCode(self.metadata['layers'][0].get("datatype"))
        bands = np.empty((256,256, ds.RasterCount), dtype=dtype)
        masks = np.empty((256,256, ds.RasterCount), dtype=dtype)
        
        for b in range(1, ds.RasterCount+1):
            band = ds.GetRasterBand(b).ReadAsArray()
            bands[:,:,b-1] = band

            mask = np.where(band == self.metadata['layers'][0].get("nodata"), 1, 0)
            masks[:,:,b-1] = mask

        data = ma.masked_array(bands, mask=masks)
        ds = None

        return (data, mask)

    def tile(self, z, x, y, **kwargs):
        #TODO: tile outside extent should return nothing
        data, mask = self.tile_data(z, x, y, width=kwargs.get("width", 256), height=kwargs.get("height", 256))
        rows, cols, bands = data.shape
        format = kwargs.get("format","png").lower()
        request_args = kwargs.get("request_args", {})
        im_data = BytesIO()

        if bands == 1:
            mode = request_args.get("mode", "linear")
        if bands == 3:
            mode = 'rgb'

        cm = Colormap(colormap=request_args.get("colormap",""), mode=mode, ranges=request_args.get("ranges","min,max"), stats=self.metadata['layers'][0]['stats'])
        rgba = cm.rgba(data)
        
        if format == 'png':
            im = Image.fromarray(rgba, mode='RGBA')
            im.save(im_data, format="PNG")
            return Response(im_data.getvalue(), mimetype='image/png')

        elif format == 'jpeg':
            im = Image.fromarray(rgba[:,:,:-1], mode='RGB')
            im.save(im_data, format="JPEG", quality=int(request_args.get("quality",75)), optimize=True, progressive=True)
            return Response(im_data.getvalue(), mimetype='image/jpeg')

        elif format == 'base64':
            im = Image.fromarray(rgba, mode='RGBA')
            im.save(im_data, format="PNG")
            return Response(b"data:image/png;base64,"+base64.b64encode(im_data.getvalue()), mimetype='application/base64')

        else:
            raise Exception("Unknown format")

    def utfgrid(self, **kwargs):
        pass

class Vector(object):
    def __init__(self, path):
        raise NotImplementedError

    def close(self):
        pass

    @property
    def metadata(self):
        return {
            'type':'vector',
            'crs':self.ds.GetProjectionRef(),
            'vector':{},
            'layers':self.layers
        }

    @property
    def layers(self):
        return []

    def tile(self, **kwargs):
        pass

    def utfgrid(self, **kwargs):
        pass


class MapdropFile(object):
    def __init__(self, path):
        MAPDROP_DATA = os.environ.get("MAPDROP_DATA", None)
        if not os.path.isdir(MAPDROP_DATA):
            raise Exception("Invalid MAPDROP_DATA directory.")

        fullpath = os.path.join(MAPDROP_DATA, path)
        if not os.path.isfile(fullpath):
            raise Exception("File {} does not exist.".format(fullpath))

        self.path = path
        self.fullpath = fullpath

        try:
            ds = gdal.Open(fullpath)
            if ds is not None:
                self.ds = Raster(path, ds)
                self.is_raster = True
                self.is_vector = False
        except Exception as e:
            raise Exception("Can't open file: {}".format(e))

    @property
    def metadata(self):
        return self.ds.metadata

    def __repr__(self):
        return "<MapdropFile path='{}'>".format(self.path)

    def close(self):
        self.ds.close()

    # def __getattr__(self, name):
    #     """
    #     Pass any methods executed on the MapdropFile onto 
    #     either the raster or the vector.
    #     """
    #     def meth(*args, **kwargs):
    #         print("unknown method: {}".format(name))
    #         m = getattr(self.ds, name, None)
    #         if callable(m):
    #             return m(*args, **kwargs)
    #     return meth
