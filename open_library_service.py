import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from pathlib import Path

# Base address used for all Open Library API requests.
OPEN_LIBRARY_BASE_URL = "https://openlibrary.org"

# Identifies our educational application when making API requests.
OPEN_LIBRARY_USER_AGENT = (
    "BookAlchemy/0.1 (educational project)"
)

# Absolute local directory in which catalog covers are stored.
CATALOG_COVER_DIRECTORY = (
    Path(__file__).resolve().parent
    / "static"
    / "covers"
    / "catalog"
)

# Relative path used later by Flask's static file handling.
CATALOG_COVER_RELATIVE_DIRECTORY = (
    Path("covers")
    / "catalog"
)


def fetch_json(url):
    """Requests JSON data from an Open Library URL."""

    # Creates an HTTP request with an identifying User-Agent.
    request = Request(
        url,
        headers={
            "User-Agent": OPEN_LIBRARY_USER_AGENT
        }
    )

    try:
        # Opens the URL and waits at most ten seconds
        # for the server response.
        with urlopen(request, timeout=10) as response:
            return json.load(response)

    except HTTPError as error:
        # Open Library returns status code 404 when
        # no record exists for the requested identifier.
        if error.code == 404:
            return None

        # Other HTTP errors are converted into a clearer
        # application-level error.
        raise RuntimeError(
            f"Open Library returned HTTP error {error.code}."
        ) from error

    except URLError as error:
        # This handles connection problems such as
        # missing internet access or an unreachable server.
        raise RuntimeError(
            "Open Library could not be reached."
        ) from error


def fetch_books_by_isbns(isbns):
    """Loads multiple books from the Open Library Search API."""

    # The function expects a non-empty list of ISBN values.
    if not isinstance(isbns, list) or not isbns:
        raise ValueError(
            "A non-empty list of ISBNs is required."
        )

    normalized_isbns = []

    # Every ISBN is normalized with the same function
    # used by the single-book import.
    for isbn in isbns:
        normalized_isbn = select_isbn([isbn])

        if normalized_isbn is None:
            raise ValueError(
                f"Invalid ISBN in batch request: {isbn}"
            )

        # Avoids sending the same ISBN more than once.
        if normalized_isbn not in normalized_isbns:
            normalized_isbns.append(normalized_isbn)

    # This is our own batch-size limit. It keeps requests
    # controlled and prevents excessively long URLs.
    if len(normalized_isbns) > 50:
        raise ValueError(
            "A batch may contain no more than 50 ISBNs."
        )

    # Creates a Solr query such as:
    # isbn:(9780451524935 OR 9780060850524)
    isbn_query = (
        "isbn:("
        + " OR ".join(normalized_isbns)
        + ")"
    )

    # Only requests fields that are useful for our catalog.
    fields = [
        "key",
        "title",
        "author_name",
        "author_key",
        "first_publish_year",
        "isbn",
        "cover_i",
        "first_sentence",
        "editions",
        "editions.key",
        "editions.title",
        "editions.isbn",
        "editions.publish_date",
        "editions.publisher",
        "editions.language",
        "editions.number_of_pages",
        "editions.cover_i"
    ]

    # urlencode() safely converts the query parameters
    # into a correctly encoded URL.
    query_parameters = urlencode({
        "q": isbn_query,
        "fields": ",".join(fields),
        "limit": len(normalized_isbns)
    })

    search_url = (
        f"{OPEN_LIBRARY_BASE_URL}"
        f"/search.json?{query_parameters}"
    )

    response_data = fetch_json(search_url)

    if not isinstance(response_data, dict):
        return []

    search_results = response_data.get("docs", [])

    if not isinstance(search_results, list):
        return []

    return search_results


def convert_to_isbn13(isbn):
    """Returns a normalized ISBN-13 for an ISBN-10 or ISBN-13."""

    normalized_isbn = select_isbn([isbn])

    if normalized_isbn is None:
        return None

    # An ISBN-13 can be returned without conversion.
    if len(normalized_isbn) == 13:
        return normalized_isbn

    # Converts the first nine digits of an ISBN-10
    # into the first twelve digits of an ISBN-13.
    isbn13_without_check_digit = (
        "978"
        + normalized_isbn[:9]
    )

    checksum_total = 0

    # ISBN-13 alternates between the multipliers 1 and 3.
    for position, digit in enumerate(
        isbn13_without_check_digit
    ):
        if position % 2 == 0:
            multiplier = 1
        else:
            multiplier = 3

        checksum_total += int(digit) * multiplier

    check_digit = (
        10 - checksum_total % 10
    ) % 10

    return (
        isbn13_without_check_digit
        + str(check_digit)
    )


