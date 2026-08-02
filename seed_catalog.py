import json
from pathlib import Path
from time import sleep

from app import app
from data_models import CatalogBook, db
from open_library_service import (
    combine_book_data,
    convert_to_isbn13,
    download_cover_image,
    fetch_author_by_key,
    fetch_books_by_isbns,
    fetch_edition_by_isbn,
    fetch_work_by_key,
    find_search_result_by_isbn,
    normalize_search_book,
    select_isbn
)


# Absolute path to the JSON file containing the catalog seed data.
SEED_DATA_FILE = (
    Path(__file__).resolve().parent
    / "catalog_seed_data.json"
)

# Maximum number of ISBNs sent in one Search API request.
BATCH_SIZE = 50


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


def find_existing_catalog_book_by_isbn(isbn):
    """Finds a catalog entry using an equivalent ISBN-10 or ISBN-13."""

    requested_isbn13 = convert_to_isbn13(isbn)

    if requested_isbn13 is None:
        return None

    # Open Library sometimes stores an ISBN-10 even when
    # the seed file contains the equivalent ISBN-13.
    catalog_books = CatalogBook.query.all()

    for catalog_book in catalog_books:
        stored_isbn13 = convert_to_isbn13(
            catalog_book.isbn
        )

        if stored_isbn13 == requested_isbn13:
            return catalog_book

    return None


def find_existing_catalog_book(book_data):
    """Finds an existing catalog entry using stable identifiers."""

    edition_key = book_data.get("edition_key")

    if edition_key:
        existing_book = CatalogBook.query.filter_by(
            edition_key=edition_key
        ).first()

        if existing_book:
            return existing_book

    work_key = book_data.get("work_key")

    if work_key:
        existing_book = CatalogBook.query.filter_by(
            work_key=work_key
        ).first()

        if existing_book:
            return existing_book

    isbn = book_data.get("isbn")

    if isbn:
        existing_book = CatalogBook.query.filter_by(
            isbn=isbn
        ).first()

        if existing_book:
            return existing_book

    return None


def add_catalog_book(seed_data, search_result):
    """Adds one normalized Search API result to the local catalog."""

    # The Search API returns a structure that differs from our
    # CatalogBook model. This function converts the API result
    # into one consistent dictionary containing only the fields
    # required by our application.
    normalized_book = normalize_search_book(
        search_result,
        seed_data["isbn"],
        seed_data.get("original_publication_year")
    )

    # A missing result usually means that the requested ISBN
    # could not be matched to one of the embedded editions.
    if normalized_book is None:
        raise ValueError(
            "The matching Search API result could not be normalized."
        )

    # Checks stable Open Library identifiers before inserting.
    # This prevents duplicates even when another ISBN or edition
    # of the same literary work is used later.
    existing_book = find_existing_catalog_book(
        normalized_book
    )

    if existing_book:
        print(
            "Catalog entry already exists: "
            f"{existing_book.title}"
        )

        # False tells seed_catalog() that no new database
        # entry was created.
        return False

    # Downloads the selected edition cover into:
    # static/covers/catalog/
    #
    # download_cover_image() reuses an existing local image,
    # so repeated seed runs do not download the same cover again.
    cover_path = download_cover_image(
        normalized_book["cover_url"],
        normalized_book["isbn"]
    )

    # Creates the SQLAlchemy object that represents one book
    # in the local discovery catalog.
    #
    # CatalogBook is separate from Book:
    # - CatalogBook contains recommendations and discovery data.
    # - Book will later contain the user's personal collection,
    #   notes, favorites, and personal categories.
    catalog_book = CatalogBook(
        isbn=normalized_book["isbn"],
        title=normalized_book["title"],
        author_name=normalized_book["author_name"],

        # publication_year describes the selected concrete edition.
        publication_year=normalized_book[
            "publication_year"
        ],

        # original_publication_year describes when the work itself
        # was originally published.
        original_publication_year=normalized_book[
            "original_publication_year"
        ],

        # The Search API may only provide a first sentence here.
        # A more complete description can later be retrieved
        # through the detailed single-book API endpoints.
        source_description=normalized_book[
            "source_description"
        ],

        # The visible and standardized summary will be generated
        # in a later development step.
        summary=None,

        publisher=normalized_book["publisher"],
        language=normalized_book["language"],
        number_of_pages=normalized_book[
            "number_of_pages"
        ],

        # The category is curated in catalog_seed_data.json
        # instead of being copied from noisy API subject lists.
        category=seed_data["category"],

        # cover_url keeps the original external address.
        # cover_path points to the downloaded local image.
        cover_id=normalized_book["cover_id"],
        cover_url=normalized_book["cover_url"],
        cover_path=cover_path,

        # These Open Library identifiers help us recognize
        # duplicate editions and works during future imports.
        author_key=normalized_book["author_key"],
        work_key=normalized_book["work_key"],
        edition_key=normalized_book["edition_key"]
    )

    # Adds the new object to the current SQLAlchemy session.
    db.session.add(catalog_book)

    # Permanently writes the new catalog entry to SQLite.
    db.session.commit()

    print(
        "Catalog entry created: "
        f"{catalog_book.title} by "
        f"{catalog_book.author_name}"
    )

    # True tells seed_catalog() that the created counter
    # should be increased.
    return True


