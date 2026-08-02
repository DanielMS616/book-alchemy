import os

from sqlalchemy import or_
from datetime import datetime
from flask import Flask, flash, redirect, render_template, request, url_for

from data_models import db, Author, Book, CatalogBook


# Creates the Flask application.
app = Flask(__name__)

# Flask uses the secret key to protect session data,
# including temporary flash messages.
app.config["SECRET_KEY"] = "book-alchemy-secret-key"

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

    # A POST request is sent when the author form is submitted.
    if request.method == "POST":
        # Reads the submitted values from the form.
        name = request.form.get("name")
        birthdate_value = request.form.get("birthdate")
        date_of_death_value = request.form.get("date_of_death")

        # Converts the birthdate string into a Python date object.
        birth_date = datetime.strptime(
            birthdate_value,
            "%Y-%m-%d"
        ).date()

        # An empty date-of-death field is stored as None.
        date_of_death = None

        if date_of_death_value:
            date_of_death = datetime.strptime(
                date_of_death_value,
                "%Y-%m-%d"
            ).date()

        # Creates a new Author object.
        new_author = Author(
            name=name,
            birth_date=birth_date,
            date_of_death=date_of_death
        )

        # Saves the new author in the database.
        db.session.add(new_author)
        db.session.commit()

        # Stores a temporary success message.
        flash(f'Author "{name}" was successfully added.')

        # Starts a new GET request for the author form.
        return redirect(url_for("add_author"))

    # A GET request displays the empty author form.
    return render_template("add_author.html")


@app.route("/catalog")
def catalog():
    """Displays and searches the local discovery catalog."""

    # Reads the search text from the URL.
    # An empty string means that all catalog books are displayed.
    search_query = request.args.get(
        "search",
        ""
    ).strip()

    # Reads the selected sorting option.
    # Books are sorted alphabetically by title by default.
    sort_by = request.args.get(
        "sort",
        "title"
    )

    # Starts a query for the discovery catalog.
    # SQLAlchemy does not execute it until .all() is called.
    catalog_query = CatalogBook.query

    if search_query:
        # Searches both title and author name.
        #
        # or_() means that a book is included when at least
        # one of the two conditions matches.
        catalog_query = catalog_query.filter(
            or_(
                CatalogBook.title.like(
                    f"%{search_query}%"
                ),
                CatalogBook.author_name.like(
                    f"%{search_query}%"
                )
            )
        )

    if sort_by == "author":
        # Sorts first by author and then by title.
        # The second criterion creates a stable order when
        # several books were written by the same author.
        catalog_query = catalog_query.order_by(
            CatalogBook.author_name,
            CatalogBook.title
        )

    elif sort_by == "category":
        # Groups books alphabetically by category.
        # Books inside each category are sorted by title.
        catalog_query = catalog_query.order_by(
            CatalogBook.category,
            CatalogBook.title
        )

    else:
        # Uses title sorting when no valid alternative was selected.
        sort_by = "title"

        catalog_query = catalog_query.order_by(
            CatalogBook.title
        )

    # Executes the completed database query.
    catalog_books = catalog_query.all()

    message = None

    if search_query and not catalog_books:
        message = (
            f'No catalog books found for '
            f'"{search_query}".'
        )

    return render_template(
        "catalog.html",
        books=catalog_books,
        search_query=search_query,
        sort_by=sort_by,
        message=message
    )


