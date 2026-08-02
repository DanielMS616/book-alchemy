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
    # Classics
    {
        "isbn": "9780451524935",
        "category": "Classics",
        "original_publication_year": 1949
    },
    {
        "isbn": "9780316769488",
        "category": "Classics",
        "original_publication_year": 1951
    },
    {
        "isbn": "9780451526342",
        "category": "Classics",
        "original_publication_year": 1945
    },
    {
        "isbn": "9780141439518",
        "category": "Classics",
        "original_publication_year": 1813
    },
    {
        "isbn": "9780743273565",
        "category": "Classics",
        "original_publication_year": 1925
    },
    {
        "isbn": "9780061120084",
        "category": "Classics",
        "original_publication_year": 1960
    },

    # Science Fiction
    {
        "isbn": "9780060850524",
        "category": "Science Fiction",
        "original_publication_year": 1932
    },
    {
        "isbn": "9781451673319",
        "category": "Science Fiction",
        "original_publication_year": 1953
    },
    {
        "isbn": "9780441172719",
        "category": "Science Fiction",
        "original_publication_year": 1965
    },
    {
        "isbn": "9780441569595",
        "category": "Science Fiction",
        "original_publication_year": 1984
    },
    {
        "isbn": "9780345404473",
        "category": "Science Fiction",
        "original_publication_year": 1968
    },
    {
        "isbn": "9780441478125",
        "category": "Science Fiction",
        "original_publication_year": 1969
    },

    # Fantasy
    {
        "isbn": "9780547928227",
        "category": "Fantasy",
        "original_publication_year": 1937
    },
    {
        "isbn": "9780547928210",
        "category": "Fantasy",
        "original_publication_year": 1954
    },
    {
        "isbn": "9780547773742",
        "category": "Fantasy",
        "original_publication_year": 1968
    },
    {
        "isbn": "9780756404741",
        "category": "Fantasy",
        "original_publication_year": 2007
    },
    {
        "isbn": "9780765311788",
        "category": "Fantasy",
        "original_publication_year": 2006
    },

    # Software Development
    {
        "isbn": "9780132350884",
        "category": "Software Development",
        "original_publication_year": 2008
    },
    {
        "isbn": "9780135957059",
        "category": "Software Development",
        "original_publication_year": 1999
    },
    {
        "isbn": "9780201633610",
        "category": "Software Development",
        "original_publication_year": 1994
    },
    {
        "isbn": "9780134757599",
        "category": "Software Development",
        "original_publication_year": 1999
    },

    # Non-Fiction and Biography
    {
        "isbn": "9780735211292",
        "category": "Non-Fiction",
        "original_publication_year": 2018
    },
    {
        "isbn": "9780062316097",
        "category": "Non-Fiction",
        "original_publication_year": 2011
    },
    {
        "isbn": "9780374533557",
        "category": "Non-Fiction",
        "original_publication_year": 2011
    },
    {
        "isbn": "9781451648539",
        "category": "Biography",
        "original_publication_year": 2011
    }
]


def add_catalog_book(seed_data):
    """Loads one book from Open Library and adds it to the catalog."""

    isbn = seed_data["isbn"]

    # The edition is loaded first because Open Library may return
    # a different but equivalent ISBN format, such as ISBN-10
    # instead of the ISBN-13 stored in the seed list.
    edition_data = fetch_edition_by_isbn(isbn)

    if edition_data is None:
        print(f"No Open Library edition found for ISBN {isbn}.")
        return False

    # A catalog book represents one work and should not be added again
    # merely because another ISBN format or edition was supplied.
    existing_book = None

    edition_key = edition_data.get("edition_key")

    if edition_key:
        existing_book = CatalogBook.query.filter_by(
            edition_key=edition_key
        ).first()

    work_key = edition_data.get("work_key")

    if existing_book is None and work_key:
        existing_book = CatalogBook.query.filter_by(
            work_key=work_key
        ).first()

    normalized_isbn = edition_data.get("isbn")

    if existing_book is None and normalized_isbn:
        existing_book = CatalogBook.query.filter_by(
            isbn=normalized_isbn
        ).first()

    if existing_book:
        print(
            "Catalog entry already exists: "
            f"{existing_book.title}"
        )
        return False

    # A short pause prevents multiple API requests
    # from being sent immediately after one another.
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

    # Downloads the cover into Flask's static directory.
    # An existing local cover is reused.
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
        source_description=complete_book[
            "source_description"
        ],
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
    skipped_books = 0
    failed_books = 0

    # enumerate(..., start=1) returns both the current position
    # and the corresponding seed dictionary.
    for position, seed_data in enumerate(
        SEED_BOOKS,
        start=1
    ):
        isbn = seed_data.get("isbn", "unknown ISBN")

        print(
            f"Processing book {position} of "
            f"{len(SEED_BOOKS)}..."
        )

        try:
            # add_catalog_book() returns True when a new book
            # was created and False when it was skipped.
            book_was_created = add_catalog_book(seed_data)

        except Exception as error:
            # A failed database operation can leave the current
            # SQLAlchemy session in an unusable state.
            # rollback() returns it to the last valid state.
            db.session.rollback()

            failed_books += 1

            print(
                f"Catalog entry failed for ISBN {isbn}: "
                f"{type(error).__name__}: {error}"
            )

            # continue skips the remaining code of this loop
            # iteration and starts processing the next book.
            continue

        if book_was_created:
            created_books += 1
        else:
            skipped_books += 1

    print()
    print("Catalog seeding completed.")
    print(f"Created: {created_books}")
    print(f"Skipped: {skipped_books}")
    print(f"Failed:  {failed_books}")


if __name__ == "__main__":
    # Database operations require the configured Flask application.
    with app.app_context():
        seed_catalog()