def add_catalog_book_from_single_api(seed_data):
    """Imports one catalog book using the detailed API endpoints."""

    # The seed file contains the requested ISBN, our curated category,
    # and optionally the verified original publication year.
    isbn = seed_data["isbn"]

    # First, load the exact edition belonging to the requested ISBN.
    #
    # An edition represents a concrete published version of a book.
    # It may contain information such as:
    # - publisher
    # - publication year
    # - language
    # - number of pages
    # - edition-specific cover
    edition_data = fetch_edition_by_isbn(isbn)

    if edition_data is None:
        raise ValueError(
            "No Open Library edition was found."
        )

    # A short pause prevents several detailed API requests
    # from being sent immediately one after another.
    sleep(1)

    # The edition contains a reference to the general literary work.
    #
    # Example:
    # One edition of "The Hobbit" may have been published in 2012,
    # while the work itself was originally published in 1937.
    work_key = edition_data.get("work_key")

    if not work_key:
        raise ValueError(
            "The Open Library edition has no work key."
        )

    # Load the general work data.
    #
    # Work data can contain information shared by all editions,
    # such as the original title, subjects, description, and author.
    work_data = fetch_work_by_key(work_key)

    if work_data is None:
        raise ValueError(
            "No Open Library work was found."
        )

    sleep(1)

    # The work record contains the reference to its author.
    author_key = work_data.get("author_key")

    if not author_key:
        raise ValueError(
            "The Open Library work has no author key."
        )

    # Load the detailed author information.
    #
    # This can include the author's name, birth and death dates,
    # biography, alternate names, and an Open Library photo ID.
    author_data = fetch_author_by_key(author_key)

    if author_data is None:
        raise ValueError(
            "No Open Library author was found."
        )

    # The three API responses use different structures.
    # combine_book_data() merges them into one consistent dictionary
    # that can be used by our CatalogBook database model.
    #
    # The manually curated original publication year from the seed
    # file has priority over an unreliable or missing API value.
    complete_book = combine_book_data(
        edition_data,
        work_data,
        author_data,
        original_publication_year=seed_data.get(
            "original_publication_year"
        )
    )

    if complete_book is None:
        raise ValueError(
            "The detailed Open Library data could not be combined."
        )

    # Before creating a new database row, check whether the same
    # edition, work, or ISBN already exists in the catalog.
    #
    # This also prevents another edition of the same literary work
    # from being added accidentally.
    existing_book = find_existing_catalog_book(
        complete_book
    )

    if existing_book:
        print(
            "Catalog entry already exists: "
            f"{existing_book.title}"
        )

        # False tells seed_catalog() that no new row was created.
        return False

    # Download the selected cover into:
    # static/covers/catalog/
    #
    # If the image already exists locally, the download function
    # returns the existing path instead of downloading it again.
    cover_path = download_cover_image(
        complete_book["cover_url"],
        complete_book["isbn"]
    )

    # Create the SQLAlchemy object for the local discovery catalog.
    #
    # This is a CatalogBook, not a personal Book:
    # CatalogBook contains curated discovery data.
    # Book will later contain personal notes, favorites, and categories.
    catalog_book = CatalogBook(
        isbn=complete_book["isbn"],
        title=complete_book["title"],
        author_name=complete_book["author_name"],

        # The publication year belongs to this concrete edition.
        publication_year=complete_book[
            "publication_year"
        ],

        # The original publication year belongs to the literary work.
        original_publication_year=complete_book[
            "original_publication_year"
        ],

        # summary remains empty until we create a standardized
        # user-facing summary in a later development step.
        summary=None,

        # The original Open Library description is preserved
        # separately and is not overwritten by a future summary.
        source_description=complete_book[
            "source_description"
        ],

        publisher=complete_book["publisher"],
        language=complete_book["language"],
        number_of_pages=complete_book[
            "number_of_pages"
        ],

        # The category comes from our curated JSON seed data,
        # not from Open Library's large and inconsistent subject lists.
        category=seed_data["category"],

        # cover_url stores the external source.
        # cover_path points to the locally downloaded image.
        cover_id=complete_book["cover_id"],
        cover_url=complete_book["cover_url"],
        cover_path=cover_path,

        # These identifiers connect our local record to Open Library
        # and help detect duplicates during future imports.
        author_key=complete_book["author_key"],
        work_key=complete_book["work_key"],
        edition_key=complete_book["edition_key"]
    )

    # Add the new object to the current database transaction.
    db.session.add(catalog_book)

    # Permanently save the catalog entry in SQLite.
    db.session.commit()

    print(
        "Catalog entry created using single-book fallback: "
        f"{catalog_book.title} by "
        f"{catalog_book.author_name}"
    )

    # True tells seed_catalog() to increase the created counter.
    return True


