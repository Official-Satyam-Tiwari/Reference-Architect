#!/usr/bin/env python3
"""
BiblioAudit
Automated Reference Integrity & Verification System
Single-file engine that cross-verifies citations against 12+ major academic databases.
Uses utility.py for supporting functions.
"""

import sys
import os
import re
import time
import argparse
import asyncio
import aiohttp
import xmltodict
import urllib.parse
from pathlib import Path
import bibtexparser
from bibtexparser.bparser import BibTexParser

from utility import (
    similarity,
    is_title_match,
    format_source_name,
    make_bibtex,
    fetch_canonical_bibtex,
    to_csv,
    check_authors,
    check_journal_match,
    compute_feedback_delta,
    print_feedback_report,
    feedback_to_csv
)

# UTF-8 terminal configuration for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

VERSION = "2.2.2"
USER_AGENT = "BiblioAudit/2.2 (https://github.com/Official-Satyam-Tiwari/reference-architect; mailto:agent@biblioaudit.org)"
DEFAULT_HEADERS = {"User-Agent": USER_AGENT}

DATABASES = [
    "Crossref (Universal DOIs & Publisher Catalog)",
    "DataCite (Zenodo, Software, Datasets & Institutional Repos)",
    "OpenAlex (Global 250M+ Knowledge Graph)",
    "Semantic Scholar (AI & Computer Science Graph)",
    "arXiv (Physics, Mathematics, CS Preprints)",
    "PubMed (Biomedical & Life Sciences NLM/NIH)",
    "Europe PMC (Clinical, Medical & European Open Access)",
    "DOAJ (Directory of Open Access Journals)",
    "HAL Open Science (CNRS, INRIA Multidisciplinary Archive)",
    "Zenodo (Open Science Research Code & Datasets)",
    "INSPIRE HEP (High-Energy Physics & Quantum Theory)",
    "NASA ADS (Astrophysics & Planetary Science, opt-in)"
]

# ==============================================================================
# ACADEMIC DATABASE ENGINES
# ==============================================================================

async def fetch_pdf_link(session, doi):
    """Finds legal open-access PDF via Unpaywall."""
    if not doi:
        return None
    clean_doi = doi.replace("https://doi.org/", "").strip()
    try:
        url = f"https://api.unpaywall.org/v2/{clean_doi}?email=agent@biblioaudit.org"
        async with session.get(url, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=4)) as r:
            if r.status == 200:
                data = await r.json()
                best_loc = data.get("best_oa_location", {})
                if best_loc and best_loc.get("url_for_pdf"):
                    return best_loc.get("url_for_pdf")
    except Exception:
        pass
    return None

