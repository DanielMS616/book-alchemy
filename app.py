import os

from datetime import datetime
from flask import Flask, redirect, render_template, request, url_for

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


@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    """Displays the book form and stores submitted book data."""

    # Loads all authors for the dropdown menu.
    authors = Author.query.all()

    # A POST request is sent when the book form is submitted.
    if request.method == "POST":
        # Reads the submitted values from the form.
        isbn = request.form.get("isbn")
        title = request.form.get("title")
        publication_year = int(
            request.form.get("publication_year")
        )
        author_id = int(
            request.form.get("author_id")
        )

        # Creates a new Book object from the submitted form data.
        new_book = Book(
            isbn=isbn,
            title=title,
            publication_year=publication_year,
            author_id=author_id
        )

        # Adds the new book to the current database session.
        db.session.add(new_book)

        # Permanently saves the book in the database.
        db.session.commit()

        # Displays the form again with a success message.
        return render_template(
            "add_book.html",
            authors=authors,
            message="Book successfully added."
        )

    # A GET request only displays the form.
    return render_template(
        "add_book.html",
        authors=authors
    )


@app.route("/book/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    """Deletes a book and removes its author if no other books remain."""

    # Searches for the book using its primary key.
    book = db.session.get(Book, book_id)

    # Redirects to the homepage if the book does not exist.
    if book is None:
        return redirect(
            url_for(
                "home",
                success="Book could not be found."
            )
        )

    # Stores information that is still needed after deleting the book.
    book_title = book.title
    author = book.author

    # Searches for another book written by the same author.
    # The current book is excluded from this query.
    another_book = Book.query.filter(
        Book.author_id == author.id,
        Book.id != book.id
    ).first()

    # Marks the selected book for deletion.
    db.session.delete(book)

    # If no other book by this author exists,
    # the author is also removed from the database.
    if another_book is None:
        db.session.delete(author)

    # Saves both deletions together.
    db.session.commit()

    return redirect(
        url_for(
            "home",
            success=f'"{book_title}" was successfully deleted.'
        )
    )


@app.route("/")
def home():
    """Displays books and allows sorting and searching by title."""

    # Reads the search term from the URL.
    # If no search term exists, an empty string is used.
    search_query = request.args.get("search", "").strip()

    # Reads the selected sorting option from the URL.
    sort_by = request.args.get("sort", "title")

    # Starts a query for the books table.
    # The query is not executed yet.
    books_query = Book.query

    # Reads a success message that may have been added during a redirect.
    success_message = request.args.get("success")

    if search_query:
        # LIKE searches for the entered text anywhere in the title.
        # The percentage signs are SQL wildcards.
        books_query = books_query.filter(
            Book.title.like(f"%{search_query}%")
        )

    if sort_by == "author":
        # Connects books with authors and sorts by author name.
        books_query = (
            books_query
            .join(Author)
            .order_by(Author.name)
        )
    else:
        # Sorts by book title by default.
        books_query = books_query.order_by(Book.title)

    # Executes the completed database query.
    books = books_query.all()

    # Prepares a message if a search was performed
    # but no matching books were found.
    message = None

    if search_query and not books:
        message = f'No books found for "{search_query}".'

    return render_template(
        "home.html",
        books=books,
        search_query=search_query,
        message=message,
        success_message=success_message
    )


# Creates all database tables defined by the SQLAlchemy models.
# The application context gives SQLAlchemy access to the Flask configuration.
# with app.app_context():
#     db.create_all()