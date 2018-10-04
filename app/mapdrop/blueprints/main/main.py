import os
import re
import json

from slugify import slugify
from flask import Blueprint, Response, render_template, abort, render_template_string, request, jsonify, redirect, url_for, current_app
from shapely.geometry import mapping, shape
from functools import wraps
from shapely.wkt import loads
from mapdrop import redis_store

from ...mapdropfile import MapdropFile

main = Blueprint('main', __name__, template_folder='templates', url_prefix='/')


class APIException(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        rv['status_code'] = self.status_code
        rv['payload'] = None
        return rv

@main.errorhandler(APIException)
def handle_api_error(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response



def validate_filename(filename):
    """
    Validate a filename. Must be one character long, and can only contain
    a-z A-Z 0-9 and characters . - _.
    """
    if len(filename) == 0:
        return False
    exp = re.compile(r'[^a-zA-Z0-9\.\-\_]')
    return not bool(exp.search(filename))

def validate_directory(directory):
    exp = re.compile(r'[^a-zA-Z0-9\.\-\_\/]')
    return not bool(exp.search(directory))

def path_validate(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        path = kwargs.get("path", "")
        print("args=")
        print(args)


        print("checking path {}".format(path))
        directory, filename = os.path.split(path)
        print("directory={} filename={}".format(directory, filename))

        if filename == '':
            # Working with directory
            if validate_directory(directory):
                kwargs.update({'filename':filename, 'directory':directory, 'path':path})
                return f(*args, **kwargs)
            else:
                raise APIException("Invalid directory path", status_code=400)

        else:
            # Working with a file
            if validate_directory(directory) and validate_filename(filename):
                kwargs.update({'filename':filename, 'directory':directory, 'path':path})
                return f(*args, **kwargs)
            else:
                raise APIException("Invalid file path", status_code=400)
    return decorated_function

def path_exists_or_404(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        path = kwargs.get("path", "")
        directory, filename = os.path.split(path)
        fullpath = os.path.join(current_app.config.get("MAPDROP_DATA"), directory, filename)
        print(fullpath)
        kwargs.update({'fullpath':fullpath})
        if os.path.isfile(fullpath) or os.path.isdir(fullpath):
            return f(*args, **kwargs)
        else:
            raise APIException("Path not found", status_code=404)
    return decorated_function

@main.route('/', methods=['GET'])
@main.route('/<path:path>', methods=['GET'])
@path_validate
@path_exists_or_404
def info(*args, **kwargs):
    """
    Preview 
    """
    path = kwargs.get("path")
    mapdrop_version = current_app.config['MAPDROP_VERSION']

    path_components = []

    path_split = path.split("/")
    for n, comp in enumerate(path_split):
        path_item = "/".join(path_split[:n+1])
        if n < (len(path_split)-1):
            path_item += '/'
        path_components.append({'name':comp, 'path': path_item})

    if kwargs.get("filename") == '':
        # Directory view
        contents = []
        fullpath = os.path.join(current_app.config.get("MAPDROP_DATA"), path)
        for item in os.listdir(fullpath):
            item_localpath = os.path.join(path, item)
            item_path = os.path.join(fullpath, item)
            if os.path.isfile(item_path):
                contents.append({'type':'file','name':item, 'info':'', 'path':item_localpath, 'icon':'far fa-map'})
            if os.path.isdir(item_path):
                info = "{}".format(len(os.listdir(os.path.join(fullpath, item))))
                contents.append({'type':'dir','name':item+'/', 'info':info, 'path':item_localpath+'/', 'icon':'far fa-folder'})
        num_items = len(contents)
        return render_template("main/directory.html", **locals())
    else:
        # File view
        path = kwargs.get("path")
        mf = MapdropFile(path)
        return render_template("main/info.html", **locals())

# Views related to derived data from individial files (tiles, previews, etc) below
@main.route('/<path:path>~/tiles/<int:z>/<int:x>/<int:y>.<string:format>', methods=['GET'])
@path_validate
@path_exists_or_404
def tile(path, z, x, y, format, **kwargs):
    fullpath = os.path.join(current_app.config.get("MAPDROP_DATA"), path)
    mf = MapdropFile(fullpath)
    return mf.ds.tile(z, x, y, format=format, request_args=request.args)

@main.route('/<path:path>~/metadata/metadata.json', methods=['GET'])
@path_validate
@path_exists_or_404
def metadata(path, **kwargs):
    mf = MapdropFile(path)
    return jsonify(mf.metadata)

@main.route('/<path:path>~/metadata/extent.<string:format>', methods=['GET'])
@path_validate
@path_exists_or_404
def metadata_extent(path, format, **kwargs):
    mf = MapdropFile(path)
    geom = loads(mf.metadata.get("extent"))
    if format == 'json':
        return jsonify(mapping(geom))
    if format == 'wkt':
        return Response(geom.wkt, mimetype='text/plain')

@main.route('/<path:path>~/metadata/crs.<string:format>', methods=['GET'])
@path_validate
@path_exists_or_404
def metadata_crs(path, format, **kwargs):
    mf = MapdropFile(path)
    if format == 'wkt':
        return Response(mf.metadata.get("crs"), mimetype='text/plain')


@main.route('/<path:path>~/raw', methods=['GET'])
@path_validate
@path_exists_or_404
def raw(path, **kwargs):
    #mf = MapdropFile(kwargs.get("fullpath"))
    #return jsonify(mf.ds.metadata)
    return "RAW file"

@main.route('/<path:path>~/view', methods=['GET'])
@path_validate
@path_exists_or_404
def view(path, **kwargs):

    tilelayer_url = '/'+path+'~/tiles/{z}/{x}/{y}.png'
    return render_template("main/preview.html", **locals())



@main.route('/<path:path>~/<path:subpath>')
@path_validate
def catchall(*args, **kwargs):
    """
    Catch-all route for a path followed by a ~ that is not matched by 
    any valid views defined above.
    """
    return 'Invalid subpath', 404

@main.route('/<path:path>', methods=['PUT','POST'])
@path_validate
def put(path, **kwargs):
    directory, filename = os.path.split(path)
    fullpath = os.path.join(current_app.config.get("MAPDROP_DATA"), directory, filename)
    fulldirectory = os.path.join(current_app.config.get("MAPDROP_DATA"), directory)

    if os.path.isfile(fullpath):
        raise APIException("File already exists. Delete old one first", status_code=400)
    else:
        if not os.path.exists(fulldirectory):
            try: 
                os.makedirs(fulldirectory)
            except: 
                raise APIException("Could not create directory.", status_code=500)
        with open(fullpath, 'wb') as f:
            f.write(request.data)
        return 'PUT {}'.format(path), 200
