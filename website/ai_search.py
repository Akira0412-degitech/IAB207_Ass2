"""US4 - semantic "vibe search" for the landing page.

Keyword search (US3) only finds a gig when the visitor types part of its
title, venue or lineup. This module lets them describe the night they want
instead ("chill acoustic night") and ranks gigs by meaning, using a
sentence embedding of each gig and cosine similarity against the query.

All AI logic lives here so views.py only has to call semantic_search() and
handle AISearchUnavailable. The assignment brief allows sentence-transformers,
huggingface_hub and the OpenAI API only, so nothing else is imported, and
torch is used solely through sentence-transformers itself.
"""

import hashlib
import threading
import time

from flask import current_app

# The model the unit recommends. Small (about 90 MB) and fast enough to embed
# every gig on a laptop CPU, which is all the marker is guaranteed to have.
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'

# Tuned against the seeded gigs by scoring every gig for five real queries
# and two off-topic ones (full table in the PR for #18). MiniLM scores for
# related music text sit in a narrow band, so the threshold is a floor that
# rejects off-topic queries, not a measure of a good match: the ranking does
# that. Off-topic queries ("cheap flights to paris", "asdkjh qwe") peaked at
# 0.18, and the weakest correct top pick was a one-word query ("rap") at
# 0.30. 0.25 sits in that gap with room on both sides.
SIMILARITY_THRESHOLD = 0.25

# Three picks fit one row of cards on desktop, and a visitor asking for a
# vibe wants a short shortlist, not a second copy of the whole listing.
TOP_N = 3

# Embedding cost grows with input length and the model truncates long input
# anyway, so a pasted essay is cut down rather than slowing the page.
MAX_QUERY_LENGTH = 200

# After a failed load (e.g. no internet on the first run) wait this long
# before trying again, so every landing page visit does not sit through
# another download attempt and its network timeout.
RETRY_AFTER_SECONDS = 60

# Lazy loading: importing sentence_transformers pulls in torch, which takes
# several seconds, and the first load downloads the model. Doing either at
# import time or in create_app() would slow every page and seed_db.py, and
# would stop the whole site starting when the model is unavailable. So the
# model is loaded on the first AI search only, then kept for the process.
_model = None
_load_failed_at = None
# The dev server is threaded; the lock stops two simultaneous first searches
# from both loading a copy of the model.
_model_lock = threading.Lock()

# {event_id: (text_fingerprint, embedding)}. Kept in memory rather than in a
# database column because an embedding is derived data, tied to one model
# version, and cheap to rebuild for a site this size. A column would need a
# models.py change and a re-seed every time the model or event_text() changes.
_embedding_cache = {}


class AISearchUnavailable(Exception):
    """Raised when the model cannot be loaded or used.

    views.py catches this and shows a calm message with the normal listing,
    so a missing package or a failed download never becomes a 500.
    """


def _get_model():
    """Return the sentence-transformers model, loading it on first use."""
    global _model, _load_failed_at

    if _model is not None:
        return _model

    with _model_lock:
        # Another thread may have finished loading while this one waited.
        if _model is not None:
            return _model
        if (_load_failed_at is not None
                and time.monotonic() - _load_failed_at < RETRY_AFTER_SECONDS):
            raise AISearchUnavailable('model load failed recently')
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(MODEL_NAME)
        except Exception as exc:
            # ImportError when the package is missing, OSError or an HTTP
            # error when the download fails. Either way the site carries on.
            _load_failed_at = time.monotonic()
            current_app.logger.warning(
                'AI search unavailable, could not load %s: %s', MODEL_NAME, exc)
            raise AISearchUnavailable(str(exc)) from exc
        _load_failed_at = None
        return _model


# A bare label like 'Hip-Hop / R&B' scored lower for "rap" than a rock gig
# did when tuning, because a promoter's description rarely names its own
# genre. Spelling each genre out in plain words gives the model the
# vocabulary visitors actually use. Keys match forms.GENRES.
GENRE_PHRASES = {
    'Rock / Punk': 'Rock and punk: guitar bands, fast, raw and loud',
    'Metal / Heavy': 'Metal and heavy music: loud, distorted guitars, mosh pits',
    'Electronic': 'Electronic and dance music: DJs, synths, beats, a dance floor',
    'Hip-Hop / R&B': 'Hip-hop, rap and R&B: MCs, beats and soul singers',
    'Jazz / Blues': 'Jazz and blues: horns, upright bass, swing and improvised solos',
    'Folk / Acoustic': ('Folk and acoustic music: singer-songwriters, quiet, '
                        'mellow and unplugged'),
}

