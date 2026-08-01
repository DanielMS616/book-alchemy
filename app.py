import os

from flask import Flask

from data_models import db, Author, Book


# Creates the Flask application.
app = Flask(__name__)

# Determines the absolute path of the project directory.
basedir = os.path.abspath(os.path.dirname(__file__))

# Configures the connection to the local SQLite database.
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"sqlite:///{os.path.join(basedir, 'data/library.sqlite')}"
)

# Connects the central SQLAlchemy object to the Flask application.
db.init_app(app)


# Creates all database tables defined by the SQLAlchemy models.
# The application context gives SQLAlchemy access to the Flask configuration.
# with app.app_context():
#     db.create_all()