from datetime import datetime

def select_isbn(isbn_numbers):
    """Returns an ISBN-13 if available, otherwise an ISBN-10."""

    # Open Library may return no ISBN values for a book.
    if not isbn_numbers:
        return None

    # First, the entire list is searched for an ISBN-13.
    # ISBN-13 is preferred because it is the current standard.
    for isbn in isbn_numbers:
        cleaned_isbn = isbn.replace("-", "").strip()

        if len(cleaned_isbn) == 13 and cleaned_isbn.isdigit():
            return cleaned_isbn

    # Only if no ISBN-13 exists do we search for an ISBN-10.
    for isbn in isbn_numbers:
        cleaned_isbn = isbn.replace("-", "").strip().upper()

        # The first nine characters must be digits.
        # The final character may be a digit or the letter X.
        if (
            len(cleaned_isbn) == 10
            and cleaned_isbn[:9].isdigit()
            and (
                cleaned_isbn[-1].isdigit()
                or cleaned_isbn[-1] == "X"
            )
        ):
            return cleaned_isbn

    # No structurally valid ISBN was found.
    return None


def extract_year(date_value):
    """Extracts a four-digit year from an Open Library date value."""

    # Open Library may return no publication date.
    if not date_value:
        return None

    # Some API fields contain the date inside a list.
    # In that case, the first available value is used.
    if isinstance(date_value, list):
        date_value = date_value[0]

    # Converts the value into a string so that it can be searched.
    date_text = str(date_value)

    # Splits the text into individual parts and searches
    # for a four-digit number that could represent a year.
    for text_part in date_text.replace(",", " ").split():
        cleaned_part = text_part.strip("?().")

        if (
            len(cleaned_part) == 4
            and cleaned_part.isdigit()
        ):
            return int(cleaned_part)

    # No usable four-digit year was found.
    return None


def extract_description(description_value):
    """Returns the text from an Open Library description value."""

    # Some descriptions are returned as a dictionary
    # containing the actual text under the key "value".
    if isinstance(description_value, dict):
        description_text = description_value.get("value")

    # Other descriptions are returned directly as a string.
    elif isinstance(description_value, str):
        description_text = description_value

    # Missing or unsupported values cannot provide a description.
    else:
        return None

    # An empty description should be treated like a missing value.
    if not description_text:
        return None

    # Removes unnecessary whitespace from the beginning and end.
    return description_text.strip()


def extract_first_text(value):
    """Returns the first non-empty text from a string or list."""

    # A direct string can be returned after removing
    # unnecessary whitespace.
    if isinstance(value, str):
        cleaned_value = value.strip()

        if cleaned_value:
            return cleaned_value

        return None

    # Some Open Library fields contain multiple text values.
    # The first usable string is returned.
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                cleaned_item = item.strip()

                if cleaned_item:
                    return cleaned_item

    # Unsupported or empty values cannot provide text.
    return None


def extract_language(language_value):
    """Returns the first usable Open Library language code."""

    # Missing or empty language data cannot provide a language code.
    if not language_value:
        return None

    # Converts a single value into a list so that all values
    # can be processed by the same loop.
    if not isinstance(language_value, list):
        language_value = [language_value]

    for language_entry in language_value:
        # The direct ISBN endpoint may return a dictionary:
        # {"key": "/languages/eng"}
        if isinstance(language_entry, dict):
            language_text = language_entry.get("key")

        # Search results may return a direct language code:
        # "eng"
        elif isinstance(language_entry, str):
            language_text = language_entry

        else:
            continue

        if not language_text:
            continue

        # Removes whitespace and extracts the final part
        # from values such as "/languages/eng".
        language_code = language_text.strip().split("/")[-1]

        if language_code:
            return language_code

    # No usable language code was found.
    return None


def extract_cover_id(cover_value):
    """Returns the first usable positive Open Library cover ID."""

    # Missing cover data cannot provide a cover ID.
    if cover_value is None:
        return None

    # Converts a single cover ID into a list so that all values
    # can be processed with the same loop.
    if not isinstance(cover_value, list):
        cover_value = [cover_value]

    for cover_id in cover_value:
        # Boolean values are technically integers in Python,
        # but they are not valid Open Library cover IDs.
        if isinstance(cover_id, bool):
            continue

        # A usable cover ID must be a positive integer.
        if isinstance(cover_id, int) and cover_id > 0:
            return cover_id

    # No usable cover ID was found.
    return None


