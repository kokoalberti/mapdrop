from flask import Blueprint, render_template, abort, render_template_string, request, jsonify, redirect, url_for, current_app

from shapely.geometry import mapping, shape

main = Blueprint('main', __name__, template_folder='templates', url_prefix='/')

@main.route('/', methods=['GET'])
def home():
    return 'Hello, World.'