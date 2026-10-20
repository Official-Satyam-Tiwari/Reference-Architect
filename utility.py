import difflib
import urllib.request
import pandas as pd
import bibtexparser

def normalize(text):
    """Aggressively normalizes text for comparison."""
    if not text:
        return ""
    text = str(text).replace("{", "").replace("}", "").replace(".", " ").replace(",", " ").replace("-", " ")
    return " ".join(text.lower().split())

def similarity(a, b):
    """Calculates fuzzy similarity ratio (0.0 to 1.0)."""
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()

def is_title_match(a, b, threshold=0.75):
    """
    Checks if two titles match using fuzzy similarity or substring containment
    (handles subtitles dropped or added in BibTeX).
    """
    if not a or not b:
        return False
    sim = similarity(a, b)
    if sim >= threshold:
        return True
    na = normalize(a)
    nb = normalize(b)
    if len(na) >= 20 and len(nb) >= 20:
        if na in nb or nb in na:
            return True
    return False

def format_source_name(source_code):
    """Converts internal engine codes to clean human-readable names."""
    if not source_code:
        return "Unknown"
        
    mapping = {
        "crossref-doi": "Crossref (DOI)",
        "crossref-title": "Crossref (Search)",
        "crossref-aligned": "Crossref (Aligned)",
        "datacite-doi": "DataCite (DOI)",
        "datacite": "DataCite (Search)",
        "openalex-doi": "OpenAlex (DOI)",
        "openalex": "OpenAlex",
        "semanticscholar-doi": "Semantic Scholar (DOI)",
        "semanticscholar": "Semantic Scholar",
        "pubmed-full": "PubMed",
        "europepmc-doi": "Europe PMC (DOI)",
        "europepmc": "Europe PMC",
        "arxiv": "arXiv (Preprint)",
        "doaj": "DOAJ (Open Access)",
        "hal": "HAL Open Science",
        "zenodo": "Zenodo",
        "inspirehep": "INSPIRE HEP",
        "nasaads": "NASA ADS",
        "opencitations": "OpenCitations",
        "doi2bib": "doi2bib (Crossref)",
        "manual-override": "Manual Override"
    }
    return mapping.get(source_code, str(source_code).title())

def make_bibtex(key, data):
    """Generates a clean BibTeX string from verified canonical data."""
    if not data:
        return ""
    entry_type = "article"
    if "arxiv" in str(data.get("journal", "")).lower() or data.get("arxiv_id"):
        entry_type = "misc"

    bib = f"@{entry_type}{{{key},\n"
    
    fields = [
        ("author", data.get("author")),
        ("title", data.get("title")),
        ("journal", data.get("journal")),
        ("year", data.get("year")),
        ("volume", data.get("volume")),
        ("number", data.get("number")),
        ("pages", data.get("pages")),
        ("doi", data.get("doi")),
        ("eprint", data.get("arxiv_id")),
        ("archivePrefix", "arXiv" if data.get("arxiv_id") else None)
    ]
    
    for field, value in fields:
        if value:
            bib += f"  {field} = {{{value}}},\n"
            
    bib += "}\n"
    return bib

def fetch_canonical_bibtex(key, doi, fallback_clean_data=None):
    """
    Fetches the official publisher BibTeX entry for a verified DOI using doi2bib
    and content negotiation, while preserving the user's original citation key.
    Falls back to make_bibtex(key, fallback_clean_data) if lookup is unavailable.
    """
    if doi:
        clean_doi = doi.replace("https://doi.org/", "").strip()
        # 1. Try doi2bib (uses Crossref content negotiation + journal abbreviations)
        try:
            from doi2bib.crossref import get_bib_from_doi
            found, bib = get_bib_from_doi(clean_doi, abbrev_journal=True)
            if found and bib:
                parsed = bibtexparser.loads(bib)
                if parsed.entries:
                    parsed.entries[0]["ID"] = key
                    return bibtexparser.dumps(parsed).strip()
        except Exception:
            pass

        # 2. Try generic DOI content negotiation (DataCite, Zenodo, etc.)
        try:
            url = f"https://doi.org/{clean_doi}"
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/x-bibtex", "User-Agent": "BiblioAudit/2.2"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    bib_str = resp.read().decode("utf-8", errors="replace")
                    parsed = bibtexparser.loads(bib_str)
                    if parsed.entries:
                        parsed.entries[0]["ID"] = key
                        return bibtexparser.dumps(parsed).strip()
        except Exception:
            pass

    # 3. Fallback to synthesized BibTeX
    return make_bibtex(key, fallback_clean_data).strip()

