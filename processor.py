from utils import similarity, check_authors, check_journal_match
from engines import fetch_crossref, fetch_openalex, fetch_pubmed, fetch_pdf_link

async def process_entry(entry, session, sem):
    """
    Validates a single BibTeX entry against multiple databases.
    """
    key = entry.get("ID")
    
    # 0. Manual Override
    if entry.get("verified", "").lower() == "true":
        return {
            "key": key, "exists": True, "confidence": 100,
            "resolution": "manual-override", "verified_doi": entry.get("doi", "Manual"),
            "doi_url": f"https://doi.org/{entry.get('doi')}" if entry.get('doi') else None,
            "pdf_link": None, "field_check": {}, "clean_data": {}, "warnings": []
        }

    status = {
        "key": key, "exists": False, "verified_doi": None, "doi_url": None, "pdf_link": None,
        "resolution": None, "confidence": 0, "field_check": {}, "clean_data": {}, "warnings": []
    }

    title = entry.get("title")
    doi = entry.get("doi")
    item, source = None, None
    
    # 1. API Lookups (Tiered)
    async with sem:
        item, source = await fetch_crossref(session, doi, title)
        if not item and title: 
            item, source = await fetch_openalex(session, title)
        
        # Crossref Alignment Strategy
        if item and item.get("DOI") and source == "openalex":
             cr_item, cr_source = await fetch_crossref(session, doi=item["DOI"])
             if cr_item: item, source = cr_item, "crossref-aligned"
        
        if not item and title: 
            item, source = await fetch_pubmed(session, title)
            
        # PDF Discovery
        if item and item.get("DOI"): 
            status["pdf_link"] = await fetch_pdf_link(session, item["DOI"])

    if not item: return status

    # 2. Extract Data
    status["exists"] = True
    status["resolution"] = source
    status["verified_doi"] = item.get("DOI")
    
    if status["verified_doi"]:
         status["doi_url"] = f"https://doi.org/{status['verified_doi']}" if "PMID" not in status["verified_doi"] else f"https://pubmed.ncbi.nlm.nih.gov/{status['verified_doi'].replace('PMID:', '')}/"

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

    # Clean Data for Suggestions
    cr_vol = item.get("volume")
    cr_num = item.get("issue") or item.get("journal-issue", {}).get("issue")
    cr_page = item.get("page")

    status["clean_data"] = {
        "title": cr_title, "year": str(cr_year) if cr_year else None,
        "journal": cr_journal, "author": cr_author_str,
        "volume": str(cr_vol) if cr_vol else None,
        "number": str(cr_num) if cr_num else None,
        "pages": str(cr_page) if cr_page else None,
        "doi": status["verified_doi"]
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
    
    if source in ["crossref-doi", "crossref-aligned", "pubmed-full"]:
        status["confidence"] = 100 if score == valid else int((score/valid)*100) if valid else 50
    else:
        status["confidence"] = int((score/valid)*100) if valid else 50
        
    return status