def extract_first_integer(value):
    """Returns the first usable integer from a value or list."""

    # bool must be excluded because it is a subclass of int.
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        cleaned_value = value.strip()

        if cleaned_value.isdigit():
            return int(cleaned_value)

        return None

    if isinstance(value, list):
        for item in value:
            extracted_integer = extract_first_integer(item)

            if extracted_integer is not None:
                return extracted_integer

    return None


def find_matching_edition(search_result, requested_isbn):
    """Finds the edition matching the requested ISBN."""

    if not isinstance(search_result, dict):
        return None

    requested_isbn13 = convert_to_isbn13(
        requested_isbn
    )

    if requested_isbn13 is None:
        raise ValueError(
            "A valid requested ISBN is required."
        )

    editions = search_result.get("editions")

    if not isinstance(editions, dict):
        return None

    edition_documents = editions.get("docs", [])

    if not isinstance(edition_documents, list):
        return None

    for edition_document in edition_documents:
        if not isinstance(edition_document, dict):
            continue

        edition_isbns = edition_document.get(
            "isbn",
            []
        )

        if isinstance(edition_isbns, str):
            edition_isbns = [edition_isbns]

        for edition_isbn in edition_isbns:
            edition_isbn13 = convert_to_isbn13(
                edition_isbn
            )

            if edition_isbn13 == requested_isbn13:
                return edition_document

    return None


def find_search_result_by_isbn(
    search_results,
    requested_isbn
):
    """Finds the search result containing the requested edition."""

    if not isinstance(search_results, list):
        return None

    for search_result in search_results:
        matching_edition = find_matching_edition(
            search_result,
            requested_isbn
        )

        if matching_edition is not None:
            return search_result

    return None


def normalize_search_book(
    search_result,
    requested_isbn,
    original_publication_year=None
):
    """Normalizes one book returned by the Search API."""

    if not isinstance(search_result, dict):
        return None

    matching_edition = find_matching_edition(
        search_result,
        requested_isbn
    )

    if matching_edition is None:
        return None

    # Search API author keys do not always contain
    # the complete "/authors/" path.
    author_key = extract_first_text(
        search_result.get("author_key")
    )

    if (
        author_key
        and not author_key.startswith("/authors/")
    ):
        author_key = (
            f"/authors/{author_key.lstrip('/')}"
        )

    # The edition cover is preferred over the general work cover.
    cover_id = (
        extract_cover_id(
            matching_edition.get("cover_i")
        )
        or extract_cover_id(
            search_result.get("cover_i")
        )
    )

    # Our manually checked year has priority.
    if original_publication_year is not None:
        selected_original_publication_year = (
            original_publication_year
        )
    else:
        selected_original_publication_year = (
            extract_first_integer(
                search_result.get(
                    "first_publish_year"
                )
            )
        )

    return {
        # Open Library references
        "edition_key": extract_reference_key(
            matching_edition.get("key")
        ),
        "work_key": extract_reference_key(
            search_result.get("key")
        ),
        "author_key": author_key,

        # Main book information
        "title": (
            extract_first_text(
                matching_edition.get("title")
            )
            or extract_first_text(
                search_result.get("title")
            )
        ),
        "isbn": convert_to_isbn13(
            requested_isbn
        ),
        "publication_year": extract_year(
            matching_edition.get("publish_date")
        ),
        "original_publication_year": (
            selected_original_publication_year
        ),
        "publisher": extract_first_text(
            matching_edition.get("publisher")
        ),
        "language": extract_language(
            matching_edition.get("language")
        ),
        "number_of_pages": extract_first_integer(
            matching_edition.get(
                "number_of_pages"
            )
        ),

        # Author information
        "author_name": extract_first_text(
            search_result.get("author_name")
        ),

        # Cover information
        "cover_id": cover_id,
        "cover_url": build_cover_url(cover_id),

        # The Search API may provide a first sentence,
        # but not always a complete book description.
        "source_description": extract_first_text(
            search_result.get("first_sentence")
        )
    }


