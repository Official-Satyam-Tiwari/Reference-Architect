# BiblioAudit

[![DOI](https://zenodo.org/badge/1128307082.svg)](https://doi.org/10.5281/zenodo.18155557)
[![CI](https://github.com/Official-Satyam-Tiwari/Reference-Architect/actions/workflows/ci.yml/badge.svg)](https://github.com/Official-Satyam-Tiwari/Reference-Architect/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

BiblioAudit is a command-line tool that checks and verifies citations in BibTeX (`.bib`) files. It cross-checks references across more than 12 academic databases in parallel to confirm that entries exist, identify missing or broken DOIs, correct publication years and journal names, and locate legal open-access PDFs.

It also includes an automated re-check loop (`--loop`) that repairs metadata, generates a corrected BibTeX library via `doi2bib`, and verifies that all corrections pass validation.

---

## Example Output

```text
========================================================================
  BiblioAudit v2.2.0 - Reference Integrity & Verification System
========================================================================
  Cascading Triangulation Matrix: 12 Academic Databases

[*] Reading bibliography: References/sn-bibliography.bib
[*] Found 42 entries. Starting AUDIT...
[*] Processing 42 references (Concurrency limit: 6)...

  [VERIFIED]  (100%) Moskal2014          -> Crossref (DOI)
  [VERIFIED]  (100%) Tiwari2025          -> Crossref (DOI)
  [VERIFIED]  (100%) Spencer2021         -> Crossref (Search)
  [VERIFIED]  (100%) Tiwari_BiblioAudit  -> DataCite (DOI)
  [ATTENTION] ( 75%) Liu2021             -> Crossref (Search)
        └─ Year: BibTeX='2021' vs Record='2025'
  [NOT FOUND] (  0%) NEMA2018            -> Missing in all queried databases

============================================================
                      AUDIT SUMMARY
============================================================
  Total References Audited : 42
  Verified Clean (>90%)    :   35  ( 83.3%)
  Needs Attention          :    4  (  9.5%)
  Not Found                :    3  (  7.1%)
  Total Time Elapsed       : 12.59s
============================================================
[+] Audit CSV report saved to: References/sn-bibliography_report.csv
[+] Corrected BibTeX library saved to: References/sn-bibliography_fixed.bib
```

---

## Supported Academic Databases

BiblioAudit queries the following scientific databases in parallel:

| Database | Coverage and Specialization | Query Method |
|---|---|---|
| **Crossref** | Primary registry for journal articles, conference proceedings, and books | DOI, Title, Author |
| **DataCite** | Research datasets, software records, and Zenodo deposits | DOI, Title, Keyword |
| **OpenAlex** | Global index covering 250M+ scientific publications | DOI, Title, Author |
| **Semantic Scholar** | Multidisciplinary literature and computer science graph | DOI, Title, Author |
| **arXiv** | Preprints in physics, mathematics, and computer science | Title, Author |
| **PubMed** | Biomedical and clinical literature (NLM/NIH) | E-utilities Search |
| **Europe PMC** | Medical physics, clinical research, and European open access | REST Search, DOI |
| **DOAJ** | Peer-reviewed open access journals worldwide | Title Search |
| **HAL Open Science** | European multidisciplinary open archive (CNRS, INRIA, CEA) | Field Search |
| **Zenodo** | Open research code, software citations, and data archives | REST Records API |
| **INSPIRE HEP** | High-energy physics, astrophysics, and quantum field theory | Literature Search |
| **NASA ADS** | Astrophysics, astronomy, and planetary physics literature | Search API (optional token) |
| **Unpaywall** | Legal open-access PDF discovery | DOI lookup |
| **OpenCitations** | Citation metrics and citation network counts | COCI DOI index |

---

## Installation

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/Official-Satyam-Tiwari/Reference-Architect.git
   cd Reference-Architect
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Optional Package Install

To make the `biblioaudit` command directly available from anywhere in your terminal:
```bash
pip install -e .
```

---

## Usage

Run the tool from your terminal:

```bash
python biblioaudit.py [path-to-bib-file-or-folder] [options]
```

If you do not specify a path, BiblioAudit automatically checks files in the `References/` directory.

### Options

| Option | Description | Default |
|---|---|---|
| `-o`, `--output` | File path for the CSV report | `<filename>_audit_report.csv` |
| `--fix-bib` | File path to export corrected BibTeX entries | None |
| `--loop` | Run automated feedback loop: re-audits the corrected file and reports convergence metrics | `False` |
| `-r`, `--rate` | Maximum number of concurrent requests | `4` |
| `-v`, `--verbose` | Print field-by-field differences for mismatched citations | `False` |
| `--version` | Show program version | |
| `-h`, `--help` | Show command-line help message | |

---

## Examples

### 1. Basic Check

Check a bibliography file and print progress to the console:
```bash
python biblioaudit.py References/sn-bibliography.bib
```

### 2. Automated Re-Check Loop

Audits the original file, repairs citations via `doi2bib`, immediately re-checks the repaired file, and prints a before-and-after convergence report:
```bash
python biblioaudit.py References/sn-bibliography.bib --loop
```

### 3. Generate Reports and Corrected BibTeX

Save a detailed CSV report and write official publisher BibTeX records:
```bash
python biblioaudit.py References/sn-bibliography.bib -o report.csv --fix-bib fixed.bib
```

### 4. Fast Processing with Detailed Field Differences

Increase the request rate and print field-by-field differences for mismatched citations:
```bash
python biblioaudit.py References/sn-bibliography.bib --rate 6 --verbose
```

---

## Project Structure

```text
Reference-Architect/
├── References/              # Directory for your .bib files (ignored by git)
│   └── sn-bibliography.bib
├── biblioaudit.py           # Main runner, engines, and verification logic
├── utility.py               # Text similarity, BibTeX parsing, and CSV exports
├── requirements.txt         # Package dependencies
├── pyproject.toml           # Packaging metadata
├── CITATION.cff             # Citation metadata for GitHub
├── LICENSE                  # MIT License
└── README.md                # Documentation
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

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
