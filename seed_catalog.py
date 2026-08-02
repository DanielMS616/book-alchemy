from time import sleep

from app import app
from data_models import CatalogBook, db
from open_library_service import (
    combine_book_data,
    download_cover_image,
    fetch_author_by_key,
    fetch_edition_by_isbn,
    fetch_work_by_key
)


# Defines the books that should be added to the local catalog.
# Each dictionary contains information that we assign ourselves
# or cannot currently retrieve reliably from the direct API endpoints.
SEED_BOOKS = [
    {
        "isbn": "9780451524935",
        "category": "Classics",
        "original_publication_year": 1949
    }
]


def add_catalog_book(seed_data):
    """Loads one book from Open Library and adds it to the catalog."""

    isbn = seed_data["isbn"]

    # Stops early when this ISBN already exists in the local catalog.
    existing_book = CatalogBook.query.filter_by(
        isbn=isbn
    ).first()

    if existing_book:
        print(
            "Catalog entry already exists: "
            f"{existing_book.title}"
        )
        return False

    # Loads the concrete edition identified by the ISBN.
    edition_data = fetch_edition_by_isbn(isbn)

    if edition_data is None:
        print(f"No Open Library edition found for ISBN {isbn}.")
        return False

    # Open Library asks clients not to send requests too quickly.
    sleep(1)

    # Loads the general work connected to the edition.
    work_data = fetch_work_by_key(
        edition_data["work_key"]
    )

    if work_data is None:
        print(f"No work data found for ISBN {isbn}.")
        return False

    sleep(1)

    # Loads the author connected to the work.
    author_data = fetch_author_by_key(
        work_data["author_key"]
    )

    if author_data is None:
        print(f"No author data found for ISBN {isbn}.")
        return False

    # Combines edition, work, and author information
    # into one consistent dictionary.
    complete_book = combine_book_data(
        edition_data,
        work_data,
        author_data,
        original_publication_year=seed_data.get(
            "original_publication_year"
        )
    )

    # Downloads the Open Library cover into Flask's static directory.
    cover_path = download_cover_image(
        complete_book["cover_url"],
        complete_book["isbn"]
    )

    # Creates the database object for the local discovery catalog.
    catalog_book = CatalogBook(
        isbn=complete_book["isbn"],
        title=complete_book["title"],
        author_name=complete_book["author_name"],
        publication_year=complete_book["publication_year"],
        original_publication_year=complete_book[
            "original_publication_year"
        ],

        # The original Open Library description remains unchanged.
        source_description=complete_book[
            "source_description"
        ],

        # The standardized visible summary will be created later.
        summary=None,

        publisher=complete_book["publisher"],
        language=complete_book["language"],
        number_of_pages=complete_book["number_of_pages"],
        category=seed_data["category"],

        cover_id=complete_book["cover_id"],
        cover_url=complete_book["cover_url"],

        cover_path=cover_path,

        author_key=complete_book["author_key"],
        work_key=complete_book["work_key"],
        edition_key=complete_book["edition_key"]
    )

    db.session.add(catalog_book)
    db.session.commit()

    print(
        "Catalog entry created: "
        f"{catalog_book.title} by {catalog_book.author_name}"
    )

    return True


def seed_catalog():
    """Adds all configured seed books to the local catalog."""

    created_books = 0

    # enumerate(..., start=1) provides both the current position
    # and the corresponding seed dictionary.
    for position, seed_data in enumerate(
        SEED_BOOKS,
        start=1
    ):
        print(
            f"Processing book {position} of "
            f"{len(SEED_BOOKS)}..."
        )

        if add_catalog_book(seed_data):
            created_books += 1

    print()
    print(
        f"Catalog seeding completed. "
        f"{created_books} new book(s) added."
    )


if __name__ == "__main__":
    # Database operations require the configured Flask application.
    with app.app_context():
        seed_catalog()