import json
from pathlib import Path

from app import app
from data_models import Book, CatalogBook, db


# Uses an absolute path so the script also works when it is
# started from another working directory.
PROJECT_DIRECTORY = Path(__file__).resolve().parent

OVERRIDES_FILE = (
    PROJECT_DIRECTORY
    / "catalog_overrides.json"
)


def load_catalog_overrides():
    """Loads and validates the catalog correction entries."""

    overrides = json.loads(
        OVERRIDES_FILE.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(overrides, list):
        raise ValueError(
            "catalog_overrides.json must contain a JSON list."
        )

    seen_isbns = set()

    for position, override in enumerate(
        overrides,
        start=1
    ):
        if not isinstance(override, dict):
            raise ValueError(
                f"Override {position} must be a JSON object."
            )

        isbn = override.get("isbn")
        title = override.get("title")
        author_name = override.get("author_name")

        if not isinstance(isbn, str) or not isbn.strip():
            raise ValueError(
                f"Override {position} has no valid ISBN."
            )

        if not isinstance(title, str) or not title.strip():
            raise ValueError(
                f"Override {position} has no valid title."
            )

        if (
            not isinstance(author_name, str)
            or not author_name.strip()
        ):
            raise ValueError(
                f"Override {position} has no valid author name."
            )

        normalized_isbn = isbn.strip()

        if normalized_isbn in seen_isbns:
            raise ValueError(
                f"Duplicate override ISBN: {normalized_isbn}"
            )

        seen_isbns.add(normalized_isbn)

    return overrides


def apply_catalog_overrides():
    """Applies curated titles and author names to local book records."""

    overrides = load_catalog_overrides()

    updated_catalog_books = 0
    unchanged_catalog_books = 0
    updated_personal_books = 0
    missing_catalog_books = []

    with app.app_context():
        try:
            for override in overrides:
                isbn = override["isbn"].strip()
                title = override["title"].strip()
                author_name = override[
                    "author_name"
                ].strip()

                # Finds the imported catalog entry using its stable ISBN.
                catalog_book = CatalogBook.query.filter_by(
                    isbn=isbn
                ).first()

                if catalog_book is None:
                    missing_catalog_books.append(isbn)
                    continue

                catalog_was_changed = False

                if catalog_book.title != title:
                    catalog_book.title = title
                    catalog_was_changed = True

                if catalog_book.author_name != author_name:
                    catalog_book.author_name = author_name
                    catalog_was_changed = True

                if catalog_was_changed:
                    updated_catalog_books += 1
                else:
                    unchanged_catalog_books += 1

                # A catalog book may already have been copied into the
                # user's personal library. Those existing copies are
                # updated as well so both views stay consistent.
                personal_books = Book.query.filter_by(
                    isbn=isbn
                ).all()

                for personal_book in personal_books:
                    personal_book_was_changed = False

                    if personal_book.title != title:
                        personal_book.title = title
                        personal_book_was_changed = True

                    if (
                        personal_book.author is not None
                        and personal_book.author.name
                        != author_name
                    ):
                        personal_book.author.name = author_name
                        personal_book_was_changed = True

                    if personal_book_was_changed:
                        updated_personal_books += 1

            # All corrections are saved together in one transaction.
            db.session.commit()

        except Exception:
            # Restores the previous state when any correction fails.
            db.session.rollback()
            raise

    print("Catalog overrides completed.")
    print(f"Catalog updated:   {updated_catalog_books}")
    print(f"Catalog unchanged: {unchanged_catalog_books}")
    print(f"Library updated:   {updated_personal_books}")
    print(f"Catalog missing:   {len(missing_catalog_books)}")

    if missing_catalog_books:
        print()
        print("Missing ISBNs:")

        for isbn in missing_catalog_books:
            print(f"- {isbn}")


if __name__ == "__main__":
    apply_catalog_overrides()
