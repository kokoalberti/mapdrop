import os
import sys

from flask import Flask, render_template, render_template_string, redirect, url_for

from flask_redis import FlaskRedis

from werkzeug.routing import BaseConverter

# Create the application object and configure it
app = Flask(__name__)
app.config.from_object('mapdrop.settings') 
app.config['MAPDROP_VERSION'] = '0.1.0'


# Configure Redis connection
REDIS_URL = os.environ.get('REDIS_URL', None)
if REDIS_URL:
    app.config['REDIS_URL'] = REDIS_URL
redis_store = FlaskRedis(app)

# Configure the data directory
MAPDROP_DATA = os.environ.get("MAPDROP_DATA", None)
if not MAPDROP_DATA:
    raise Exception("No MAPDROP_DATA directory defined.")

if not os.path.isdir(MAPDROP_DATA):
    try: os.makedirs(MAPDROP_DATA)
    except: pass

if not os.path.isdir(MAPDROP_DATA):
    raise Exception("Can't create MAPDROP_DATA directory in {}".format(MAPDROP_DATA))
else:
    print(" * Mapdrop data directory: {}".format(MAPDROP_DATA))
    app.config['MAPDROP_DATA'] = MAPDROP_DATA



# Import and register the blueprints for the main application. Made this
# as a blueprint for the moment in case we decide to add things like an
# admin interface or something later. That can then become its own 
# blueprints as well.
from mapdrop.blueprints.main import main
app.register_blueprint(main)

if __name__ == "__main__":
    app.run()