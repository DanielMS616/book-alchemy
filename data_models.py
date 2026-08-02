from flask_sqlalchemy import SQLAlchemy


# Creates the central SQLAlchemy object for the application.
# The object is connected to the Flask app later in app.py.
db = SQLAlchemy()


class Author(db.Model):
    """Represents an author in the personal library."""

    # Defines the name of the corresponding database table.
    __tablename__ = "authors"

    # Automatically generated primary key for every author.
    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
    )

    # Basic author information.
    name = db.Column(db.String)
    birth_date = db.Column(db.Date)
    date_of_death = db.Column(db.Date)

    # Short, consistently formatted biography displayed in the app.
    # This may later be generated from source_biography.
    biography = db.Column(db.Text)

    # Original biography retrieved from Open Library.
    source_biography = db.Column(db.Text)

    # Open Library photo information.
    photo_id = db.Column(db.Integer)
    photo_url = db.Column(db.String)

    # Relative path to a locally stored author image.
    # Example: images/authors/OL118077A.jpg
    photo_path = db.Column(db.String)

    # Reference to the corresponding Open Library author record.
    open_library_key = db.Column(db.String)


class Book(db.Model):
    """Represents a book in the personal library."""

    # Defines the name of the corresponding database table.
    __tablename__ = "books"

    # Automatically generated primary key for every book.
    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
    )

    # Identifies the concrete edition of the book.
    isbn = db.Column(db.String)

    # Basic information about the selected edition.
    title = db.Column(db.String)
    publication_year = db.Column(db.Integer)

    # First known publication year of the general work.
    original_publication_year = db.Column(db.Integer)

    # Short, consistently formatted description displayed in the app.
    summary = db.Column(db.Text)

    # Original description retrieved from Open Library.
    source_description = db.Column(db.Text)

    # Personal notes about the book.
    # Examples: current chapter, thoughts, or reading plans.
    notes = db.Column(db.Text)

    # Marks the book as a personal favorite.
    # New books are not favorites by default.
    is_favorite = db.Column(
        db.Boolean,
        default=False
    )

    # Main category used for organizing the personal collection.
    category = db.Column(db.String)

    # Additional information about the selected edition.
    publisher = db.Column(db.String)
    language = db.Column(db.String)
    number_of_pages = db.Column(db.Integer)

    # Cover information from Open Library.
    cover_id = db.Column(db.Integer)
    cover_url = db.Column(db.String)

    # Relative path to a locally stored cover image.
    # Example: covers/catalog/9780451524935.jpg
    cover_path = db.Column(db.String)

    # References to the corresponding Open Library records.
    work_key = db.Column(db.String)
    edition_key = db.Column(db.String)

    # Stores the ID of the author who wrote the book.
    author_id = db.Column(
        db.Integer,
        db.ForeignKey("authors.id")
    )

    # Provides access to the associated Author object.
    # This relationship is not an additional database column.
    author = db.relationship("Author")


class CatalogBook(db.Model):
    """Represents a book available in the local discovery catalog."""

    # Defines the name of the corresponding database table.
    __tablename__ = "catalog_books"

    # Automatically generated primary key for every catalog entry.
    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
    )

    # Identifies the concrete book edition.
    isbn = db.Column(db.String)

    # Basic information displayed in the catalog.
    title = db.Column(db.String)
    author_name = db.Column(db.String)

    # Publication year of the selected edition.
    publication_year = db.Column(db.Integer)

    # First known publication year of the general work.
    original_publication_year = db.Column(db.Integer)

    # Short, consistently formatted description displayed in the app.
    # This may later be generated from source_description.
    summary = db.Column(db.Text)

    # Original description retrieved from Open Library.
    source_description = db.Column(db.Text)

    # Additional information about the selected edition.
    publisher = db.Column(db.String)
    language = db.Column(db.String)
    number_of_pages = db.Column(db.Integer)

    # Main category assigned during the catalog import.
    category = db.Column(db.String)

    # Open Library cover information.
    cover_id = db.Column(db.Integer)
    cover_url = db.Column(db.String)

    # Relative path to a locally downloaded cover image.
    # Example: covers/catalog/9780451524935.jpg
    cover_path = db.Column(db.String)

    # References to the corresponding Open Library records.
    author_key = db.Column(db.String)
    work_key = db.Column(db.String)
    edition_key = db.Column(db.String)