def check_journal_match(bib_journal, api_journal):
    """Smart check for Journal Abbreviations (e.g., J. Nucl. Med)."""
    if not bib_journal or not api_journal:
        return "missing"
    norm_bib = normalize(bib_journal)
    norm_api = normalize(api_journal)
    
    if difflib.SequenceMatcher(None, norm_bib, norm_api).ratio() > 0.6:
        return "ok"
    
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
            
    if matches >= len(short) * 0.75:
        return "ok"
    return "mismatch"

def check_authors(bib_authors, api_authors):
    """Checks if the first author matches between BibTeX and API."""
    if not bib_authors or not api_authors:
        return False
    first_bib = bib_authors.split(" and ")[0].split(",")[0]
    norm_first = normalize(first_bib)
    
    for auth in api_authors.split(" and "):
        norm_auth = normalize(auth)
        if norm_first in norm_auth or norm_auth in norm_first:
            return True
        if difflib.SequenceMatcher(None, norm_first, norm_auth).ratio() > 0.7:
            return True
    return False

def to_csv(results):
    """Converts verification results to a CSV string for export."""
    if not results:
        return b""
    
    rows = []
    for r in results:
        clean = r.get("clean_data", {})
        row = {
            "Citation Key": r.get("key"),
            "Confidence Score": f"{r.get('confidence', 0)}%",
            "Verification Status": "Verified" if r.get("confidence", 0) >= 90 else "Needs Attention" if r.get("exists") else "Not Found",
            "Source Found": format_source_name(r.get("resolution", "None")),
            "DOI": clean.get("doi") or r.get("verified_doi"),
            "Title": clean.get("title") or r.get("bibtex_title"),
            "Year": clean.get("year") or r.get("bibtex_year"),
            "Journal": clean.get("journal") or r.get("bibtex_journal"),
            "PDF Link": r.get("pdf_link"),
            "ArXiv ID": clean.get("arxiv_id"),
            "Citation Count": clean.get("citation_count")
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode("utf-8")

def compute_feedback_delta(initial_results, fixed_results):
    """
    Computes comparative metrics between the initial audit and the re-audit of the corrected library.
    Evaluates convergence rate, score deltas, and repaired citation details.
    """
    init_map = {r["key"]: r for r in initial_results}
    fixed_map = {r["key"]: r for r in fixed_results}

    total = len(initial_results)
    init_clean = [r for r in initial_results if r.get("confidence", 0) >= 90]
    fixed_clean = [r for r in fixed_results if r.get("confidence", 0) >= 90]
    init_attn = [r for r in initial_results if r.get("exists") and r.get("confidence", 0) < 90]
    fixed_attn = [r for r in fixed_results if r.get("exists") and r.get("confidence", 0) < 90]
    init_miss = [r for r in initial_results if not r.get("exists")]
    fixed_miss = [r for r in fixed_results if not r.get("exists")]

    init_avg_conf = (sum(r.get("confidence", 0) for r in initial_results) / total) if total else 0
    fixed_avg_conf = (sum(r.get("confidence", 0) for r in fixed_results) / total) if total else 0

    repaired = []
    for key, r1 in init_map.items():
        r2 = fixed_map.get(key)
        if not r2:
            continue
        c1 = r1.get("confidence", 0)
        c2 = r2.get("confidence", 0)
        if c2 > c1 or (c1 < 90 and c2 >= 90):
            repaired.append({
                "key": key,
                "before_conf": c1,
                "after_conf": c2,
                "before_status": "Verified" if c1 >= 90 else "Needs Attention" if r1.get("exists") else "Not Found",
                "after_status": "Verified" if c2 >= 90 else "Needs Attention" if r2.get("exists") else "Not Found",
                "before_source": format_source_name(r1.get("resolution")),
                "after_source": format_source_name(r2.get("resolution")),
                "doi": (r2.get("clean_data") or {}).get("doi") or r2.get("verified_doi")
            })

    fixable_count = len(init_attn) + (len(init_miss) - len(fixed_miss))
    repaired_count = len(repaired)
    convergence_pct = (repaired_count / fixable_count * 100) if fixable_count > 0 else 100.0

    return {
        "total": total,
        "initial_clean": len(init_clean),
        "fixed_clean": len(fixed_clean),
        "clean_delta": len(fixed_clean) - len(init_clean),
        "initial_attn": len(init_attn),
        "fixed_attn": len(fixed_attn),
        "attn_delta": len(fixed_attn) - len(init_attn),
        "initial_miss": len(init_miss),
        "fixed_miss": len(fixed_miss),
        "miss_delta": len(fixed_miss) - len(init_miss),
        "initial_avg_conf": init_avg_conf,
        "fixed_avg_conf": fixed_avg_conf,
        "conf_delta": fixed_avg_conf - init_avg_conf,
        "convergence_rate": convergence_pct,
        "repaired": repaired
    }

def print_feedback_report(delta):
    """Prints a structured ASCII report of the feedback loop results."""
    t = delta["total"]
    c1, c2 = delta["initial_clean"], delta["fixed_clean"]
    a1, a2 = delta["initial_attn"], delta["fixed_attn"]
    m1, m2 = delta["initial_miss"], delta["fixed_miss"]
    s1, s2 = delta["initial_avg_conf"], delta["fixed_avg_conf"]

    p_c1 = (c1 / t * 100) if t else 0
    p_c2 = (c2 / t * 100) if t else 0
    p_a1 = (a1 / t * 100) if t else 0
    p_a2 = (a2 / t * 100) if t else 0
    p_m1 = (m1 / t * 100) if t else 0
    p_m2 = (m2 / t * 100) if t else 0

    print("\n" + "=" * 68)
    print("                    CLOSED FEEDBACK LOOP REPORT")
    print("=" * 68)
    print(f"  {'Metric':<26} {'Original Run':<16} {'Re-Audit Run':<16} {'Delta'}")
    print("  " + "-" * 64)
    print(f"  {'Verified Clean (>=90%)':<26} {c1:>3} ({p_c1:5.1f}%)     {c2:>3} ({p_c2:5.1f}%)     {delta['clean_delta']:+d} ({p_c2 - p_c1:+.1f}%)")
    print(f"  {'Needs Attention':<26} {a1:>3} ({p_a1:5.1f}%)     {a2:>3} ({p_a2:5.1f}%)     {delta['attn_delta']:+d} ({p_a2 - p_a1:+.1f}%)")
    print(f"  {'Not Found':<26} {m1:>3} ({p_m1:5.1f}%)     {m2:>3} ({p_m2:5.1f}%)     {delta['miss_delta']:+d} ({p_m2 - p_m1:+.1f}%)")
    print(f"  {'Average Confidence':<26} {s1:5.1f}%          {s2:5.1f}%          {delta['conf_delta']:+.1f}%")
    print(f"  {'Convergence Rate':<26} {delta['convergence_rate']:5.1f}% convergence on repairable citations")
    print("  " + "-" * 64)

    if delta["repaired"]:
        print("\n  [✓] Citations Successfully Repaired & Converged:")
        for item in delta["repaired"]:
            doi_str = f" [DOI: {item['doi']}]" if item.get("doi") else ""
            print(f"      * {item['key']:<22} {item['before_conf']:>3}% ({item['before_status']}) -> {item['after_conf']:>3}% ({item['after_status']}){doi_str}")
    print("=" * 68)

def feedback_to_csv(delta):
    """Exports feedback loop comparison table to CSV."""
    rows = []
    for item in delta["repaired"]:
        rows.append({
            "Citation Key": item["key"],
            "Initial Confidence": f"{item['before_conf']}%",
            "Re-Audit Confidence": f"{item['after_conf']}%",
            "Initial Status": item["before_status"],
            "Re-Audit Status": item["after_status"],
            "Initial Source": item["before_source"],
            "Re-Audit Source": item["after_source"],
            "Verified DOI": item.get("doi")
        })
    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode("utf-8")
