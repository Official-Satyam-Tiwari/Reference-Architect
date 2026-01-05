import aiohttp
import re
from utils import similarity

async def fetch_pdf_link(session, doi):
    """Tries to find an Open Access PDF using Unpaywall."""
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

async def fetch_crossref(session, doi=None, title=None):
    """Fetches metadata from Crossref."""
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

async def fetch_openalex(session, title):
    """Fetches metadata from OpenAlex."""
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

async def fetch_pubmed(session, title):
    """Fetches metadata from PubMed (E-Utils)."""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    try:
        # Step 1: Search for ID
        async with session.get(f"{base}/esearch.fcgi", params={"db":"pubmed", "term":title, "retmode":"json", "retmax":1}, timeout=5) as r:
            if r.status!=200: return None, None
            data = await r.json()
            ids = data.get("esearchresult", {}).get("idlist", [])
            if not ids: return None, None
            pmid = ids[0]

        # Step 2: Fetch Details
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