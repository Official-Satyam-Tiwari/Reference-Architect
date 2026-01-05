import aiohttp
import re
import xmltodict
from utils import similarity

# ----------------- PDF ENGINE -----------------
async def fetch_pdf_link(session, doi):
    """Tries to find OA PDF via Unpaywall."""
    if not doi: return None
    clean_doi = doi.replace("https://doi.org/", "").strip()
    try:
        url = f"https://api.unpaywall.org/v2/{clean_doi}?email=agent@streamlit.app"
        async with session.get(url, timeout=3) as r:
            if r.status == 200:
                data = await r.json()
                best_loc = data.get("best_oa_location", {})
                if best_loc and best_loc.get("url_for_pdf"):
                    return best_loc.get("url_for_pdf")
    except: pass
    return None

# ----------------- SEMANTIC SCHOLAR -----------------
async def fetch_semanticscholar(session, title):
    """Fetches metadata from Semantic Scholar Graph API."""
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {"query": title, "limit": 1, "fields": "title,authors,year,venue,externalIds"}
    try:
        async with session.get(url, params=params, timeout=5) as r:
            if r.status == 200:
                data = await r.json()
                if data.get("data"):
                    paper = data["data"][0]
                    if similarity(title, paper.get("title", "")) > 0.8:
                        return {
                            "DOI": paper.get("externalIds", {}).get("DOI"),
                            "title": [paper.get("title")],
                            "issued": {"date-parts": [[paper.get("year")]]} if paper.get("year") else {},
                            "container-title": [paper.get("venue", "")],
                            "author": [{"family": a["name"]} for a in paper.get("authors", [])]
                        }, "semanticscholar"
    except: pass
    return None, None

# ----------------- ARXIV -----------------
async def fetch_arxiv(session, title):
    """Fetches preprints from arXiv API."""
    url = "http://export.arxiv.org/api/query"
    params = {"search_query": f"ti:{title}", "max_results": 1}
    try:
        async with session.get(url, params=params, timeout=5) as r:
            if r.status == 200:
                xml_data = await r.text()
                data = xmltodict.parse(xml_data)
                entry = data.get('feed', {}).get('entry')
                
                # Handle single entry vs list vs None
                if entry:
                    # arXiv ID
                    arxiv_id = entry.get('id', '').split('/abs/')[-1]
                    matched_title = entry.get('title', '').replace('\n', ' ').strip()
                    
                    if similarity(title, matched_title) > 0.8:
                        pub_date = entry.get('published', '')[:4] # YYYY
                        
                        # Handle author list (might be dict or list)
                        authors_raw = entry.get('author')
                        if isinstance(authors_raw, dict): authors_raw = [authors_raw]
                        authors = [{"family": a.get('name')} for a in authors_raw]
                        
                        return {
                            "DOI": entry.get('arxiv:doi', {}).get('#text') if entry.get('arxiv:doi') else None,
                            "arxiv_id": arxiv_id,
                            "title": [matched_title],
                            "issued": {"date-parts": [[int(pub_date)]]} if pub_date.isdigit() else {},
                            "container-title": ["arXiv Preprint"],
                            "author": authors
                        }, "arxiv"
    except: pass
    return None, None

# ----------------- CROSSREF -----------------
async def fetch_crossref(session, doi=None, title=None):
    try:
        if doi:
            url = f"https://api.crossref.org/works/{doi.lower().strip()}"
            async with session.get(url, timeout=5) as r:
                if r.status == 200: return (await r.json())["message"], "crossref-doi"
        if title:
            url = "https://api.crossref.org/works"
            params = {"query.title": title, "rows": 2}
            async with session.get(url, params=params, timeout=5) as r:
                if r.status == 200:
                    data = await r.json()
                    for item in data["message"]["items"]:
                        if similarity(title, item.get("title", [""])[0]) > 0.8:
                            return item, "crossref-title"
    except: pass
    return None, None

# ----------------- OPENALEX -----------------
async def fetch_openalex(session, title):
    url = "https://api.openalex.org/works"
    params = {"filter": f"title.search:{title}", "mailto": "agent@streamlit.app"}
    try:
        async with session.get(url, params=params, timeout=5) as r:
            if r.status == 200:
                data = await r.json()
                results = data.get("results", [])
                if results and similarity(title, results[0].get("display_name", "")) > 0.75:
                    best = results[0]
                    return {
                        "DOI": best.get("doi", "").replace("https://doi.org/", ""),
                        "title": [best.get("display_name")],
                        "issued": {"date-parts": [[best.get("publication_year")]]},
                        "container-title": [best.get("primary_location", {}).get("source", {}).get("display_name", "")],
                        "author": [{"given": a["author"]["display_name"], "family": ""} for a in best.get("authorships", [])],
                        "volume": best.get("biblio", {}).get("volume"),
                        "issue": best.get("biblio", {}).get("issue"),
                        "page": f"{best.get('biblio', {}).get('first_page')}-{best.get('biblio', {}).get('last_page')}" if best.get("biblio", {}).get("first_page") else None
                    }, "openalex"
    except: pass
    return None, None

# ----------------- PUBMED -----------------
async def fetch_pubmed(session, title):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    try:
        async with session.get(f"{base}/esearch.fcgi", params={"db":"pubmed", "term":title, "retmode":"json", "retmax":1}, timeout=5) as r:
            if r.status!=200: return None, None
            data = await r.json()
            ids = data.get("esearchresult", {}).get("idlist", [])
            if not ids: return None, None
            pmid = ids[0]

        async with session.get(f"{base}/esummary.fcgi", params={"db":"pubmed", "id":pmid, "retmode":"json"}, timeout=5) as r:
            if r.status!=200: return None, None
            data = await r.json()
            details = data.get("result", {}).get(pmid, {})
            pub_date = details.get("pubdate", "")
            year = re.search(r'\d{4}', pub_date).group(0) if re.search(r'\d{4}', pub_date) else None
            return {
                "DOI": details.get("elocationid", "").replace("doi: ", "") or f"PMID:{pmid}",
                "title": [details.get("title", "")],
                "issued": {"date-parts": [[int(year)]]} if year else {},
                "container-title": [details.get("source", "")],
                "author": [{"family": a["name"]} for a in details.get("authors", [])],
                "volume": details.get("volume"),
                "issue": details.get("issue"),
                "page": details.get("pages")
            }, "pubmed-full"
    except: pass
    return None, None