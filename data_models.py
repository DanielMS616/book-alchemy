from flask_sqlalchemy import SQLAlchemy


# Creates the central SQLAlchemy object for the application.
# The object is connected to the Flask app later in app.py.
db = SQLAlchemy()


class Author(db.Model):
    """Represents an author in the library database."""

    # Defines the name of the corresponding database table.
    __tablename__ = "authors"

    # Primary key of the authors table.
    # The value is created automatically for every new author.
    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
    )

    # Stores the author's name.
    name = db.Column(db.String)

    # Stores the author's date of birth.
    birth_date = db.Column(db.Date)

    # Stores the author's date of death.
    # This field can remain empty for living authors.
    date_of_death = db.Column(db.Date)


class Book(db.Model):
    """Represents a book in the library database."""

    # Defines the name of the corresponding database table.
    __tablename__ = "books"

    # Automatically generated primary key for every book.
    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
    )

    # Stores the ISBN of the book.
    isbn = db.Column(db.String)

    # Stores the title of the book.
    title = db.Column(db.String)

    # Stores the year in which the book was published.
    publication_year = db.Column(db.Integer)

    # Stores the ID of the author who wrote the book.
    # The Foreign Key connects this column to the id column
    # in the authors table.
    author_id = db.Column(
        db.Integer,
        db.ForeignKey("authors.id")
    )