# '18+' and '15+' mean little to the model on their own, so each restriction
# is spelled out in the words a visitor would actually search with.
AGE_PHRASES = {
    'All ages': 'All ages, family friendly, kids and teenagers welcome',
    '15+': '15 and over, teenagers 15+ welcome',
    '18+': '18+ only, adults over 18, licensed venue',
}


def event_text(event):
    """Build the text that stands for one gig when it is embedded.

    Each part is there because a visitor might describe the gig by it.
    """
    parts = [
        # The title is often the headline act and carries the gig's name.
        event.title,
        # Genre is the strongest signal for short queries like "acoustic" or
        # "rap", which rarely appear in a description written by a promoter.
        GENRE_PHRASES.get(event.genre, 'Genre: {}'.format(event.genre)),
        # The description carries the mood words: candlelit, loud, seated...
        event.description,
    ]

    # Support slots are optional, so only acts that exist are listed.
    lineup = [a for a in (event.artist_1, event.artist_2, event.artist_3) if a]
    if lineup:
        parts.append('Lineup: {}'.format(', '.join(lineup)))

    # Venue and suburb let "something in the Valley" or "Burleigh" work.
    # Only the suburb, the last part of the address, is used: street numbers
    # and names are noise to the model, and including them lowered the
    # right gig's score for most test queries.
    venue = event.venue_name
    if event.venue_address:
        suburb = event.venue_address.rsplit(',', 1)[-1].strip()
        venue = '{}, {}'.format(venue, suburb)
    parts.append('Venue: {}'.format(venue))

    # Age restriction makes "all ages" or "bring my teenager" queries work.
    parts.append(AGE_PHRASES.get(event.age_restriction, event.age_restriction))

    # Descriptions usually end in a full stop already; strip it so the
    # joined sentences do not end up with "..".
    return '. '.join(part.strip().rstrip('.') for part in parts)


def _fingerprint(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _event_embeddings(model, events):
    """Return one embedding per event, recomputing only those whose text changed.

    Comparing a hash of event_text() rather than an updated-at time means an
    edited gig, a new gig, or a change to event_text() itself is all picked
    up automatically, with no extra column on Event.
    """
    texts = {event.id: event_text(event) for event in events}
    stale = [event.id for event in events
             if _embedding_cache.get(event.id, (None,))[0]
             != _fingerprint(texts[event.id])]

    if stale:
        # One batched encode is much faster than one call per gig. Each row is
        # stored as a plain list of floats so the cache holds no torch or
        # numpy objects, and util.cos_sim accepts a list of them directly.
        vectors = model.encode([texts[i] for i in stale])
        for event_id, vector in zip(stale, vectors):
            _embedding_cache[event_id] = (_fingerprint(texts[event_id]),
                                          vector.tolist())

    return [_embedding_cache[event.id][1] for event in events]


def semantic_search(query, events):
    """US4 - rank events by how closely they match the meaning of query.

    Returns a list of (event, score) pairs, best first: at most TOP_N, and
    only those scoring at least SIMILARITY_THRESHOLD, so an empty list means
    "nothing matches that vibe". Raises AISearchUnavailable if the model
    cannot be loaded or used.
    """
    query = (query or '').strip()[:MAX_QUERY_LENGTH]
    if not query or not events:
        return []

    model = _get_model()

    try:
        from sentence_transformers import util

        query_vector = model.encode(query).tolist()
        event_vectors = _event_embeddings(model, events)
        # cos_sim returns a 1 x len(events) matrix; row 0 is this query.
        scores = util.cos_sim([query_vector], event_vectors)[0].tolist()
    except Exception as exc:
        # Encoding should not fail once the model has loaded, but if it ever
        # does the visitor still gets the normal listing rather than a 500.
        current_app.logger.warning('AI search failed for %r: %s', query, exc)
        raise AISearchUnavailable(str(exc)) from exc

    matches = [(event, score) for event, score in zip(events, scores)
               if score >= SIMILARITY_THRESHOLD]
    matches.sort(key=lambda pair: pair[1], reverse=True)
    return matches[:TOP_N]
