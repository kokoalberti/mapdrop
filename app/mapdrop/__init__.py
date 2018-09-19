from flask import Flask, render_template, render_template_string, redirect, url_for

# Create the application object and configure it
app = Flask(__name__)
app.config.from_object('mapdrop.settings') 
app.config.from_object('mapdrop.local_settings')

# Import and register the blueprints for the main application
from mapdrop.blueprints.main import main
app.register_blueprint(main)

if __name__ == "__main__":
    app.run()