def seed_catalog():
    """Imports all configured catalog books in API batches."""

    # Loads and validates the entries from catalog_seed_data.json.
    # Every returned dictionary already contains a valid ISBN,
    # category, and optional original publication year.
    seed_books = load_seed_books()

    # These counters create a useful summary after a long import.
    created_books = 0
    skipped_books = 0
    failed_books = 0
    processed_books = 0

    # Divides the complete seed list into smaller groups.
    #
    # Example with BATCH_SIZE = 50:
    # 200 books become four batches containing 50 books each.
    #
    # range() is useful here because its step argument moves
    # through the list in fixed intervals of BATCH_SIZE.
    seed_batches = [
        seed_books[start:start + BATCH_SIZE]
        for start in range(
            0,
            len(seed_books),
            BATCH_SIZE
        )
    ]

    # enumerate(..., start=1) provides both the current batch
    # number and the corresponding list of seed entries.
    for batch_number, seed_batch in enumerate(
        seed_batches,
        start=1
    ):
        print()
        print(
            f"Fetching batch {batch_number} of "
            f"{len(seed_batches)} "
            f"({len(seed_batch)} ISBNs)..."
        )

        # Creates a simple ISBN list for the Search API request.
        batch_isbns = [
            seed_data["isbn"]
            for seed_data in seed_batch
        ]

        try:
            # One Search API request loads metadata for the
            # complete batch instead of sending several requests
            # for every individual book.
            search_results = fetch_books_by_isbns(
                batch_isbns
            )

        except Exception as error:
            # Without a batch response, none of the books inside
            # this batch can use the normal batch import.
            failed_books += len(seed_batch)

            print(
                f"Batch {batch_number} failed: "
                f"{type(error).__name__}: {error}"
            )

            # Continues with the next batch instead of stopping
            # the complete catalog import.
            continue

        # Processes the original seed entries in their configured
        # order. The API result order is not reliable and may differ.
        for seed_data in seed_batch:
            processed_books += 1
            isbn = seed_data["isbn"]

            print(
                f"Processing book {processed_books} of "
                f"{len(seed_books)}..."
            )

            try:
                # Checks the local database before depending on
                # the completeness of the current API response.
                #
                # ISBN-10 and the equivalent ISBN-13 are treated
                # as the same edition.
                existing_book = (
                    find_existing_catalog_book_by_isbn(isbn)
                )

                if existing_book:
                    skipped_books += 1

                    print(
                        "Catalog entry already exists: "
                        f"{existing_book.title}"
                    )

                    # Skips the remaining processing for this book
                    # and starts the next loop iteration.
                    continue

                # The Search API does not guarantee that its result
                # order matches the ISBN order from our seed file.
                # We therefore locate the correct result by ISBN.
                search_result = find_search_result_by_isbn(
                    search_results,
                    isbn
                )

                if search_result is None:
                    # Embedded edition data can occasionally be
                    # incomplete even though the book exists.
                    #
                    # In this case, the detailed single-book API
                    # endpoints are used as a slower but more
                    # reliable fallback.
                    print(
                        "No exact edition found in batch data. "
                        "Using single-book fallback..."
                    )

                    book_was_created = (
                        add_catalog_book_from_single_api(
                            seed_data
                        )
                    )

                else:
                    # Uses the faster batch result when the exact
                    # requested edition was found.
                    book_was_created = add_catalog_book(
                        seed_data,
                        search_result
                    )

            except Exception as error:
                # A failed commit can leave the SQLAlchemy session
                # in an invalid transaction state. rollback()
                # restores the last valid database state.
                db.session.rollback()

                failed_books += 1

                # The error type and message remain visible,
                # but the next book is still processed.
                print(
                    f"Catalog entry failed for ISBN {isbn}: "
                    f"{type(error).__name__}: {error}"
                )

                continue

            # Both import functions return True when they create
            # a new row and False when they skip an existing one.
            if book_was_created:
                created_books += 1
            else:
                skipped_books += 1

        # A short pause between batches avoids sending all Search
        # API requests immediately one after another.
        if batch_number < len(seed_batches):
            sleep(1)

    # Prints a compact result summary after all batches have
    # either been processed or skipped because of an error.
    print()
    print("Catalog seeding completed.")
    print(f"Created: {created_books}")
    print(f"Skipped: {skipped_books}")
    print(f"Failed:  {failed_books}")


if __name__ == "__main__":
    # Database operations require the configured Flask application.
    with app.app_context():
        seed_catalog()