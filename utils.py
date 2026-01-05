import difflib

def normalize(text):
    """Aggressively normalizes text for comparison."""
    if not text: return ""
    # Remove braces, punctuation, extra spaces
    text = str(text).replace("{", "").replace("}", "").replace(".", " ").replace(",", " ").replace("-", " ")
    return " ".join(text.lower().split())

def similarity(a, b):
    """Calculates fuzzy similarity ratio between two strings (0.0 to 1.0)."""
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()

def format_source_name(source_code):
    """Converts internal codes to readable names."""
    if not source_code: return "Unknown"
    return source_code.replace("-", " ").replace("id", "ID").title()

def make_bibtex(key, data):
    """Generates a clean BibTeX string from verified data."""
    if not data: return ""
    bib = f"@article{{{key},\n"
    
    fields = [
        ('author', data.get('author')),
        ('title', data.get('title')),
        ('journal', data.get('journal')),
        ('year', data.get('year')),
        ('volume', data.get('volume')),
        ('number', data.get('number')),
        ('pages', data.get('pages')),
        ('doi', data.get('doi'))
    ]
    
    for field, value in fields:
        if value:
            bib += f"  {field} = {{{value}}},\n"
            
    bib += "}"
    return bib

def check_journal_match(bib_journal, api_journal):
    """Smart check for Journal Abbreviations (e.g., J. Nucl. Med)."""
    if not bib_journal or not api_journal: return "missing"
    norm_bib = normalize(bib_journal)
    norm_api = normalize(api_journal)
    
    # 1. Direct fuzzy match
    if difflib.SequenceMatcher(None, norm_bib, norm_api).ratio() > 0.6: return "ok"
    
    # 2. Abbreviation Heuristic
    tokens_bib = norm_bib.split()
    tokens_api = norm_api.split()
    short, long = (tokens_bib, tokens_api) if len(tokens_bib) < len(tokens_api) else (tokens_api, tokens_bib)
    
    matches = 0
    long_idx = 0
    for token in short:
        while long_idx < len(long):
            if long[long_idx].startswith(token):
                matches += 1
                long_idx += 1
                break
            long_idx += 1
            
    if matches >= len(short) * 0.75: return "ok"
    return "mismatch"

def check_authors(bib_authors, api_authors):
    """Checks if the first author exists in the API list."""
    if not bib_authors or not api_authors: return False
    first_bib = bib_authors.split(" and ")[0].split(",")[0]
    norm_first = normalize(first_bib)
    
    for auth in api_authors.split(" and "):
        norm_auth = normalize(auth)
        if norm_first in norm_auth or norm_auth in norm_first: return True
        if difflib.SequenceMatcher(None, norm_first, norm_auth).ratio() > 0.7: return True
    return False