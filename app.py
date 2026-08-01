import os

from datetime import datetime
from flask import Flask, render_template, request

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


@app.route("/add_author", methods=["GET", "POST"])
def add_author():
    """Displays the author form and stores submitted author data."""

    # A POST request is sent when the user submits the HTML form.
    if request.method == "POST":
        # Reads the values from the form fields.
        name = request.form.get("name")
        birthdate_value = request.form.get("birthdate")
        date_of_death_value = request.form.get("date_of_death")

        # Converts the required birthdate string into a Python date object.
        birth_date = datetime.strptime(
            birthdate_value,
            "%Y-%m-%d"
        ).date()

        # The date of death field is optional.
        # If it is empty, None is stored in the database.
        date_of_death = None

        if date_of_death_value:
            date_of_death = datetime.strptime(
                date_of_death_value,
                "%Y-%m-%d"
            ).date()

        # Creates a new Author object with the submitted form data.
        new_author = Author(
            name=name,
            birth_date=birth_date,
            date_of_death=date_of_death
        )

        # Adds the new object to the current database session.
        db.session.add(new_author)

        # Permanently saves the new author in the database.
        db.session.commit()

        # Displays the form again together with a success message.
        return render_template(
            "add_author.html",
            message="Author successfully added."
        )

    # A normal GET request only displays the form.
    return render_template("add_author.html")


# Creates all database tables defined by the SQLAlchemy models.
# The application context gives SQLAlchemy access to the Flask configuration.
# with app.app_context():
#     db.create_all()