def download_cover_image(cover_url, isbn):
    """Downloads a catalog cover and returns its relative static path."""

    # A book without an available cover URL cannot be downloaded.
    if not cover_url:
        return None

    # Normalizes the ISBN so that the generated file name
    # contains no spaces or hyphens.
    cleaned_isbn = select_isbn([isbn])

    if cleaned_isbn is None:
        raise ValueError(
            "A valid ISBN is required for the cover file name."
        )

    # Ensures that the destination directory exists.
    CATALOG_COVER_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    file_name = f"{cleaned_isbn}.jpg"

    absolute_file_path = (
        CATALOG_COVER_DIRECTORY
        / file_name
    )

    relative_file_path = (
        CATALOG_COVER_RELATIVE_DIRECTORY
        / file_name
    )

    # Avoids downloading the same cover repeatedly.
    if absolute_file_path.exists():
        return relative_file_path.as_posix()

    request = Request(
        cover_url,
        headers={
            "User-Agent": OPEN_LIBRARY_USER_AGENT
        }
    )

    try:
        with urlopen(request, timeout=10) as response:
            image_data = response.read()

    except HTTPError as error:
        if error.code == 404:
            return None

        raise RuntimeError(
            f"Open Library returned HTTP error {error.code} "
            "while downloading the cover."
        ) from error

    except URLError as error:
        raise RuntimeError(
            "The Open Library cover could not be downloaded."
        ) from error

    # An empty response should not create an empty image file.
    if not image_data:
        return None

    absolute_file_path.write_bytes(image_data)

    # as_posix() produces a Flask-friendly path with forward slashes.
    return relative_file_path.as_posix()


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

    # A manually supplied and checked publication year has priority.
    # If no year was supplied, the value from the work data is used.
    selected_original_publication_year = (
        original_publication_year
        if original_publication_year is not None
        else work_data.get("original_publication_year")
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
        "original_publication_year": (
            selected_original_publication_year
        ),
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


def fetch_edition_by_isbn(isbn):
    """Loads and normalizes an Open Library edition by ISBN."""

    # Cleans the ISBN and checks whether its structure
    # represents an ISBN-13 or ISBN-10.
    cleaned_isbn = select_isbn([isbn])

    if cleaned_isbn is None:
        raise ValueError(
            "A valid ISBN-13 or ISBN-10 is required."
        )

    edition_url = (
        f"{OPEN_LIBRARY_BASE_URL}"
        f"/isbn/{cleaned_isbn}.json"
    )

    # Requests the concrete edition from Open Library.
    edition_response = fetch_json(edition_url)

    # A missing ISBN record produces no normalized edition.
    if edition_response is None:
        return None

    return normalize_edition_data(edition_response)


def fetch_work_by_key(work_key):
    """Loads and normalizes an Open Library work by its key."""

    # A work key must be a non-empty string.
    if not isinstance(work_key, str):
        raise ValueError(
            "A valid Open Library work key is required."
        )

    cleaned_work_key = work_key.strip()

    # Open Library work references use paths such as:
    # /works/OL1168083W
    if not cleaned_work_key.startswith("/works/"):
        raise ValueError(
            "The Open Library work key must start with '/works/'."
        )

    work_url = (
        f"{OPEN_LIBRARY_BASE_URL}"
        f"{cleaned_work_key}.json"
    )

    # Requests the general work information.
    work_response = fetch_json(work_url)

    if work_response is None:
        return None

    return normalize_work_data(work_response)


def fetch_author_by_key(author_key):
    """Loads and normalizes an Open Library author by its key."""

    # An author key must be a non-empty string.
    if not isinstance(author_key, str):
        raise ValueError(
            "A valid Open Library author key is required."
        )

    cleaned_author_key = author_key.strip()

    # Open Library author references use paths such as:
    # /authors/OL118077A
    if not cleaned_author_key.startswith("/authors/"):
        raise ValueError(
            "The Open Library author key must start with '/authors/'."
        )

    author_url = (
        f"{OPEN_LIBRARY_BASE_URL}"
        f"{cleaned_author_key}.json"
    )

    # Requests the author information.
    author_response = fetch_json(author_url)

    if author_response is None:
        return None

    return normalize_author_data(author_response)