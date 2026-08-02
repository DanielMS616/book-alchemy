import json
from pathlib import Path
from time import sleep

from app import app
from data_models import CatalogBook, db
from open_library_service import (
    combine_book_data,
    download_cover_image,
    fetch_author_by_key,
    fetch_edition_by_isbn,
    fetch_work_by_key,
    select_isbn
)


# Absolute path to the JSON file containing the catalog seed data.
SEED_DATA_FILE = (
    Path(__file__).resolve().parent
    / "catalog_seed_data.json"
)


def validate_seed_book(seed_data, position):
    """Validates and normalizes one catalog seed entry."""

    # Every JSON array entry must represent one dictionary.
    if not isinstance(seed_data, dict):
        raise ValueError(
            f"Seed entry {position} must be a JSON object."
        )

    isbn = seed_data.get("isbn")

    # select_isbn() removes spaces and hyphens and checks
    # whether the value resembles an ISBN-10 or ISBN-13.
    normalized_isbn = select_isbn([isbn])

    if normalized_isbn is None:
        raise ValueError(
            f"Seed entry {position} contains an invalid ISBN."
        )

    category = seed_data.get("category")

    if not isinstance(category, str) or not category.strip():
        raise ValueError(
            f"Seed entry {position} requires a category."
        )

    original_publication_year = seed_data.get(
        "original_publication_year"
    )

    # bool must be rejected explicitly because Python treats
    # True and False as subclasses of int.
    if (
        original_publication_year is not None
        and (
            isinstance(original_publication_year, bool)
            or not isinstance(original_publication_year, int)
            or original_publication_year <= 0
        )
    ):
        raise ValueError(
            f"Seed entry {position} contains an invalid "
            "original publication year."
        )

    # A copy is returned so that the original dictionary
    # loaded from the JSON file is not modified directly.
    validated_seed_data = seed_data.copy()

    validated_seed_data["isbn"] = normalized_isbn
    validated_seed_data["category"] = category.strip()

    return validated_seed_data


def load_seed_books():
    """Loads and validates the catalog seed entries."""

    # Reads the complete JSON file as text.
    json_content = SEED_DATA_FILE.read_text(
        encoding="utf-8"
    )

    # Converts the JSON array into Python data.
    seed_books = json.loads(json_content)

    # The seed file itself must contain a JSON array.
    if not isinstance(seed_books, list):
        raise ValueError(
            "The catalog seed file must contain a JSON list."
        )

    validated_seed_books = []

    # enumerate(..., start=1) lets error messages refer
    # to the human-readable position inside the JSON list.
    for position, seed_data in enumerate(
        seed_books,
        start=1
    ):
        validated_seed_book = validate_seed_book(
            seed_data,
            position
        )

        validated_seed_books.append(
            validated_seed_book
        )

    return validated_seed_books


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

    # Loads the seed entries from catalog_seed_data.json.
    seed_books = load_seed_books()

    created_books = 0
    skipped_books = 0
    failed_books = 0

    # enumerate(..., start=1) returns both the current position
    # and the corresponding seed dictionary.
    for position, seed_data in enumerate(
        seed_books,
        start=1
    ):
        isbn = seed_data.get("isbn", "unknown ISBN")

        print(
            f"Processing book {position} of "
            f"{len(seed_books)}..."
        )

        try:
            # add_catalog_book() returns True when a new book
            # was created and False when it was skipped.
            book_was_created = add_catalog_book(seed_data)

        except Exception as error:
            # A failed database operation can leave the current
            # SQLAlchemy session in an unusable state.
            db.session.rollback()

            failed_books += 1

            print(
                f"Catalog entry failed for ISBN {isbn}: "
                f"{type(error).__name__}: {error}"
            )

            # Continues with the next seed entry.
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