async def fetch_crossref(session, doi=None, title=None, author=None):
    """Fetches metadata from Crossref by DOI or bibliographic title/author search."""
    try:
        if doi:
            clean_doi = doi.replace("https://doi.org/", "").strip().lower()
            url = f"https://api.crossref.org/works/{clean_doi}"
            async with session.get(url, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get("message"), "crossref-doi"

        if title:
            url = "https://api.crossref.org/works"
            query = f"{title} {author}" if author else title
            params = {"query.bibliographic": query, "rows": 15}
            async with session.get(url, params=params, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    data = await r.json()
                    items = data.get("message", {}).get("items", [])
                    items.sort(key=lambda x: (
                        similarity(title, (x.get("title") or [""])[0]),
                        x.get("is-referenced-by-count", 0)
                    ), reverse=True)

                    for item in items:
                        item_titles = item.get("title", [])
                        item_title = item_titles[0] if item_titles else ""
                        if is_title_match(title, item_title):
                            return item, "crossref-title"
    except Exception:
        pass
    return None, None

async def fetch_doi2bib_entry(doi):
    """Fetches and verifies DOI metadata via doi2bib."""
    try:
        clean_doi = doi.replace("https://doi.org/", "").strip()
        from doi2bib.crossref import get_bib_from_doi
        loop = asyncio.get_running_loop()
        found, bib = await loop.run_in_executor(None, get_bib_from_doi, clean_doi)
        if found and bib:
            parsed = bibtexparser.loads(bib)
            if parsed.entries:
                e = parsed.entries[0]
                year = e.get("year")
                return {
                    "DOI": clean_doi,
                    "title": [e.get("title", "")],
                    "issued": {"date-parts": [[int(year)]]} if year and str(year).isdigit() else {},
                    "container-title": [e.get("journal", "")],
                    "author": [{"family": a.strip()} for a in e.get("author", "").split(" and ")],
                    "volume": e.get("volume"),
                    "issue": e.get("number"),
                    "page": e.get("pages")
                }, "doi2bib"
    except Exception:
        pass
    return None, None

async def fetch_datacite(session, doi=None, title=None, author=None):
    """Fetches metadata from DataCite (crucial for Zenodo DOIs, software, datasets)."""
    try:
        if doi:
            clean_doi = doi.replace("https://doi.org/", "").strip()
            url = f"https://api.datacite.org/dois/{clean_doi}"
            async with session.get(url, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    data = await r.json()
                    attrs = data.get("data", {}).get("attributes", {})
                    titles = attrs.get("titles", [])
                    matched_title = titles[0].get("title", "") if titles else ""
                    year = attrs.get("publicationYear")
                    container = attrs.get("container", {}) or {}
                    container_title = container.get("title") or attrs.get("publisher", "")

                    authors = []
                    for c in attrs.get("creators", []):
                        fam = c.get("familyName")
                        giv = c.get("givenName")
                        if not fam and c.get("name"):
                            raw = c.get("name", "")
                            fam, giv = raw.split(",", 1) if "," in raw else (raw, "")
                        if fam:
                            authors.append({"family": fam.strip(), "given": giv.strip() if giv else ""})

                    return {
                        "DOI": attrs.get("doi") or clean_doi,
                        "title": [matched_title],
                        "issued": {"date-parts": [[int(year)]]} if year else {},
                        "container-title": [container_title],
                        "author": authors,
                        "volume": container.get("volume"),
                        "issue": container.get("issue"),
                        "page": container.get("firstPage")
                    }, "datacite-doi"

        if title:
            url = "https://api.datacite.org/dois"
            query = f'"{title}"'
            if author:
                query += f' AND "{author}"'
            params = {"query": query, "page[size]": 5}
            async with session.get(url, params=params, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    data = await r.json()
                    for item in data.get("data", []):
                        attrs = item.get("attributes", {})
                        titles = attrs.get("titles", [])
                        matched_title = titles[0].get("title", "") if titles else ""
                        if similarity(title, matched_title) > 0.75:
                            year = attrs.get("publicationYear")
                            container = attrs.get("container", {}) or {}
                            container_title = container.get("title") or attrs.get("publisher", "")

                            authors = []
                            for c in attrs.get("creators", []):
                                fam = c.get("familyName")
                                giv = c.get("givenName")
                                if not fam and c.get("name"):
                                    raw = c.get("name", "")
                                    fam, giv = raw.split(",", 1) if "," in raw else (raw, "")
                                if fam:
                                    authors.append({"family": fam.strip(), "given": giv.strip() if giv else ""})

                            return {
                                "DOI": attrs.get("doi"),
                                "title": [matched_title],
                                "issued": {"date-parts": [[int(year)]]} if year else {},
                                "container-title": [container_title],
                                "author": authors,
                                "volume": container.get("volume"),
                                "issue": container.get("issue"),
                                "page": container.get("firstPage")
                            }, "datacite"
    except Exception:
        pass
    return None, None

async def fetch_openalex(session, doi=None, title=None, author=None):
    """Fetches metadata from OpenAlex Knowledge Graph (250M+ works)."""
    try:
        if doi:
            clean_doi = doi.replace("https://doi.org/", "").strip()
            url = f"https://api.openalex.org/works/https://doi.org/{clean_doi}"
            params = {"mailto": "agent@biblioaudit.org"}
            async with session.get(url, params=params, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    best = await r.json()
                    return {
                        "DOI": (best.get("doi") or "").replace("https://doi.org/", ""),
                        "title": [best.get("display_name", "")],
                        "issued": {"date-parts": [[best.get("publication_year")]]} if best.get("publication_year") else {},
                        "container-title": [best.get("primary_location", {}).get("source", {}).get("display_name", "")],
                        "author": [{"family": a.get("author", {}).get("display_name", ""), "given": ""} for a in best.get("authorships", [])],
                        "volume": best.get("biblio", {}).get("volume"),
                        "issue": best.get("biblio", {}).get("issue"),
                        "page": f"{best.get('biblio', {}).get('first_page')}-{best.get('biblio', {}).get('last_page')}" if best.get("biblio", {}).get("first_page") else None,
                        "citation_count": best.get("cited_by_count")
                    }, "openalex-doi"

        if title:
            url = "https://api.openalex.org/works"
            filter_query = f"title.search:{title},author.search:{author}" if author else f"title.search:{title}"
            params = {"filter": filter_query, "sort": "cited_by_count:desc", "mailto": "agent@biblioaudit.org"}
            async with session.get(url, params=params, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    data = await r.json()
                    results = data.get("results", [])
                    if results:
                        best = results[0]
                        if similarity(title, best.get("display_name", "")) > 0.75:
                            return {
                                "DOI": (best.get("doi") or "").replace("https://doi.org/", ""),
                                "title": [best.get("display_name")],
                                "issued": {"date-parts": [[best.get("publication_year")]]} if best.get("publication_year") else {},
                                "container-title": [best.get("primary_location", {}).get("source", {}).get("display_name", "")],
                                "author": [{"family": a.get("author", {}).get("display_name", ""), "given": ""} for a in best.get("authorships", [])],
                                "volume": best.get("biblio", {}).get("volume"),
                                "issue": best.get("biblio", {}).get("issue"),
                                "page": f"{best.get('biblio', {}).get('first_page')}-{best.get('biblio', {}).get('last_page')}" if best.get("biblio", {}).get("first_page") else None,
                                "citation_count": best.get("cited_by_count")
                            }, "openalex"
    except Exception:
        pass
    return None, None

async def fetch_semanticscholar(session, doi=None, title=None, author=None):
    """Fetches metadata from Semantic Scholar Graph API."""
    try:
        if doi:
            clean_doi = doi.replace("https://doi.org/", "").strip()
            url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{clean_doi}"
            params = {"fields": "title,authors,year,venue,externalIds,citationCount"}
            async with session.get(url, params=params, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    paper = await r.json()
                    return {
                        "DOI": paper.get("externalIds", {}).get("DOI") or clean_doi,
                        "title": [paper.get("title", "")],
                        "issued": {"date-parts": [[paper.get("year")]]} if paper.get("year") else {},
                        "container-title": [paper.get("venue", "")],
                        "author": [{"family": a.get("name", "")} for a in paper.get("authors", [])],
                        "citation_count": paper.get("citationCount")
                    }, "semanticscholar-doi"

        if title:
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            query = f"{title} {author}" if author else title
            params = {"query": query, "limit": 5, "fields": "title,authors,year,venue,externalIds,citationCount"}
            async with session.get(url, params=params, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    data = await r.json()
                    items = data.get("data", [])
                    items.sort(key=lambda x: x.get("citationCount", 0), reverse=True)
                    for paper in items:
                        if similarity(title, paper.get("title", "")) > 0.75:
                            return {
                                "DOI": paper.get("externalIds", {}).get("DOI"),
                                "title": [paper.get("title")],
                                "issued": {"date-parts": [[paper.get("year")]]} if paper.get("year") else {},
                                "container-title": [paper.get("venue", "")],
                                "author": [{"family": a.get("name", "")} for a in paper.get("authors", [])],
                                "citation_count": paper.get("citationCount")
                            }, "semanticscholar"
    except Exception:
        pass
    return None, None

async def fetch_arxiv(session, title, author=None):
    """Fetches preprints from arXiv API."""
    url = "https://export.arxiv.org/api/query"
    query = f'ti:"{title}"'
    if author:
        query += f' AND au:"{author}"'
    params = {"search_query": query, "max_results": 2}
    try:
        async with session.get(url, params=params, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                xml_data = await r.text()
                data = xmltodict.parse(xml_data)
                entries = data.get("feed", {}).get("entry")
                if entries:
                    if isinstance(entries, dict):
                        entries = [entries]
                    for entry in entries:
                        matched_title = entry.get("title", "").replace("\n", " ").strip()
                        if similarity(title, matched_title) > 0.75:
                            arxiv_id = entry.get("id", "").split("/abs/")[-1]
                            pub_date = entry.get("published", "")[:4]
                            authors_raw = entry.get("author")
                            if isinstance(authors_raw, dict):
                                authors_raw = [authors_raw]
                            authors = [{"family": a.get("name", "")} for a in (authors_raw or [])]

                            return {
                                "DOI": entry.get("arxiv:doi", {}).get("#text") if entry.get("arxiv:doi") else None,
                                "arxiv_id": arxiv_id,
                                "title": [matched_title],
                                "issued": {"date-parts": [[int(pub_date)]]} if pub_date.isdigit() else {},
                                "container-title": ["arXiv Preprint"],
                                "author": authors
                            }, "arxiv"
    except Exception:
        pass
    return None, None

async def fetch_pubmed(session, title, author=None):
    """Fetches biomedical literature from NCBI PubMed E-utilities."""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    term = f"{title} AND {author}[Author]" if author else title
    try:
        async with session.get(f"{base}/esearch.fcgi", params={"db": "pubmed", "term": term, "retmode": "json", "retmax": 1}, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                return None, None
            data = await r.json()
            ids = data.get("esearchresult", {}).get("idlist", [])
            if not ids:
                return None, None
            pmid = ids[0]

        async with session.get(f"{base}/esummary.fcgi", params={"db": "pubmed", "id": pmid, "retmode": "json"}, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                return None, None
            data = await r.json()
            details = data.get("result", {}).get(pmid, {})
            matched_title = details.get("title", "")

            if similarity(title, matched_title) <= 0.75:
                return None, None

            pub_date = details.get("pubdate", "")
            year_match = re.search(r"\d{4}", pub_date)
            year = year_match.group(0) if year_match else None
            return {
                "DOI": details.get("elocationid", "").replace("doi: ", "") or f"PMID:{pmid}",
                "title": [matched_title],
                "issued": {"date-parts": [[int(year)]]} if year else {},
                "container-title": [details.get("source", "")],
                "author": [{"family": a.get("name", "")} for a in details.get("authors", [])],
                "volume": details.get("volume"),
                "issue": details.get("issue"),
                "page": details.get("pages")
            }, "pubmed-full"
    except Exception:
        pass
    return None, None

async def fetch_europepmc(session, doi=None, title=None, author=None):
    """Fetches biomedical and clinical literature from Europe PMC webservice."""
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    try:
        if doi:
            clean_doi = doi.replace("https://doi.org/", "").strip()
            params = {"query": f'DOI:"{clean_doi}"', "format": "json", "pageSize": 1}
            async with session.get(url, params=params, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    data = await r.json()
                    results = data.get("resultList", {}).get("result", [])
                    if results:
                        paper = results[0]
                        pub_date = paper.get("firstPublicationDate", "") or paper.get("pubYear", "")
                        year = pub_date[:4] if pub_date and len(pub_date) >= 4 else None
                        journal_info = paper.get("journalInfo", {}) or {}
                        jrnl = journal_info.get("journal") or {}
                        journal_title = jrnl.get("title") or paper.get("journalTitle") or ""

                        authors = []
                        for a in (paper.get("authorList") or {}).get("author", []):
                            full_name = a.get("fullName", "")
                            fam, giv = full_name.split(",", 1) if "," in full_name else (full_name, "")
                            authors.append({"family": fam.strip(), "given": giv.strip() if giv else ""})

                        return {
                            "DOI": paper.get("doi") or clean_doi,
                            "title": [paper.get("title", "")],
                            "issued": {"date-parts": [[int(year)]]} if year else {},
                            "container-title": [journal_title],
                            "author": authors,
                            "volume": str(journal_info.get("volume")) if journal_info.get("volume") else None,
                            "issue": str(journal_info.get("issue")) if journal_info.get("issue") else None,
                            "page": paper.get("pageInfo"),
                            "citation_count": paper.get("citedByCount")
                        }, "europepmc-doi"

        if title:
            query = f'(TITLE:"{title}")'
            if author:
                query += f' AND (AUTHOR:"{author}")'
            params = {"query": query, "format": "json", "pageSize": 5, "sort": "CITED_DESC"}
            async with session.get(url, params=params, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    data = await r.json()
                    for paper in data.get("resultList", {}).get("result", []):
                        matched_title = paper.get("title", "")
                        if similarity(title, matched_title) > 0.75:
                            pub_date = paper.get("firstPublicationDate", "") or paper.get("pubYear", "")
                            year = pub_date[:4] if pub_date and len(pub_date) >= 4 else None

                            journal_info = paper.get("journalInfo", {}) or {}
                            jrnl = journal_info.get("journal") or {}
                            journal_title = jrnl.get("title") or paper.get("journalTitle") or ""

                            authors = []
                            for a in (paper.get("authorList") or {}).get("author", []):
                                full_name = a.get("fullName", "")
                                fam, giv = full_name.split(",", 1) if "," in full_name else (full_name, "")
                                authors.append({"family": fam.strip(), "given": giv.strip() if giv else ""})

                            doi = paper.get("doi")
                            if not doi and paper.get("pmcid"):
                                doi = f"PMCID:{paper.get('pmcid')}"

                            return {
                                "DOI": doi,
                                "title": [matched_title],
                                "issued": {"date-parts": [[int(year)]]} if year else {},
                                "container-title": [journal_title],
                                "author": authors,
                                "volume": str(journal_info.get("volume")) if journal_info.get("volume") else None,
                                "issue": str(journal_info.get("issue")) if journal_info.get("issue") else None,
                                "page": paper.get("pageInfo"),
                                "citation_count": paper.get("citedByCount")
                            }, "europepmc"
    except Exception:
        pass
    return None, None

async def fetch_doaj(session, title, author=None):
    """Fetches articles from Directory of Open Access Journals (DOAJ)."""
    try:
        clean_title = urllib.parse.quote(title)
        url = f"https://doaj.org/api/v2/search/articles/title:%22{clean_title}%22"
        params = {"pageSize": 5}
        async with session.get(url, params=params, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                data = await r.json()
                for item in data.get("results", []):
                    bib = item.get("bibjson", {})
                    matched_title = bib.get("title", "")
                    if similarity(title, matched_title) > 0.75:
                        year = bib.get("year")
                        journal = bib.get("journal", {})
                        authors = [{"family": a.get("name", "")} for a in bib.get("author", [])]
                        doi = next((i.get("id") for i in bib.get("identifier", []) if i.get("type", "").lower() == "doi"), None)

                        return {
                            "DOI": doi,
                            "title": [matched_title],
                            "issued": {"date-parts": [[int(year)]]} if year and str(year).isdigit() else {},
                            "container-title": [journal.get("title", "")],
                            "author": authors,
                            "volume": str(journal.get("volume")) if journal.get("volume") else None,
                            "issue": str(journal.get("number")) if journal.get("number") else None,
                            "page": f"{bib.get('start_page', '')}-{bib.get('end_page', '')}".strip("-") or None
                        }, "doaj"
    except Exception:
        pass
    return None, None

async def fetch_hal(session, title, author=None):
    """Fetches metadata from HAL Open Science (CNRS, INRIA European archive)."""
    url = "https://api.archives-ouvertes.fr/search/"
    query = f'title_t:"{title}"'
    if author:
        query += f' AND authFullName_t:"{author}"'
    params = {
        "q": query, "wt": "json", "rows": 5,
        "fl": "title_s,authFullName_s,producedDateY_i,journalTitle_s,doiId_s,volume_s,issue_s,page_s"
    }
    try:
        async with session.get(url, params=params, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                data = await r.json()
                for doc in data.get("response", {}).get("docs", []):
                    titles = doc.get("title_s", [])
                    matched_title = titles[0] if titles else ""
                    if similarity(title, matched_title) > 0.75:
                        return {
                            "DOI": doc.get("doiId_s"),
                            "title": [matched_title],
                            "issued": {"date-parts": [[int(doc.get("producedDateY_i"))]]} if doc.get("producedDateY_i") else {},
                            "container-title": [doc.get("journalTitle_s", "")],
                            "author": [{"family": name} for name in doc.get("authFullName_s", [])],
                            "volume": str(doc.get("volume_s")) if doc.get("volume_s") else None,
                            "issue": str(doc.get("issue_s")) if doc.get("issue_s") else None,
                            "page": doc.get("page_s")
                        }, "hal"
    except Exception:
        pass
    return None, None

async def fetch_zenodo(session, title, author=None):
    """Fetches records, software citations, and datasets from Zenodo REST API."""
    url = "https://zenodo.org/api/records"
    query = f'"{title}"'
    if author:
        query += f' AND "{author}"'
    params = {"q": query, "size": 5}
    try:
        async with session.get(url, params=params, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                data = await r.json()
                for hit in data.get("hits", {}).get("hits", []):
                    meta = hit.get("metadata", {})
                    matched_title = meta.get("title", "")
                    if similarity(title, matched_title) > 0.75:
                        pub_date = meta.get("publication_date", "")
                        year = pub_date[:4] if pub_date and len(pub_date) >= 4 else None
                        container_title = meta.get("journal_title") or meta.get("publication_type") or "Zenodo"

                        authors = []
                        for c in meta.get("creators", []):
                            name = c.get("name", "")
                            fam, giv = name.split(",", 1) if "," in name else (name, "")
                            authors.append({"family": fam.strip(), "given": giv.strip() if giv else ""})

                        return {
                            "DOI": hit.get("doi") or meta.get("doi"),
                            "title": [matched_title],
                            "issued": {"date-parts": [[int(year)]]} if year and year.isdigit() else {},
                            "container-title": [container_title],
                            "author": authors,
                            "volume": None, "issue": None, "page": None
                        }, "zenodo"
    except Exception:
        pass
    return None, None

async def fetch_inspirehep(session, title, author=None):
    """Fetches high-energy physics metadata from INSPIRE HEP API."""
    url = "https://inspirehep.net/api/literature"
    query = f'title:"{title}"'
    if author:
        query += f' AND author:"{author}"'
    params = {"q": query, "size": 5, "sort": "mostrecent"}
    try:
        async with session.get(url, params=params, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                data = await r.json()
                for hit in data.get("hits", {}).get("hits", []):
                    meta = hit.get("metadata", {})
                    titles = meta.get("titles", [])
                    matched_title = titles[0].get("title", "") if titles else ""
                    if similarity(title, matched_title) > 0.75:
                        dois = meta.get("dois", [])
                        doi = (dois[0].get("value") or dois[0].get("doi")) if dois and isinstance(dois[0], dict) else (dois[0] if dois else None)
                        arxiv_eprints = meta.get("arxiv_eprints", [])
                        arxiv_id = arxiv_eprints[0].get("value") if arxiv_eprints and isinstance(arxiv_eprints[0], dict) else (arxiv_eprints[0] if arxiv_eprints else None)

                        pub_info = meta.get("publication_info", [{}])[0] if meta.get("publication_info") else {}
                        authors = []
                        for a_data in meta.get("authors", []):
                            full_name = a_data.get("full_name", "")
                            fam, giv = full_name.split(",", 1) if "," in full_name else (full_name, "")
                            authors.append({"family": fam.strip(), "given": giv.strip() if giv else ""})

                        return {
                            "DOI": doi,
                            "arxiv_id": arxiv_id,
                            "title": [matched_title],
                            "issued": {"date-parts": [[pub_info.get("year")]]} if pub_info.get("year") else {},
                            "container-title": [pub_info.get("journal_title", "")],
                            "author": authors,
                            "volume": str(pub_info.get("journal_volume")) if pub_info.get("journal_volume") else None,
                            "issue": None,
                            "page": str(pub_info.get("page_artid")) if pub_info.get("page_artid") else None
                        }, "inspirehep"
    except Exception:
        pass
    return None, None

async def fetch_nasaads(session, title, author=None):
    """Fetches astrophysics/physics metadata from NASA ADS API (requires NASA_ADS_API_KEY)."""
    api_key = os.environ.get("NASA_ADS_API_KEY", "")
    if not api_key:
        return None, None

    url = "https://api.adsabs.harvard.edu/v1/search/query"
    query = f'title:"{title}"'
    if author:
        query += f' author:"{author}"'
    headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {api_key}"}
    params = {"q": query, "fl": "title,author,year,bibcode,doi,volume,issue,pub,page", "rows": 5}
    try:
        async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                data = await r.json()
                for doc in data.get("response", {}).get("docs", []):
                    titles = doc.get("title", [""])
                    matched_title = titles[0] if titles else ""
                    if similarity(title, matched_title) > 0.75:
                        authors = [{"family": a.split(",")[0].strip() if "," in a else a} for a in doc.get("author", [])]
                        doi = doc.get("doi")
                        if isinstance(doi, list):
                            doi = doi[0] if doi else None

                        page = doc.get("page")
                        if isinstance(page, list):
                            page = page[0] if page else None

                        return {
                            "DOI": doi,
                            "title": [matched_title],
                            "issued": {"date-parts": [[doc.get("year")]]} if doc.get("year") else {},
                            "container-title": [doc.get("pub", "")],
                            "author": authors,
                            "volume": str(doc.get("volume")) if doc.get("volume") else None,
                            "issue": str(doc.get("issue")) if doc.get("issue") else None,
                            "page": str(page) if page else None
                        }, "nasaads"
    except Exception:
        pass
    return None, None

async def fetch_opencitations(session, doi):
    """Fetches citation count from OpenCitations COCI API."""
    if not doi:
        return None, None
    clean_doi = doi.replace("https://doi.org/", "").strip()
    url = f"https://opencitations.net/index/coci/api/v1/citations/{clean_doi}"
    try:
        async with session.get(url, headers=DEFAULT_HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                data = await r.json()
                if isinstance(data, list):
                    return {"citation_count": len(data)}, "opencitations"
    except Exception:
        pass
    return None, None

# ==============================================================================
# VERIFICATION & AUDIT PIPELINE
# ==============================================================================

async def process_entry(entry, session, sem):
    """
    Validates a single BibTeX entry across 12+ academic databases.
    Returns audit status, field checks, clean canonical metadata, and confidence score.
    """
    key = entry.get("ID", "Unknown")
    
    if entry.get("verified", "").lower() == "true":
        return {
            "key": key,
            "exists": True,
            "confidence": 100,
            "resolution": "manual-override",
            "verified_doi": entry.get("doi", "Manual"),
            "doi_url": f"https://doi.org/{entry.get('doi')}" if entry.get("doi") else None,
            "pdf_link": None,
            "field_check": {},
            "clean_data": {},
            "warnings": []
        }

    bibtex_title = entry.get("title", "")
    bibtex_year = entry.get("year", "")
    bibtex_journal = entry.get("journal", "") or entry.get("booktitle", "")
    bibtex_author_raw = entry.get("author", "")

    status = {
        "key": key,
        "entry_type": entry.get("ENTRYTYPE", "article"),
        "bibtex_title": bibtex_title,
        "bibtex_year": bibtex_year,
        "bibtex_journal": bibtex_journal,
        "bibtex_author": bibtex_author_raw,
        "exists": False,
        "verified_doi": None,
        "arxiv_id": None,
        "doi_url": None,
        "pdf_link": None,
        "resolution": None,
        "confidence": 0,
        "field_check": {},
        "clean_data": {},
        "warnings": [],
        "original_entry": entry
    }

    title = bibtex_title.replace("{", "").replace("}", "").strip()
    doi = entry.get("doi", "").strip() if entry.get("doi") else None

    first_author_lastname = None
    if bibtex_author_raw:
        first_author = bibtex_author_raw.split(" and ")[0].strip()
        first_author_lastname = first_author.split(",")[0].strip() if "," in first_author else first_author.split(" ")[-1].strip()

    item, source = None, None

    async with sem:
        # Phase 1: Exact DOI Resolution (Crossref -> DataCite -> OpenAlex -> Europe PMC -> Semantic Scholar)
        if doi:
            item, source = await fetch_crossref(session, doi=doi)
            if item and title:
                returned_title = (item.get("title") or [""])[0]
                if not is_title_match(title, returned_title, threshold=0.65):
                    status["warnings"].append("DOI resolves to a different title in Crossref; verifying other sources")
                    item, source = None, None

            if not item:
                item, source = await fetch_datacite(session, doi=doi)
                if item and title:
                    returned_title = (item.get("title") or [""])[0]
                    if not is_title_match(title, returned_title, threshold=0.65):
                        item, source = None, None

            if not item:
                item, source = await fetch_doi2bib_entry(doi=doi)
                if item and title:
                    returned_title = (item.get("title") or [""])[0]
                    if not is_title_match(title, returned_title, threshold=0.65):
                        item, source = None, None

            if not item:
                item, source = await fetch_openalex(session, doi=doi)
                if item and title:
                    returned_title = (item.get("title") or [""])[0]
                    if not is_title_match(title, returned_title, threshold=0.65):
                        item, source = None, None

            if not item:
                item, source = await fetch_europepmc(session, doi=doi)
                if item and title:
                    returned_title = (item.get("title") or [""])[0]
                    if not is_title_match(title, returned_title, threshold=0.65):
                        item, source = None, None

            if not item:
                item, source = await fetch_semanticscholar(session, doi=doi)
                if item and title:
                    returned_title = (item.get("title") or [""])[0]
                    if not is_title_match(title, returned_title, threshold=0.65):
                        item, source = None, None

        # Phase 2: Cascading Search by Title & Author across 12 Engines
        if not item and title:
            item, source = await fetch_semanticscholar(session, title=title, author=first_author_lastname)
            if not item: item, source = await fetch_openalex(session, title=title, author=first_author_lastname)
            if not item: item, source = await fetch_inspirehep(session, title=title, author=first_author_lastname)
            if not item: item, source = await fetch_arxiv(session, title=title, author=first_author_lastname)
            if not item: item, source = await fetch_crossref(session, title=title, author=first_author_lastname)
            if not item: item, source = await fetch_datacite(session, title=title, author=first_author_lastname)
            if not item: item, source = await fetch_europepmc(session, title=title, author=first_author_lastname)
            if not item: item, source = await fetch_pubmed(session, title=title, author=first_author_lastname)
            if not item: item, source = await fetch_doaj(session, title=title, author=first_author_lastname)
            if not item: item, source = await fetch_hal(session, title=title, author=first_author_lastname)
            if not item: item, source = await fetch_zenodo(session, title=title, author=first_author_lastname)
            if not item: item, source = await fetch_nasaads(session, title=title, author=first_author_lastname)

        # Phase 3: Metadata Alignment & Enrichment
        if item and item.get("DOI"):
            if source in ["openalex", "semanticscholar", "inspirehep", "europepmc", "doaj", "hal"]:
                cr_item, _ = await fetch_crossref(session, doi=item["DOI"])
                if cr_item:
                    item, source = cr_item, "crossref-aligned"

            status["pdf_link"] = await fetch_pdf_link(session, item["DOI"])

            if "citation_count" not in item or item.get("citation_count") is None:
                oc_item, _ = await fetch_opencitations(session, item["DOI"])
                if oc_item:
                    item["citation_count"] = oc_item.get("citation_count")

    if not item:
        return status

    # Phase 4: Canonical Metadata Extraction
    status["exists"] = True
    status["resolution"] = source
    status["verified_doi"] = item.get("DOI")
    status["arxiv_id"] = item.get("arxiv_id")

    if status["verified_doi"]:
        if "PMID:" in str(status["verified_doi"]):
            status["doi_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{status['verified_doi'].replace('PMID:', '')}/"
        elif "PMCID:" in str(status["verified_doi"]):
            status["doi_url"] = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{status['verified_doi'].replace('PMCID:', '')}/"
        else:
            status["doi_url"] = f"https://doi.org/{status['verified_doi']}"
    elif status["arxiv_id"]:
        status["doi_url"] = f"https://arxiv.org/abs/{status['arxiv_id']}"

    cr_title = (item.get("title") or [""])[0]
    date_parts = (item.get("issued") or {}).get("date-parts") or [[None]]
    cr_year = date_parts[0][0] if date_parts and date_parts[0] else None
    cr_journal = (item.get("container-title") or [""])[0]

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
        "title": cr_title,
        "year": str(cr_year) if cr_year else None,
        "journal": cr_journal,
        "author": cr_author_str,
        "volume": str(cr_vol) if cr_vol else None,
        "number": str(cr_num) if cr_num else None,
        "pages": str(cr_page) if cr_page else None,
        "doi": status["verified_doi"],
        "arxiv_id": status["arxiv_id"],
        "citation_count": item.get("citation_count")
    }

    # Phase 5: Verification & Discrepancy Checks
    year_status = "mismatch"
    bib_year = entry.get("year")
    if str(bib_year).strip() == str(cr_year).strip():
        year_status = "ok"
    elif bib_year and cr_year:
        try:
            if abs(int(bib_year) - int(cr_year)) <= 1:
                year_status = "ok"
        except Exception:
            pass

    journal_status = check_journal_match(bibtex_journal, cr_journal)
    auth_status = "ok" if check_authors(bibtex_author_raw, cr_author_str) else "mismatch"
    title_status = "ok" if is_title_match(title, cr_title) else "mismatch"

    status["field_check"] = {
        "title": {"bibtex": title, "correct": cr_title, "status": title_status},
        "year": {"bibtex": bib_year, "correct": cr_year, "status": year_status},
        "journal": {"bibtex": bibtex_journal, "correct": cr_journal, "status": journal_status},
        "author": {"bibtex": bibtex_author_raw, "correct": cr_author_str, "status": auth_status}
    }

    # Phase 6: Confidence Scoring
    checked_fields = [k for k in ["title", "year", "journal", "author"] if entry.get(k)]
    if not checked_fields:
        checked_fields = ["title"]

    ok_count = sum(1 for f in checked_fields if status["field_check"].get(f, {}).get("status") == "ok")
    total_checked = len(checked_fields)
    score_ratio = ok_count / total_checked if total_checked > 0 else 0.5
    raw_confidence = int(score_ratio * 100)

    trusted_direct = [
        "crossref-doi", "datacite-doi", "openalex-doi", "europepmc-doi",
        "semanticscholar-doi", "crossref-aligned", "pubmed-full", "arxiv", "doi2bib"
    ]
    if source in trusted_direct and status["field_check"]["title"]["status"] == "ok":
        status["confidence"] = max(raw_confidence, 90 if ok_count >= total_checked - 1 else 75)
    else:
        status["confidence"] = raw_confidence

    return status

# ==============================================================================
# CLI RUNNER & DISCOVERY
# ==============================================================================

async def run_audit(entries, rate_limit, verbose=False):
    sem = asyncio.Semaphore(rate_limit)
    total = len(entries)
    results = []

    print(f"[*] Processing {total} references (Concurrency limit: {rate_limit})...\n")

    async with aiohttp.ClientSession() as session:
        tasks = [process_entry(e, session, sem) for e in entries]

        idx = 0
        for coro in asyncio.as_completed(tasks):
            res = await coro
            results.append(res)
            idx += 1

            key = res.get("key", "Unknown")
            conf = res.get("confidence", 0)
            source_display = format_source_name(res.get("resolution"))

            if conf >= 90:
                print(f"  [VERIFIED]  ({conf:3d}%) {key:<25} -> {source_display}")
            elif res.get("exists"):
                print(f"  [ATTENTION] ({conf:3d}%) {key:<25} -> {source_display}")
                if verbose and res.get("field_check"):
                    for field, chk in res["field_check"].items():
                        if chk.get("status") != "ok":
                            print(f"        └─ {field.capitalize()}: BibTeX='{chk.get('bibtex')}' vs Record='{chk.get('correct')}'")
            else:
                print(f"  [NOT FOUND] ({conf:3d}%) {key:<25} -> Missing in all queried databases")

    entry_order = {e.get("ID"): i for i, e in enumerate(entries)}
    results.sort(key=lambda r: entry_order.get(r.get("key"), 999999))
    return results

def print_summary(results, elapsed):
    clean = [r for r in results if r.get("confidence", 0) >= 90]
    needs_work = [r for r in results if r.get("exists") and r.get("confidence", 0) < 90]
    missing = [r for r in results if not r.get("exists")]
    total = len(results)

    clean_pct = (len(clean) / total * 100) if total else 0
    work_pct = (len(needs_work) / total * 100) if total else 0
    miss_pct = (len(missing) / total * 100) if total else 0

    print("\n" + "=" * 60)
    print("                      AUDIT SUMMARY")
    print("=" * 60)
    print(f"  Total References Audited : {total}")
    print(f"  Verified Clean (>90%)    : {len(clean):>4}  ({clean_pct:5.1f}%)")
    print(f"  Needs Attention          : {len(needs_work):>4}  ({work_pct:5.1f}%)")
    print(f"  Not Found                : {len(missing):>4}  ({miss_pct:5.1f}%)")
    print(f"  Total Time Elapsed       : {elapsed:.2f}s")
    print("=" * 60)

def audit_file(input_path, output_csv=None, fix_bib=None, rate=4, verbose=False, loop=False):
    """Audits a single BibTeX file with optional closed-loop verification."""
    path = Path(input_path)
    if not path.exists():
        print(f"[!] Error: File '{input_path}' not found.", file=sys.stderr)
        return False

    print(f"\n[*] Reading bibliography: {path}")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            bib_str = f.read()

        parser = BibTexParser()
        parser.ignore_nonstandard_types = False
        library = bibtexparser.loads(bib_str, parser=parser)
        entries = library.entries
    except Exception as e:
        print(f"[!] Error parsing BibTeX file: {e}", file=sys.stderr)
        return False

    if not entries:
        print(f"[!] No entries found in {path.name}.", file=sys.stderr)
        return False

    header_pass1 = "PASS 1: INITIAL BIBLIOGRAPHY AUDIT" if loop else "AUDIT"
    print(f"[*] Found {len(entries)} entries. Starting {header_pass1}...")
    start_time = time.time()
    results = asyncio.run(run_audit(entries, rate, verbose))
    elapsed = time.time() - start_time

    print_summary(results, elapsed)

    # Save CSV report for Pass 1
    csv_file = output_csv or f"{path.stem}_audit_report.csv"
    try:
        csv_bytes = to_csv(results)
        with open(csv_file, "wb") as f:
            f.write(csv_bytes)
        print(f"[+] Initial audit CSV report saved to: {csv_file}")
    except Exception as e:
        print(f"[!] Warning: Could not save CSV: {e}", file=sys.stderr)

    # Save fixed BibTeX
    target_fixed_bib = fix_bib or (f"{path.parent / (path.stem + '_fixed.bib')}" if loop else None)
    if target_fixed_bib:
        try:
            with open(target_fixed_bib, "w", encoding="utf-8") as f:
                for r in results:
                    clean_data = r.get("clean_data")
                    conf = r.get("confidence", 0)
                    if clean_data and r.get("exists") and conf >= 80:
                        f.write(fetch_canonical_bibtex(r["key"], r.get("verified_doi"), clean_data) + "\n\n")
                    else:
                        orig = r.get("original_entry") or {}
                        etype = orig.get("ENTRYTYPE", r.get("entry_type", "misc"))
                        f.write(f"@{etype}{{{r['key']},\n")
                        wrote_doi = False
                        for field, val in orig.items():
                            if field in ["ENTRYTYPE", "ID"]:
                                continue
                            if field.lower() == "doi":
                                wrote_doi = True
                            f.write(f"  {field} = {{{val}}},\n")
                        if not wrote_doi and r.get("verified_doi") and conf >= 70:
                            f.write(f"  doi = {{{r['verified_doi']}}},\n")
                        f.write("}\n\n")
            print(f"[+] Corrected BibTeX library saved to: {target_fixed_bib}")
        except Exception as e:
            print(f"[!] Warning: Could not save fixed BibTeX: {e}", file=sys.stderr)

    # Automated Feedback Loop: Re-audit the generated fixed file
    if loop and target_fixed_bib and Path(target_fixed_bib).exists():
        print(f"\n" + "=" * 68)
        print("    FEEDBACK LOOP: RE-AUDITING GENERATED FIXED BIBLIOGRAPHY")
        print("=" * 68)
        try:
            with open(target_fixed_bib, "r", encoding="utf-8", errors="replace") as f:
                fixed_bib_str = f.read()
            p2 = BibTexParser()
            p2.ignore_nonstandard_types = False
            fixed_lib = bibtexparser.loads(fixed_bib_str, parser=p2)
            fixed_entries = fixed_lib.entries

            print(f"[*] Re-auditing {len(fixed_entries)} repaired entries in '{Path(target_fixed_bib).name}'...")
            t2_start = time.time()
            re_results = asyncio.run(run_audit(fixed_entries, rate, verbose=False))
            t2_elapsed = time.time() - t2_start

            # Calculate and display convergence metrics
            delta = compute_feedback_delta(results, re_results)
            print_feedback_report(delta)

            # Save feedback comparison CSV
            fb_csv_path = f"{path.parent / (path.stem + '_feedback_loop.csv')}"
            try:
                fb_bytes = feedback_to_csv(delta)
                with open(fb_csv_path, "wb") as f:
                    f.write(fb_bytes)
                print(f"[+] Feedback loop comparison report saved to: {fb_csv_path}")
            except Exception as e:
                print(f"[!] Warning: Could not save feedback CSV: {e}", file=sys.stderr)

        except Exception as e:
            print(f"[!] Error during feedback loop re-audit: {e}", file=sys.stderr)

    return True

def main():
    print(f"""
========================================================================
  BiblioAudit v{VERSION} - Reference Integrity & Verification System
========================================================================
  Cascading Triangulation Matrix: {len(DATABASES)} Academic Databases
""")

    parser = argparse.ArgumentParser(
        description="BiblioAudit: Automated Reference Integrity & Verification Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python biblioaudit.py References/sn-bibliography.bib
  python biblioaudit.py References/sn-bibliography.bib --loop
  python biblioaudit.py References/ -o report.csv --fix-bib fixed.bib
  python biblioaudit.py                          # Automatically audits files in References/
        """
    )
    parser.add_argument("input_target", nargs="?", default=None, help="Path to .bib file or folder containing .bib files (default: References/)")
    parser.add_argument("-o", "--output", help="Path for CSV audit report")
    parser.add_argument("--fix-bib", help="Optional path to export corrected BibTeX file")
    parser.add_argument("--loop", "--feedback-loop", action="store_true", help="Run automated feedback loop: re-audits the corrected file and reports convergence metrics")
    parser.add_argument("-r", "--rate", type=int, default=4, help="Max concurrent requests (default: 4)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed field comparison for mismatched citations")
    parser.add_argument("--version", action="version", version=f"BiblioAudit v{VERSION}")
    args = parser.parse_args()

    # Discover target files
    target = args.input_target
    if not target:
        if Path("References").is_dir():
            target = "References"
        elif Path("references").is_dir():
            target = "references"
        else:
            bibs = list(Path(".").glob("*.bib"))
            if bibs:
                target = str(bibs[0])
            else:
                print("[!] Error: No input .bib file specified and no References/ folder found.", file=sys.stderr)
                parser.print_help()
                sys.exit(1)

    target_path = Path(target)
    if target_path.is_dir():
        bib_files = sorted(list(target_path.glob("*.bib")))
        # Don't re-audit generated output files
        bib_files = [b for b in bib_files if not b.stem.endswith("_fixed")]
        if not bib_files:
            print(f"[!] No .bib files found in directory: {target_path}", file=sys.stderr)
            sys.exit(1)
        print(f"[*] Found {len(bib_files)} bibliography file(s) in {target_path}:")
        for b in bib_files:
            print(f"    - {b.name}")
        for b in bib_files:
            out_csv = args.output if (len(bib_files) == 1 and args.output) else f"{b.parent / (b.stem + '_audit_report.csv')}"
            out_fix = args.fix_bib if (len(bib_files) == 1 and args.fix_bib) else None
            audit_file(b, output_csv=out_csv, fix_bib=out_fix, rate=args.rate, verbose=args.verbose, loop=args.loop)
    else:
        audit_file(target_path, output_csv=args.output, fix_bib=args.fix_bib, rate=args.rate, verbose=args.verbose, loop=args.loop)

    print("\n[OK] All audits completed.")

if __name__ == "__main__":
    main()