@app.route(
    "/catalog/<int:catalog_book_id>/add",
    methods=["POST"]
)
def add_catalog_book_to_library(catalog_book_id):
    """Copies one catalog book into the personal library."""

    # Loads the selected catalog entry by its primary key.
    catalog_book = db.session.get(
        CatalogBook,
        catalog_book_id
    )

    # Keeps the current catalog search and sorting selection
    # so the user returns to the same catalog view.
    search_query = request.form.get(
        "search",
        ""
    ).strip()

    sort_by = request.form.get(
        "sort",
        "title"
    )

    if catalog_book is None:
        flash("The selected catalog book could not be found.")

        return redirect(
            url_for(
                "catalog",
                search=search_query,
                sort=sort_by
            )
        )

    # First checks the stable Open Library work key.
    # This prevents another edition of the same work from
    # being added to the personal library more than once.
    existing_book = None

    if catalog_book.work_key:
        existing_book = Book.query.filter_by(
            work_key=catalog_book.work_key
        ).first()

    # ISBN is used as a fallback when no matching work key
    # exists in the personal library.
    if existing_book is None:
        existing_book = Book.query.filter_by(
            isbn=catalog_book.isbn
        ).first()

    if existing_book:
        flash(
            f'"{existing_book.title}" is already '
            "in your library."
        )

        return redirect(
            url_for(
                "catalog",
                search=search_query,
                sort=sort_by
            )
        )

    # Removes the HTML entity found in the imported Homer name.
    # The catalog source data itself remains unchanged.
    author_name = (
        catalog_book.author_name
        or "Unknown Author"
    ).replace(
        "&nbsp;",
        " "
    ).strip()

    # Searches for an existing author using the stable
    # Open Library author key whenever one is available.
    author = None

    if catalog_book.author_key:
        author = Author.query.filter_by(
            open_library_key=catalog_book.author_key
        ).first()

    # Author name is used as a fallback for catalog entries
    # without an Open Library author key.
    if author is None:
        author = Author.query.filter_by(
            name=author_name
        ).first()

    # Creates the author only when no matching author exists.
    if author is None:
        author = Author(
            name=author_name,
            open_library_key=catalog_book.author_key
        )

        db.session.add(author)

    # Copies the reusable catalog data into a personal Book.
    #
    # Personal fields such as notes and is_favorite keep
    # their model defaults and can be changed later.
    new_book = Book(
        isbn=catalog_book.isbn,
        title=catalog_book.title,
        publication_year=catalog_book.publication_year,
        original_publication_year=(
            catalog_book.original_publication_year
        ),
        summary=catalog_book.summary,
        source_description=(
            catalog_book.source_description
        ),
        category=catalog_book.category,
        publisher=catalog_book.publisher,
        language=catalog_book.language,
        number_of_pages=catalog_book.number_of_pages,
        cover_id=catalog_book.cover_id,
        cover_url=catalog_book.cover_url,
        cover_path=catalog_book.cover_path,
        work_key=catalog_book.work_key,
        edition_key=catalog_book.edition_key,

        # Assigning the relationship connects the Book
        # with either the existing or newly created Author.
        author=author
    )

    db.session.add(new_book)
    db.session.commit()

    flash(
        f'"{new_book.title}" was added to your library.'
    )

    return redirect(
        url_for(
            "catalog",
            search=search_query,
            sort=sort_by
        )
    )


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

        # Form values arrive as strings and are converted to integers.
        publication_year = int(
            request.form.get("publication_year")
        )
        author_id = int(
            request.form.get("author_id")
        )

        # Creates a new Book object.
        new_book = Book(
            isbn=isbn,
            title=title,
            publication_year=publication_year,
            author_id=author_id
        )

        # Saves the new book in the database.
        db.session.add(new_book)
        db.session.commit()

        # Stores a temporary success message.
        flash(f'Book "{title}" was successfully added.')

        # Starts a new GET request for the book form.
        return redirect(url_for("add_book"))

    # A GET request displays the form and its author dropdown.
    return render_template(
        "add_book.html",
        authors=authors
    )


@app.route("/book/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    """Deletes a book and removes its author if no other books remain."""

    # Searches for the book using its primary key.
    book = db.session.get(Book, book_id)

    # Handles the case that the requested book does not exist.
    if book is None:
        flash("Book could not be found.")
        return redirect(url_for("home"))

    # Stores information needed after deleting the book.
    book_title = book.title
    author = book.author

    # Searches for another book written by the same author.
    # The book currently being deleted is excluded.
    another_book = Book.query.filter(
        Book.author_id == author.id,
        Book.id != book.id
    ).first()

    # Marks the selected book for deletion.
    db.session.delete(book)

    # Removes the author if no other book by this author remains.
    if another_book is None:
        db.session.delete(author)

    # Permanently saves all changes.
    db.session.commit()

    # Stores a temporary message for the next request.
    flash(f'"{book_title}" was successfully deleted.')

    # Redirects to the library homepage.
    return redirect(url_for("home"))


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
        message=message
    )