def build_cover_url(cover_id):
    """Builds an Open Library cover URL from a valid cover ID."""

    # A missing cover ID cannot produce a usable image URL.
    if cover_id is None:
        return None

    # Uses the medium-sized Open Library cover image.
    return (
        "https://covers.openlibrary.org"
        f"/b/id/{cover_id}-M.jpg"
    )


def extract_reference_key(reference_value):
    """Returns the first usable Open Library reference key."""

    # Missing reference data cannot provide a key.
    if not reference_value:
        return None

    # Converts a single reference into a list so that
    # all values can be processed with the same loop.
    if not isinstance(reference_value, list):
        reference_value = [reference_value]

    for reference_entry in reference_value:
        # Open Library usually returns references as dictionaries:
        # {"key": "/works/OL1168083W"}
        if isinstance(reference_entry, dict):
            reference_key = reference_entry.get("key")

        # A direct string is also supported.
        elif isinstance(reference_entry, str):
            reference_key = reference_entry

        else:
            continue

        if not reference_key:
            continue

        cleaned_key = reference_key.strip()

        if cleaned_key:
            return cleaned_key

    # No usable reference key was found.
    return None


def extract_author_key(author_entries):
    """Returns the first usable author key from Open Library work data."""

    # Missing author data cannot provide an author key.
    if not isinstance(author_entries, list):
        return None

    for author_entry in author_entries:
        # Each work author is normally represented by a dictionary.
        if not isinstance(author_entry, dict):
            continue

        # The actual author reference is nested inside
        # the outer author entry.
        author_reference = author_entry.get("author")

        # Reuses the existing helper to extract the key
        # from the nested author reference.
        author_key = extract_reference_key(author_reference)

        if author_key:
            return author_key

    # No usable author reference was found.
    return None


def normalize_edition_data(edition_data):
    """Converts Open Library edition data into a consistent dictionary."""

    # A missing or invalid API response cannot be normalized.
    if not isinstance(edition_data, dict):
        return None

    # Collects all available ISBN-13 and ISBN-10 values.
    # They are combined because select_isbn() decides which
    # valid ISBN should be preferred.
    isbn_numbers = []

    isbn_13_values = edition_data.get("isbn_13", [])

    if isinstance(isbn_13_values, list):
        isbn_numbers.extend(isbn_13_values)
    elif isinstance(isbn_13_values, str):
        isbn_numbers.append(isbn_13_values)

    isbn_10_values = edition_data.get("isbn_10", [])

    if isinstance(isbn_10_values, list):
        isbn_numbers.extend(isbn_10_values)
    elif isinstance(isbn_10_values, str):
        isbn_numbers.append(isbn_10_values)

    # Selects and normalizes the individual edition values.
    isbn = select_isbn(isbn_numbers)
    cover_id = extract_cover_id(
        edition_data.get("covers")
    )

    return {
        "edition_key": extract_reference_key(
            edition_data.get("key")
        ),
        "work_key": extract_reference_key(
            edition_data.get("works")
        ),
        "title": extract_first_text(
            edition_data.get("title")
        ),
        "subtitle": extract_first_text(
            edition_data.get("subtitle")
        ),
        "isbn": isbn,
        "publication_year": extract_year(
            edition_data.get("publish_date")
        ),
        "publisher": extract_first_text(
            edition_data.get("publishers")
        ),
        "language": extract_language(
            edition_data.get("languages")
        ),
        "number_of_pages": edition_data.get(
            "number_of_pages"
        ),
        "cover_id": cover_id,
        "cover_url": build_cover_url(cover_id),
        "source_description": extract_description(
            edition_data.get("description")
        )
    }


def normalize_work_data(work_data):
    """Converts Open Library work data into a consistent dictionary."""

    # A missing or invalid API response cannot be normalized.
    if not isinstance(work_data, dict):
        return None

    # Collects all usable subject strings.
    subjects = []

    for subject in work_data.get("subjects", []):
        if not isinstance(subject, str):
            continue

        cleaned_subject = subject.strip()

        if cleaned_subject:
            subjects.append(cleaned_subject)

    cover_id = extract_cover_id(
        work_data.get("covers")
    )

    return {
        "work_key": extract_reference_key(
            work_data.get("key")
        ),
        "title": extract_first_text(
            work_data.get("title")
        ),
        "original_publication_year": extract_year(
            work_data.get("first_publish_date")
        ),
        "author_key": extract_author_key(
            work_data.get("authors")
        ),
        "subjects": subjects,
        "cover_id": cover_id,
        "cover_url": build_cover_url(cover_id),
        "source_description": extract_description(
            work_data.get("description")
        )
    }




