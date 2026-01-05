# BiblioAudit 🧬

[![DOI](https://zenodo.org/badge/1128307082.svg)](https://doi.org/10.5281/zenodo.18155557)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://biblioaudit.streamlit.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

**Automated Reference Integrity & Verification System**

BiblioAudit is an open-source tool designed to "stress test" your bibliography before submission. It triangulates citations against **5 major academic databases** to verify existence, correct metadata errors (typos, wrong years), and discover open-access PDFs.

Checking references manually is tedious and error-prone. BiblioAudit automates this in seconds.

## 🚀 Key Features

* **🧠 5-Engine Verification Matrix:** Cross-checks citations against:
    * **Crossref:** Universal DOI validation.
    * **OpenAlex:** Global knowledge graph matching.
    * **PubMed:** Specialized for biomedical & life sciences.
    * **arXiv:** Preprints in Physics, Math, and CS.
    * **Semantic Scholar:** AI-driven citation ranking.
* **🔍 Smart Matching:** Uses fuzzy logic and author-specific queries to catch typos without triggering false alarms.
* **📄 PDF Discovery:** Automatically finds legal, Open Access PDF links for your references via Unpaywall.
* **📊 Visual Analytics:** View citation timelines and health metrics (Clean vs. Needs Attention) at a glance.
* **🛡️ Privacy First:** Runs entirely in your browser session. No data is stored or saved.

## 🛠️ Installation & Local Usage

You can run BiblioAudit locally on your machine.

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/Official-Satyam-Tiwari/reference-architect.git](https://github.com/Official-Satyam-Tiwari/reference-architect.git)
    cd reference-architect
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the application:**
    ```bash
    streamlit run app.py
    ```

4.  **Open in Browser:**
    The app will automatically open at `http://localhost:8501`.

## 📖 How to Use

1.  **Upload:** Drag and drop your `.bib` file into the upload area.
2.  **Configure:** Use the sidebar to adjust the **Verification Speed** (recommended: "Balanced" at 5 requests/sec).
3.  **Audit:** Click **"Start Audit"**. The tool will process entries in parallel.
4.  **Review:**
    * **Clean Citations:** Entries that matched with high confidence (>90%).
    * **Needs Attention:** Entries where the Year, Journal, or Title didn't match the official record perfectly.
    * **Not Found:** Entries that failed verification. Use the auto-generated **Google Scholar** links to check them manually.
5.  **Export:** Download the full audit report as a CSV file to share with co-authors.

## 📄 Citation

If you use BiblioAudit in your research workflow, please cite it using the metadata below:

> **Tiwari, S. (2025). BiblioAudit: Automated Citation Integrity & Verification Tool (Version 2.1.0) [Software]. Zenodo. https://doi.org/10.5281/zenodo.18155557**

**BibTeX:**
```bibtex
@software{Tiwari_BiblioAudit_2025,
  author = {Tiwari, Satyam},
  title = {{BiblioAudit: Automated Citation Integrity & Verification Tool}},
  version = {2.1.0},
  year = {2025},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.18155557},
  url = {[https://doi.org/10.5281/zenodo.18155557](https://doi.org/10.5281/zenodo.18155557)}
}
