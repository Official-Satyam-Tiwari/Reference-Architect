# BiblioAudit

[![DOI](https://zenodo.org/badge/1128307082.svg)](https://doi.org/10.5281/zenodo.18155557)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

BiblioAudit is a command-line tool that checks citations in BibTeX (`.bib`) files. It verifies that references exist, finds missing DOIs, corrects wrong years and journal names, and finds links to open-access PDFs.

It checks references across more than 12 academic databases in parallel and generates a report of all findings.

---

## Features

* **Multi-Database Checking:** Checks references across major scientific databases:
    * **Crossref:** Journal articles, conference proceedings, and books.
    * **DataCite:** Datasets, software citations, and Zenodo records.
    * **OpenAlex:** Global index of research publications.
    * **Semantic Scholar:** Computer science and multidisciplinary papers.
    * **arXiv:** Physics, mathematics, and computer science preprints.
    * **PubMed:** Biomedical and medical life sciences.
    * **Europe PMC:** Open access clinical and life science literature.
    * **DOAJ:** Directory of Open Access Journals.
    * **HAL Open Science:** European research archive.
    * **Zenodo:** Open code, software, datasets, and reports.
    * **INSPIRE HEP:** High-energy physics and astrophysics.
    * **NASA ADS:** Astronomy and physics literature.
* **Typo and Error Detection:** Compares titles, authors, years, and journals to catch typos without false warnings.
* **Open Access PDF Discovery:** Finds legal, free PDF links using the Unpaywall API.
* **Automatic BibTeX Fixes:** Exports a corrected `.bib` file with official publisher metadata using `doi2bib`.
* **Automated Re-check (`--loop`):** Audits the original file, builds a corrected version, re-checks it automatically, and shows a before-and-after comparison.
* **CSV Reports:** Saves a clear summary report with confidence scores and source links.

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Official-Satyam-Tiwari/reference-architect.git
   cd reference-architect
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## Usage

Run the tool from your terminal:

```bash
python biblioaudit.py [path-to-bib-file-or-folder] [options]
```

If you do not specify a path, BiblioAudit automatically checks files in the `References/` folder.

### Options

| Option | Description | Default |
|---|---|---|
| `-o`, `--output` | File path for the CSV report | `<filename>_audit_report.csv` |
| `--fix-bib` | File path to save corrected BibTeX entries | None |
| `--loop` | Re-audit the corrected file and show before-and-after results | False |
| `-r`, `--rate` | Maximum number of concurrent requests | 4 |
| `-v`, `--verbose` | Print field-by-field differences for mismatched citations | False |
| `--version` | Show program version | |
| `-h`, `--help` | Show help message | |

### Examples

**Check a single file:**
```bash
python biblioaudit.py References/sn-bibliography.bib
```

**Check a file, fix errors, and run an automated re-check:**
```bash
python biblioaudit.py References/sn-bibliography.bib --loop
```

**Save a CSV report and a corrected BibTeX file:**
```bash
python biblioaudit.py References/sn-bibliography.bib -o report.csv --fix-bib fixed.bib
```

**Run faster with detailed mismatch information:**
```bash
python biblioaudit.py References/sn-bibliography.bib --rate 6 --verbose
```

---

## Citation

If you use BiblioAudit in your research, please cite:

> Tiwari, S. (2025). BiblioAudit: Automated Citation Integrity & Verification Tool (Version 2.2.0) [Software]. Zenodo. https://doi.org/10.5281/zenodo.18155557

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