def parse_open_library_date(date_value):
    """Converts a supported Open Library date into a Python date object."""

    # Missing values and unsupported data types cannot provide a date.
    if not isinstance(date_value, str):
        return None

    cleaned_date = date_value.strip()

    if not cleaned_date:
        return None

    # Open Library uses several different date formats.
    supported_formats = (
        "%d %B %Y",
        "%B %d, %Y",
        "%Y-%m-%d"
    )

    for date_format in supported_formats:
        try:
            return datetime.strptime(
                cleaned_date,
                date_format
            ).date()

        except ValueError:
            # The current format did not match,
            # so the next supported format is tested.
            continue

    # Incomplete or unknown formats are not guessed.
    return None


def normalize_author_data(author_data):
    """Converts Open Library author data into a consistent dictionary."""

    # A missing or invalid API response cannot be normalized.
    if not isinstance(author_data, dict):
        return None

    # Collects all usable alternate names.
    alternate_names = []

    for alternate_name in author_data.get("alternate_names", []):
        if not isinstance(alternate_name, str):
            continue

        cleaned_name = alternate_name.strip()

        if cleaned_name:
            alternate_names.append(cleaned_name)

    # Open Library may provide several author photos.
    # The first usable positive ID is selected.
    photo_id = extract_cover_id(
        author_data.get("photos")
    )

    return {
        "author_key": extract_reference_key(
            author_data.get("key")
        ),
        "name": extract_first_text(
            author_data.get("name")
        ),
        "personal_name": extract_first_text(
            author_data.get("personal_name")
        ),
        "alternate_names": alternate_names,

        # Converts supported API date strings into Python date objects.
        "birth_date": parse_open_library_date(
            author_data.get("birth_date")
        ),
        "death_date": parse_open_library_date(
            author_data.get("death_date")
        ),

        # Keeps the original text in case a date could not be parsed.
        "birth_date_raw": extract_first_text(
            author_data.get("birth_date")
        ),
        "death_date_raw": extract_first_text(
            author_data.get("death_date")
        ),

        "photo_id": photo_id,

        # Keeps the original Open Library biography.
        "source_biography": extract_description(
            author_data.get("bio")
        )
    }


def combine_book_data(
    edition_data,
    work_data,
    author_data,
    original_publication_year=None
):
    """Combines normalized edition, work, and author data."""

    # All three inputs must be normalized dictionaries.
    if not isinstance(edition_data, dict):
        return None

    if not isinstance(work_data, dict):
        return None

    if not isinstance(author_data, dict):
        return None

    # The description of the concrete edition is preferred.
    # If it is missing, the general work description is used.
    source_description = edition_data.get("source_description")
    description_source = "edition"

    if not source_description:
        source_description = work_data.get("source_description")
        description_source = "work"

    if not source_description:
        description_source = None

    # The cover of the concrete edition is preferred.
    # If it is missing, the general work cover is used.
    cover_id = (
        edition_data.get("cover_id")
        or work_data.get("cover_id")
    )

    cover_url = (
        edition_data.get("cover_url")
        or work_data.get("cover_url")
    )

    # The direct work endpoint may not contain an original publication year.
    # A year from the Search API can therefore be passed as a fallback.
    work_publication_year = (
        work_data.get("original_publication_year")
        or original_publication_year
    )

    return {
        # Open Library references
        "edition_key": edition_data.get("edition_key"),
        "work_key": work_data.get("work_key"),
        "author_key": author_data.get("author_key"),

        # Main book information
        "title": (
            edition_data.get("title")
            or work_data.get("title")
        ),
        "subtitle": edition_data.get("subtitle"),
        "isbn": edition_data.get("isbn"),
        "publication_year": edition_data.get(
            "publication_year"
        ),
        "original_publication_year": work_publication_year,
        "publisher": edition_data.get("publisher"),
        "language": edition_data.get("language"),
        "number_of_pages": edition_data.get(
            "number_of_pages"
        ),

        # Author information
        "author_name": author_data.get("name"),
        "author_birth_date": author_data.get("birth_date"),
        "author_death_date": author_data.get("death_date"),
        "author_alternate_names": author_data.get(
            "alternate_names",
            []
        ),

        # Additional metadata
        "subjects": work_data.get("subjects", []),
        "cover_id": cover_id,
        "cover_url": cover_url,

        # Original API texts
        "source_description": source_description,
        "description_source": description_source,
        "source_biography": author_data.get(
            "source_biography"
        )
    }