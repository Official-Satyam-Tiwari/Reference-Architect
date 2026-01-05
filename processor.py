from utils import similarity, check_authors, check_journal_match
from engines import fetch_crossref, fetch_openalex, fetch_pubmed, fetch_pdf_link, fetch_semanticscholar, fetch_arxiv

async def process_entry(entry, session, sem):
    """
    Validates a single BibTeX entry against 5 databases.
    """
    key = entry.get("ID")
    
    if entry.get("verified", "").lower() == "true":
        return {
            "key": key, "exists": True, "confidence": 100,
            "resolution": "manual-override", "verified_doi": entry.get("doi", "Manual"),
            "doi_url": f"https://doi.org/{entry.get('doi')}" if entry.get('doi') else None,
            "pdf_link": None, "field_check": {}, "clean_data": {}, "warnings": []
        }

    # Store original data
    bibtex_title = entry.get("title", "")
    bibtex_year = entry.get("year", "")
    bibtex_journal = entry.get("journal", "")
    bibtex_author_raw = entry.get("author", "")

    status = {
        "key": key,
        "bibtex_title": bibtex_title, 
        "bibtex_year": bibtex_year,   
        "bibtex_journal": bibtex_journal,
        "exists": False, "verified_doi": None, "doi_url": None, "pdf_link": None,
        "resolution": None, "confidence": 0, "field_check": {}, "clean_data": {}, "warnings": []
    }

    title = entry.get("title")
    doi = entry.get("doi")
    
    # Extract First Author Last Name (e.g., "Vaswani" from "Vaswani, Ashish and...")
    first_author_lastname = None
    if bibtex_author_raw:
        # Split by 'and' to get first author, then split by comma/space
        first_author = bibtex_author_raw.split(" and ")[0].strip()
        if "," in first_author:
            first_author_lastname = first_author.split(",")[0].strip()
        else:
            first_author_lastname = first_author.split(" ")[-1].strip()
    
    item, source = None, None
    
    # 1. API Lookups
    async with sem:
        # A. Priority 1: Crossref DOI (Exact Match)
        if doi:
            item, source = await fetch_crossref(session, doi=doi)
        
        # B. Priority 2: Semantic Scholar (Title + Author)
        if not item and title:
            item, source = await fetch_semanticscholar(session, title, first_author_lastname)

        # C. Priority 3: OpenAlex (Title + Author)
        if not item and title: 
            item, source = await fetch_openalex(session, title, first_author_lastname)
            
        # D. Priority 4: arXiv (Title + Author)
        if not item and title:
            item, source = await fetch_arxiv(session, title, first_author_lastname)
        
        # E. Priority 5: Crossref Search (Title + Author)
        if not item and title:
            item, source = await fetch_crossref(session, title=title, author=first_author_lastname)
        
        # F. Priority 6: PubMed (Medical Specific)
        if not item and title: 
            item, source = await fetch_pubmed(session, title, first_author_lastname)

        # Crossref Alignment
        if item and item.get("DOI") and source in ["openalex", "semanticscholar"]:
             cr_item, cr_source = await fetch_crossref(session, doi=item["DOI"])
             if cr_item: item, source = cr_item, "crossref-aligned"
        
        # PDF Discovery
        if item and item.get("DOI"): 
            status["pdf_link"] = await fetch_pdf_link(session, item["DOI"])

    if not item: return status

    # 2. Extract Data
    status["exists"] = True
    status["resolution"] = source
    status["verified_doi"] = item.get("DOI")
    status["arxiv_id"] = item.get("arxiv_id")
    
    # Link Generation
    if status["verified_doi"]:
         status["doi_url"] = f"https://doi.org/{status['verified_doi']}" if "PMID" not in status["verified_doi"] else f"https://pubmed.ncbi.nlm.nih.gov/{status['verified_doi'].replace('PMID:', '')}/"
    elif status["arxiv_id"]:
         status["doi_url"] = f"https://arxiv.org/abs/{status['arxiv_id']}"

    # Canonical Data Extraction
    cr_title = item.get("title", [""])[0]
    date_parts = item.get("issued", {}).get("date-parts", [[None]])
    cr_year = date_parts[0][0] if date_parts else None
    cr_journal = item.get("container-title", [""])[0]
    
    cr_authors = []
    if "author" in item:
        for a in item["author"]:
            f, g = a.get("family", ""), a.get("given", "")
            cr_authors.append(f"{f}, {g}" if f and g else f)
    cr_author_str = " and ".join(cr_authors)

    cr_vol = item.get("volume")
    cr_num = item.get("issue") or item.get("journal-issue", {}).get("issue")
    cr_page = item.get("page")

    status["clean_data"] = {
        "title": cr_title, "year": str(cr_year) if cr_year else None,
        "journal": cr_journal, "author": cr_author_str,
        "volume": str(cr_vol) if cr_vol else None,
        "number": str(cr_num) if cr_num else None,
        "pages": str(cr_page) if cr_page else None,
        "doi": status["verified_doi"],
        "arxiv_id": status["arxiv_id"]
    }

    # 3. Verification Logic
    year_status = "mismatch"
    bib_year = entry.get("year")
    if str(bib_year) == str(cr_year): year_status = "ok"
    elif bib_year and cr_year:
        try:
            if abs(int(bib_year) - int(cr_year)) <= 1: year_status = "ok"
        except: pass

    journal_status = check_journal_match(entry.get("journal"), cr_journal)
    auth_status = "ok" if check_authors(entry.get("author"), cr_author_str) else "mismatch"

    status["field_check"] = {
        "title": {"bibtex": title, "correct": cr_title, "status": "ok" if similarity(title, cr_title) > 0.75 else "mismatch"},
        "year": {"bibtex": bib_year, "correct": cr_year, "status": year_status},
        "journal": {"bibtex": entry.get("journal"), "correct": cr_journal, "status": journal_status},
        "author": {"bibtex": entry.get("author"), "correct": cr_author_str, "status": auth_status}
    }
    
    # 4. Scoring
    score = sum(1 for v in status["field_check"].values() if v["status"] == "ok")
    valid = sum(1 for v in status["field_check"].values() if v["bibtex"])
    
    trusted = ["crossref-doi", "crossref-aligned", "pubmed-full", "arxiv", "semanticscholar"]
    
    if source in trusted:
        status["confidence"] = 100 if score == valid else int((score/valid)*100) if valid else 50
    else:
        status["confidence"] = int((score/valid)*100) if valid else 50
        
    return status