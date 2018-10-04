# Mapdrop

**This is a work in progress. Do not use for anything serious.**

Mapdrop is an experimental and lightweight geodata server. It is intended as a queryable REST back-end for web mapping applications and is designed to be simple and usable. 

## Why

I'm building a web application that does a wide range of visualizations and interactions with automatically generated raster and vector datasets. For this to work well I needed something that could:

  * Easily and quickly let me convert all sorts of raster and vector files into web tiles to load into a Leaflet map.
  * Needed to support raster, vector, and utfgrid tiles, as well as simple visualization options (color ramps, etc)
  * Let me query summary statistics of rasters by supplying points, polygons, or transects and returning the results in JSON format,
  * Be extendable so it's easy to add new endpoints for other types of queries on the data that I need to make visualizations.
  * Minimal configuration. I didn't want to have to create configuration file templates (for Mapserver, Geoserver, or Tilestache) and configuration files for each file I had generated. 

After some deliberation of whether starting a new project was really a good idea I though I'd make a quick prototype and take it from there, perhaps learning something in the process about Redis and GDAL.

## Synopsis

Mapdrop lets you upload data over HTTP directly to an arbitrary URL on your Mapdrop server, and then query that base URL for web tiles, metadata, statistical data, and lots of other things. 

For example, you (or your code) can upload a Geotiff file to the `/results/myfile.tif` URL on a Mapdrop server using a PUT (or POST) request:

    PUT /results/myfile.tif

then use it immediately using endpoints in a tilde-separated URL format `<filename>~<endpoint>`, for example using the `~/tiles` endpoint to load the file `/results/myfile.tif` in a Leaflet map:

    GET /results/myfile.tif~/tiles/{z}/{x}/{y}.png

Or query values at particular location:

    GET /results/myfile.tif~/query/geom.json?geom=POINT(10%2010)

Fetching a tile as a UTFGrid:

    GET /results/myfile.tif~/utfgrid/{z}/{x}/{y}.txt

Load the extent of the file as a GeoJSON feature:

    GET /results/myfile.tif~/metadata/extent.geojson

And include the map in an iframe on your own website:

    <iframe src="/results/myfile.tif~/preview"></iframe>

## Installation

The repository includes the necessary Docker files to get set up in minutes. There are three services defined: `app`, `cache`, and `web`. The `app` serves the Flask-based application through the gunicorn WSGI server, `cache` is a Redis cache for caching responses from `app`, and `web` is a nginx service that serves cached files from Redis, or passes the request onto the application server.

The `docker-compose.yaml` file can be used to build and start the services:

   docker-compose build

And start everything with:

   docker-compose up

## Configuration

## Managing files

### Creating files

Files can be uploaded with a PUT or POST request to a base URL that you want the data to be available at. 

For example, we can use `curl` to PUT the file `srtm_38_03.tif` at `/test.tif`:

    curl -i http://127.0.0.1:8080/test.tif --upload-file srtm_38_03.tif

    curl -i http://127.0.0.1:8080/test.tif -T srtm_38_03.tif

And for compatibility reasons using a POST method will also work:

    TBD

And uploading one or more files to a directory is also possible:

    TBD curl -F 'files[]=@/path/to/fileX' -F 'files[]=@/path/to/fileY' ... http://localhost/upload

Or drag and drop using a browser:

    TBD

Or add files directly to the data directory defined by the `MAPDROP_DATA` environment variable by some other means, for example through FTP, SSH, or other programs that have access to the directory.

### Existing files

To use an existing directory with files in it, simply use the `MAPDROP_DATA` environment variable and point it at your data directory.

### Deleting files

Files can be deleted using a DELETE request, or by deleting the file directly from disk.


## Endpoints

A GET request on a file should show an overview page with information on the file, and some options of what can be done, linking appropriately to subendpoints below.

Various subendpoints can be requested by appending a tilde `~` and a sub-path to the base URL of the file.

### Tiles

The `~/tiles/{z}/{x}/{y}.{format}` endpoint serves pseudomercator tiles that can be included in a webmap. Supported tile formats are PNG and UTFGRID.

Classification through form parameters?

classes=ffcc33:red:yellow:green&class=1-

### Query

Output in json/csv/geojson

`~/query/geom.json?geom=<wkt>&crs=<crs>`
`~/query/stats.json?geom=<wkt>&crs=<crs>&stats=avg,min,max,q50`
`~/query/transect.json?geom=<wkt>&crs=<crs>&points=<n>`

How does this apply to vector data????

### Download

Download the original dataset or derivatives.

`~/download?format=<tif|png|jpg>`

Maybe some options for:

- resampling for low res versions
- custom width/height
- different projections? utm etc.
- crop/subset


## Configuration

Use `~/config` endpoint on a file.


## Caching

Mapdrop itself only caches metadata for files in the Redis object store, outputs such as tiles are not cached. It is possible but this should then be configured at the webserver level. The configuration files for Docker that are included in the repository set up a Redis cache in combination with an nginx webserver.

HEAD request for any url responds with caching refresh info. Would be nice if cache can refresh of the timestamp on the file changes. Can even make an endpoint `~/cache/reset` to clear the file.

## Authentication 

Not implemented yet. Maybe basic auth with a username/api-key? Upto enduser to put mapdrop server behind SSL.
