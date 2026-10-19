# IAB207_Ass2

## Running the site

```
python main.py
```

Run it from the project root with the virtual environment active, then open http://127.0.0.1:5000.

By default the site runs with debug mode off, so an error shows the custom 500 page instead of the Werkzeug debugger. Two environment variables change this:

| Variable | Effect |
|---|---|
| `FLASK_DEBUG=1` | Turns debug mode on: the server restarts itself when you save a `.py` or template file, and errors show the interactive debugger. |
| `SECRET_KEY` | Signs session cookies. If it is not set, a random key is generated each time the server starts, so everyone is logged out after a restart. |

For development, set both so saved changes reload automatically and you stay logged in across reloads (PowerShell):

```
$env:FLASK_DEBUG="1"; $env:SECRET_KEY="dev-only-key"; python main.py
```

On macOS or Linux:

```
FLASK_DEBUG=1 SECRET_KEY=dev-only-key python main.py
```

Leave `FLASK_DEBUG` unset when checking the error pages: the custom 500 page only appears with debug mode off. Never use `dev-only-key` outside your own machine.

## Demo data

Load demo users, events, bookings and comments with:

```
python seed_db.py
```

Run it from the project root with the virtual environment active.

**Warning:** this drops every table first, so any accounts or bookings you created by hand are lost.

### Test users

All test users have the password `password123`.

| Email | Notes |
|---|---|
| `ruth@example.com` | Created every event |
| `dev@example.com` | Has four bookings |
| `marta@example.com` | Has one booking |

## AI vibe search

The landing page search box has a second button, **AI vibe search**. Instead of matching keywords, it compares the meaning of what you type (e.g. "chill acoustic night") with each upcoming gig and shows up to three AI picks above the listing, each with its match score. Cancelled and finished gigs are never recommended, and an active genre chip still applies.

It uses [`sentence-transformers`](https://www.sbert.net/) with the `sentence-transformers/all-MiniLM-L6-v2` model and cosine similarity. No other AI library is used. The code is in `website/ai_search.py`.

The first AI search after the server starts downloads the model (about 90 MB), so it needs an internet connection once and can take a minute. After that the model is cached on disk and searches take a fraction of a second. If the model cannot be loaded, the page says AI search is unavailable and shows all gigs; the rest of the site works without it.

After pulling this change, run both of these with the virtual environment active:

```
pip install -r requirements.txt
python seed_db.py
```

The seed adds three Open gigs (Lantern Hours, Southside Cypher and Saltwater Matinee) so vibe search has something to find. `pip install` is a large download because sentence-transformers brings in PyTorch.
