# BiblioAudit 🧬

[![DOI](https://zenodo.org/badge/1128307082.svg)](https://doi.org/10.5281/zenodo.18155557)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

**Automated Reference Integrity & Verification System**

BiblioAudit is a high-performance command-line tool designed to "stress test" your bibliography before paper submission. It cross-checks citations against **12+ major academic databases** to verify existence, correct metadata errors (typos, wrong publication years, missing DOIs, journal mismatches), and discover legal open-access PDFs.

Checking references manually is tedious and error-prone. BiblioAudit automates this in seconds with zero GUI overhead.

---

## 🚀 Key Features

* **🧠 12-Database Triangulation Matrix:** Cascading verification across:
    * **Crossref:** Universal DOI validation and publisher records.
    * **DataCite:** Datasets, software citations, Zenodo records, and institutional repositories.
    * **OpenAlex:** Global knowledge graph matching across 250M+ scientific works.
    * **Semantic Scholar:** AI & Computer Science citation graphs and paper search.
    * **arXiv:** Preprints in Physics, Mathematics, Computer Science, and Quantitative Biology.
    * **PubMed:** Specialized for biomedical and life sciences (NLM/NIH).
    * **Europe PMC:** Clinical literature, medical physics, and European open access.
    * **DOAJ:** Over 20,000 peer-reviewed open access journals worldwide.
    * **HAL Open Science:** European multidisciplinary archive (CNRS, INRIA, CEA).
    * **Zenodo:** Open research software, code, datasets, and CERN-affiliated outputs.
    * **INSPIRE HEP:** High-energy physics, astrophysics, and quantum theory.
    * **NASA ADS:** Astrophysics and planetary science literature.
* **🔍 Smart Matching:** Uses fuzzy sequence matching and author-specific queries to detect typos without triggering false alarms.
* **📄 PDF Discovery:** Automatically finds legal, Open Access PDF links for your references via Unpaywall.
* **🛠️ Automatic BibTeX Repair & `doi2bib` Integration:** Export a clean, publisher-standard `.bib` file with standardized DOIs, years, authors, and journals with `--fix-bib`.
* **🔁 Closed Feedback Loop (`--loop`):** Re-audits the generated fixed library automatically and evaluates convergence metrics.
* **📊 Comprehensive CSV Audit Report:** Exports full per-reference reports with confidence scores, database sources, and matched links.
* **⚡ Fast & Lightweight:** Asynchronous parallel querying via `aiohttp` with adjustable concurrency.

---

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Official-Satyam-Tiwari/reference-architect.git
   cd reference-architect
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 📖 CLI Usage

Run BiblioAudit directly from your terminal:

```bash
python biblioaudit.py [path-to-bib-file-or-folder] [options]
```
*(If no path is specified, BiblioAudit automatically checks files in the `References/` directory)*

### Options

| Option | Description | Default |
|---|---|---|
| `-o`, `--output` | Path to save the CSV audit report | `<filename>_audit_report.csv` |
| `--fix-bib` | Path to save a corrected BibTeX library | *(optional)* |
| `--loop` | Run automated feedback loop: re-audits the corrected file and reports convergence metrics | `False` |
| `-r`, `--rate` | Maximum concurrent API requests | `4` |
| `-v`, `--verbose` | Print detailed field-by-field comparison for mismatched entries | `False` |
| `--version` | Display BiblioAudit version | |
| `-h`, `--help` | Show command-line help message | |

### Examples

**Basic verification:**
```bash
python biblioaudit.py References/sn-bibliography.bib
```

**Automated Closed Feedback Loop (audit -> fix -> re-audit -> convergence report):**
```bash
python biblioaudit.py References/sn-bibliography.bib --loop
```

**Generate both a CSV report and a corrected BibTeX file:**
```bash
python biblioaudit.py References/sn-bibliography.bib -o audit_report.csv --fix-bib fixed.bib
```

**Faster processing with detailed diffs for mismatched references:**
```bash
python biblioaudit.py References/sn-bibliography.bib --rate 6 --verbose
```

---

## 📄 Citation

If you use BiblioAudit in your research workflow, please cite it using the metadata below:

> **Tiwari, S. (2025). BiblioAudit: Automated Citation Integrity & Verification Tool (Version 2.2.0) [Software]. Zenodo. https://doi.org/10.5281/zenodo.18155557**

**BibTeX:**
```bibtex
@software{Tiwari_BiblioAudit_2025,
  author = {Tiwari, Satyam},
  title = {{BiblioAudit: Automated Citation Integrity & Verification Tool}},
  version = {2.2.0},
  year = {2025},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.18155557},
  url = {https://doi.org/10.5281/zenodo.18155557}
}
```
