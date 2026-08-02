# Book Alchemy

Book Alchemy is a Flask-based personal library and book discovery application.

The project combines a traditional personal book collection with a curated local catalog of 200 books. Users can browse, search, and sort the catalog, add selected books to their personal library, manually create authors and books, and remove books without changing the original discovery catalog.

The interface combines a responsive modern layout with the visual character of an old literature forum: floral wallpaper, dark translucent book cards, brass details, warm typography, and a deliberately nostalgic atmosphere.

![Book Alchemy catalog](docs/screenshots/catalog-desktop.png)

## Features

### Personal Library

- Display books stored in the personal library
- Search books by title
- Sort books by title or author
- Add books manually
- Add authors manually
- Remove books from the personal library
- Automatically remove an author when no personal books reference that author
- Display local covers or a default cover when no image is available

### Discovery Catalog

- Curated catalog containing 200 books
- Eight categories with 25 books each
- Search by title or author
- Sort by title, author, or category
- Add catalog books to the personal library
- Prevent duplicate editions or works from being added
- Preserve the original catalog entry when a personal copy is removed

### Catalog Categories

- AI & Data Science
- Biography
- Classics
- Fantasy
- Non-Fiction
- Science Fiction
- Software Development
- Thriller & Mystery

### Data Integration

- Book metadata retrieved from Open Library
- Batch-based catalog import
- Detailed single-book API fallback for incomplete batch results
- Local cover downloads
- Reproducible catalog corrections for unsuitable edition titles and author names
- Separate storage for imported source descriptions and future normalized summaries

### Interface

- Responsive desktop and mobile layout
- Fixed floral wallpaper background
- Modern-vintage card design
- Responsive CSS Grid
- Shared navigation across all pages
- Accessible form labels and image alternative text
- Lazy-loaded catalog covers
- Local default cover for missing images

## Technologies

- Python
- Flask
- Flask-SQLAlchemy
- SQLAlchemy
- SQLite
- Jinja2
- HTML
- CSS
- Open Library API

## Project Structure

```text
book-alchemy-de/
├── app.py
├── data_models.py
├── init_database.py
├── open_library_service.py
├── seed_catalog.py
├── apply_catalog_overrides.py
├── catalog_seed_data.json
├── catalog_overrides.json
├── data/
│   └── library.sqlite
├── docs/
│   └── screenshots/
│       └── catalog-desktop.png
├── static/
│   ├── covers/
│   │   ├── catalog/
│   │   └── default-cover.svg
│   ├── css/
│   │   └── style.css
│   └── images/
│       └── book-alchemy-wallpaper.jpeg
└── templates/
    ├── home.html
    ├── catalog.html
    ├── add_book.html
    └── add_author.html
```

The SQLite database and downloaded catalog covers are generated locally and are intentionally excluded from version control.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/DanielMS616/book-alchemy.git
cd book-alchemy
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

### 3. Install the dependencies

```bash
python -m pip install -r requirements.txt
```

## Database Setup

Create the SQLite database and all required tables:

```bash
python init_database.py
```

Expected output:

```text
Database initialization completed.
Database tables are ready.
```

The initialization script only creates missing tables. Existing tables and their data are not deleted.

## Import the Discovery Catalog

Import the curated 200-book catalog:

```bash
python seed_catalog.py
```

The importer:

1. Loads and validates `catalog_seed_data.json`
2. Retrieves books through the Open Library API
3. Processes multiple ISBNs in batches
4. Uses detailed single-book requests as a fallback
5. Prevents duplicate catalog entries
6. Downloads available covers locally
7. Stores the catalog records in SQLite

After the import, apply the curated display corrections:

```bash
python apply_catalog_overrides.py
```

The override script normalizes a small number of unsuitable edition titles and author names while preserving their ISBNs and Open Library references.

## Run the Application

Start the Flask development server:

```bash
flask --app app run --debug
```

Open the application in a browser:

```text
http://127.0.0.1:5000
```

If port `5000` is already in use, start the application on another port:

```bash
flask --app app run --debug --port=5001
```

Then open:

```text
http://127.0.0.1:5001
```

## Application Pages

| Route | Purpose |
|---|---|
| `/` | Display and search the personal library |
| `/catalog` | Browse and search the discovery catalog |
| `/add_author` | Create a new author |
| `/add_book` | Add a book manually |
| `/book/<id>/delete` | Remove a book from the personal library |
| `/catalog/<id>/add` | Add a catalog book to the personal library |

Routes that modify a collection use `POST` requests.

## Rebuilding the Local Database

A fresh local setup can be reproduced with:

```bash
python init_database.py
python seed_catalog.py
python apply_catalog_overrides.py
```

The catalog importer is idempotent. Running it again skips existing entries instead of creating duplicates.

## Usage

### Browse the Catalog

Open the **Book Catalog** page to browse the complete local collection.

The catalog can be:

- searched by title or author
- sorted by title
- sorted by author
- sorted by category

Each catalog card contains an **Add to My Library** button.

### Manage the Personal Library

The **My Library** page contains books selected from the discovery catalog or added manually.

Personal books can be:

- searched by title
- sorted by title
- sorted by author
- removed from the personal library

Removing a personal book does not remove the corresponding entry from the discovery catalog. The book remains available and can be added again later.

### Add Authors and Books Manually

A manually entered book must reference an existing author.

The normal workflow is therefore:

1. Open **Add Author**
2. Create the author
3. Open **Add Book**
4. Select the author from the dropdown
5. Enter the book information

## Design Decisions

### Separate Catalog and Personal Library

`CatalogBook` represents a book available for discovery.

`Book` represents a book selected for the personal library.

This separation makes it possible to remove a personal book without changing the curated discovery catalog.

```text
CatalogBook
→ remains available in the catalog

Book
→ belongs to the personal library
→ can be added or removed independently
```

### Duplicate Prevention

Before a catalog book is copied into the personal library, the application checks stable Open Library identifiers and the ISBN.

This prevents the same work or edition from being added repeatedly.

### Local Cover Storage

Available Open Library covers are downloaded into the local static directory.

This:

- reduces repeated external requests
- improves loading reliability
- keeps previously downloaded covers available locally

Books without an individual cover use the local Book Alchemy default cover.

### Batch Import with Fallback

The Search API is used to retrieve several books with fewer requests.

Search results can occasionally omit the exact requested edition. In that case, the importer uses detailed edition, work, and author endpoints as a slower but more reliable fallback.

### Reproducible Catalog Corrections

Open Library contains many:

- translations
- adapted editions
- learner editions
- collections
- alternative titles
- catalog-style author names

The version-controlled `catalog_overrides.json` file contains a small number of curated display corrections.

The corrections can be reapplied after every fresh catalog import:

```bash
python apply_catalog_overrides.py
```

### Modern-Vintage Interface

The interface combines:

- a fixed floral wallpaper
- dark translucent panels
- warm orange typography
- brass-colored borders
- paper-colored form elements
- responsive modern layouts

The visual goal is a lovingly maintained old literature forum presented through a usable modern interface.

## Known Limitations

- The application currently supports one local user
- There is no authentication or account management
- Personal library data is stored only in the local SQLite database
- The catalog uses selected editions rather than every available edition
- Some optional metadata fields may be unavailable
- The project does not currently include pagination
- Manually added books do not automatically download cover images
- Some imported source descriptions are incomplete
- The catalog is intentionally curated instead of being dynamically unlimited

## Future Improvements

### Adaptive AI Book Recommendations

A lightweight recommendation assistant could ask three adaptive questions.

Each question would use the previous answers to narrow the reader's interests before recommending books exclusively from the local catalog.

Example flow:

```text
Question 1
→ first answer

Question 2 uses the first answer
→ second answer

Question 3 uses both previous answers
→ third answer

Three validated catalog recommendations
```

The questions should be:

- variable
- creative
- humorous
- based on the available catalog
- increasingly specific
- designed to discover the reader's interests efficiently

Planned safeguards:

- Only existing `CatalogBook` IDs may be recommended
- Python validates all model-generated IDs
- Titles, authors, covers, and metadata always come from the database
- The language model only generates questions and recommendation explanations
- Invalid or unknown IDs are rejected
- Missing factual information must not be invented

### AI Provider Architecture

The first experimental provider could use the Gemini API.

A later provider could use Ollama with a local open-weight model such as Qwen.

```text
RecommendationProvider
├── GeminiProvider
└── OllamaProvider
```

This architecture would make it possible to change providers without rewriting the complete recommendation workflow.

### Local Ollama Provider

Ollama could run locally on the user's computer and expose a local HTTP API.

The Flask application would send prompts and structured catalog information to Ollama. A locally installed model would then generate the questions and recommendation explanations.

Possible benefits:

- local processing
- no dependency on one cloud provider
- no API costs for local inference
- improved privacy
- reproducible model configuration

### Optional Reader Memory

Users could choose between:

- recommendations based only on the current three answers
- recommendations that also consider previous sessions and explicit reading preferences

Stored preferences should remain:

- transparent
- editable
- removable
- controlled by the user

The application should store concrete preference signals rather than unsupported personality diagnoses.

### Wikipedia and Wikidata Enrichment

Wikipedia and Wikidata could provide additional source-grounded information for each book.

Possible data:

- verified work descriptions
- author references
- publication information
- themes
- unique identifiers

The application would cache this information locally before using it to create structured book profiles.

### Source-Grounded Book Profiles

Future catalog entries could contain normalized recommendation information such as:

```text
spoiler-free summary
themes
mood
pace
complexity
humor
character focus
idea focus
recommended reading situation
```

Generated fields should always be derived from stored sources. Unsupported fields should remain empty instead of being invented.

### Additional Improvements

- Book detail pages
- Favorites
- Reading status
- Personal notes
- Recommendation feedback
- Category filters
- Pagination
- Catalog administration
- More curated books
- Improved edition selection
- Automated tests
- User accounts
- Multiple personal libraries

## Learning Outcomes

This project demonstrates:

- Flask application setup
- Flask routing
- GET and POST requests
- HTML forms
- Flash messages
- Post/Redirect/Get workflows
- SQLAlchemy models
- Database relationships
- SQLite database management
- Jinja template rendering
- Search queries
- Sorting queries
- SQL `LIKE` filters
- External API integration
- JSON configuration files
- JSON validation
- Batch processing
- API fallback strategies
- Local file handling
- Cover downloads
- Duplicate prevention
- Reproducible data corrections
- Responsive CSS Grid layouts
- Separation between imported data and personal application data
- Project setup documentation
- Git-based development workflows

## Acknowledgements

Book metadata and cover references are provided by the Open Library API.

The project was developed as part of the Masterschool Software Engineering curriculum.