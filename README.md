# Mapdrop

**This is a work in progress. Do not use for anything serious. See the issues page for a list of things that are not working yet.**

Mapdrop is an experimental and lightweight geodata server. It functions as a queryable REST back-end for web mapping applications and should be simple and usable. 

## Synopsis

Mapdrop lets you upload data over HTTP directly to an arbitrary URL on your Mapdrop server, and then query that base URL for web tiles, metadata, statistical data, and lots of other things. 

For example, you (or your code) can upload a GeoTIFF file to the `/results/myfile.tif` URL on a Mapdrop server using a PUT (or POST) request:

    PUT /results/myfile.tif

then the file is exposed immediately using endpoints in a tilde-separated URL format `<filename>~<endpoint>`. For example, to load the file `/results/myfile.tif` into a Leaflet map you could use `~/tiles` endpoint through the URL pattern:

    /results/myfile.tif~/tiles/{z}/{x}/{y}.png

Or query values at particular location:

    /results/myfile.tif~/query/query.json?geom=POINT(10%2010)

Fetch a raster tile in UTFGrid format:

    /results/myfile.tif~/tiles/{z}/{x}/{y}.utfgrid

Load the extent of the file as a GeoJSON feature:

    /results/myfile.tif~/metadata/extent.geojson

Or include the map in an iframe on a different website:

    <iframe src="/results/myfile.tif~/preview"></iframe>

## Installation

Docker and the `docker-compose.yaml` file are probably the fastest and easiest way to get a Mapdrop server up and running. There are three services defined: `app`, `cache`, and `web`. 

The `app` serves the Flask-based application through the gunicorn WSGI server, `cache` is a Redis cache for data persistence and caching responses from `app`, and `web` is a nginx service that serves cached files from Redis, or passes the request onto the application server.

The `docker-compose.yaml` file can be used to build and start the services:

    docker-compose build

And start everything with:

    docker-compose up

## Why

I'm building another web application that does a wide range of visualizations and interactions with automatically generated raster and vector datasets. For this to work well I needed something that could:

  * Easily and quickly let me convert all sorts of raster and vector files into web tiles to load into a Leaflet map.
  * Needed to support raster, vector, and utfgrid tiles, as well as simple visualization options (color ramps for rasters, etc).
  * Let me query summary statistics of rasters by supplying points, polygons, or transects, and returning the results in JSON format.
  * Be extendable so it's easy to add new endpoints for other types of queries on the source data to obtain the data I need to make visualizations.
  * Minimal configuration. 

After some deliberation of whether starting a new project was really a good idea I though I'd make a quick prototype (which is what you're looking at) and just take it from there, perhaps learning something in the process about Redis and GDAL. Who knows it might turn into something useful.

## Managing files

### Creating files

Files can be uploaded with a PUT or POST request to any base URL on the Mapdrop server that you want the data to be available at. 

For example, we can use `curl` to PUT the file `srtm_38_03.tif` at `/test.tif`:

    curl -i http://127.0.0.1:8080/test.tif --upload-file srtm_38_03.tif

    curl -i http://127.0.0.1:8080/test.tif -T srtm_38_03.tif

And for compatibility reasons using a POST method will also work:

    TBD

And uploading multiple files to a directory is also possible:

    TBD

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

The `~/tiles/{z}/{x}/{y}.{format}` endpoint serves pseudomercator tiles that can be included in a webmap. Supported tile formats are PNG, JPEG, or UTFGRID.

TODO: Utfgrid tiles are not implemented yet.

TODO: What about vector tiles.

### Query

TODO: Not implemented yet.

Output in json/csv/geojson, implement something like the following endpoints:

`~/query/stats.json?geom=<wkt>&crs=<crs>&stats=avg,min,max,q50`
`~/query/transect.json?geom=<wkt>&crs=<crs>&points=<n>`

How does this apply to vector data????

### Download

Download the original dataset or derivatives using the `~/raw` endpoint. 

TODO: It would be nice if this supported HTTP range requests as well, and the request to this endpoint should always be served by the web server itself, not the application.

## Caching

The Mapdrop application itself only caches/persists metadata for files present in the `MAPDROP_DATA` directory. This metadata is stored in the Redis data store. 

Actual outputs such as tiles are not cached by the application, this something that should be done by a front-end that sits in front of the web server. The Docker configuration files that are included in the repository set up a Redis cache in combination with an nginx webserver. The web server uses the URL as a cache key, checks whether it is available in the Redis store, and serves the data from the cache. Only when this is not the case is the request deferred to the backend application.

## Authentication 

Not implemented yet, but a basic authentication scheme based on something like an API key could be useful. It would then be up to enduser to put the Mapdrop server behind SSL.

## Configuration

The Mapdrop data directory can be configured through the `MAPDROP_DATA` environment variable.

Configuration of individual files may at some point be possible through an endpoint like `~/config` or something.

## Other Features

See issues page for an overview of features that are not implemented yet and other ideas.

