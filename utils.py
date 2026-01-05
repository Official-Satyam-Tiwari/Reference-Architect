import difflib
import pandas as pd

def normalize(text):
    """Aggressively normalizes text for comparison."""
    if not text: return ""
    text = str(text).replace("{", "").replace("}", "").replace(".", " ").replace(",", " ").replace("-", " ")
    return " ".join(text.lower().split())

def similarity(a, b):
    """Calculates fuzzy similarity ratio (0.0 to 1.0)."""
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()

def format_source_name(source_code):
    """Converts internal codes to readable names."""
    if not source_code:
        return "Unknown"  # <-- Handle None safely
        
    mapping = {
        "crossref-doi": "Crossref (DOI)",
        "crossref-title": "Crossref (Search)",
        "openalex": "OpenAlex",
        "pubmed-full": "PubMed",
        "arxiv": "arXiv (Preprint)",
        "semanticscholar": "Semantic Scholar"
    }
    return mapping.get(source_code, str(source_code).title())

def make_bibtex(key, data):
    """Generates a clean BibTeX string from verified data."""
    if not data: return ""
    entry_type = "article"
    if "arxiv" in str(data.get('journal', '')).lower():
        entry_type = "misc"

    bib = f"@{entry_type}{{{key},\n"
    
    fields = [
        ('author', data.get('author')),
        ('title', data.get('title')),
        ('journal', data.get('journal')),
        ('year', data.get('year')),
        ('volume', data.get('volume')),
        ('number', data.get('number')),
        ('pages', data.get('pages')),
        ('doi', data.get('doi')),
        ('eprint', data.get('arxiv_id')),
        ('archivePrefix', 'arXiv' if data.get('arxiv_id') else None)
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
    
    if difflib.SequenceMatcher(None, norm_bib, norm_api).ratio() > 0.6: return "ok"
    
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

def to_csv(results):
    """Converts verification results to a CSV string for export."""
    if not results: return ""
    
    rows = []
    for r in results:
        clean = r.get("clean_data", {})
        # --- FIX 2: Fallback Logic ---
        # If 'clean' (API data) is empty, use 'bibtex_*' (Original)
        row = {
            "Citation Key": r.get("key"),
            "Confidence Score": f"{r['confidence']}%",
            "Verification Status": "Verified" if r["confidence"] >= 90 else "Needs Attention" if r["exists"] else "Not Found",
            "Source Found": format_source_name(r.get("resolution", "None")),
            "DOI": clean.get("doi") or r.get("verified_doi"),
            "Title": clean.get("title") or r.get("bibtex_title"),
            "Year": clean.get("year") or r.get("bibtex_year"),
            "Journal": clean.get("journal") or r.get("bibtex_journal"),
            "PDF Link": r.get("pdf_link"),
            "ArXiv ID": clean.get("arxiv_id")
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode('utf-8')