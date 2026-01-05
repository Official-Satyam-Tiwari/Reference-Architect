# 🧬 BiblioAudit: Citation Health Architect

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://streamlit.io)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**BiblioAudit** is a professional citation integrity tool designed for researchers and academics. It automatically validates BibTeX bibliographies against major academic databases (**Crossref**, **OpenAlex**, **PubMed**) to ensure metadata accuracy, fix errors, and discover Open Access PDFs.

---

## 🚀 Features

* **🔍 Multi-Engine Verification:** Triangulates citation data using Crossref, OpenAlex, and PubMed APIs to guarantee existence.
* **🧠 Smart Metadata Matching:**
    * Fuzzy matching for Titles and Authors (handles typos and formatting differences).
    * Intelligent Journal Abbreviation matching (e.g., knows that *J. Nucl. Med.* = *Journal of Nuclear Medicine*).
    * Relaxed Year checking ($\pm 1$ year tolerance).
* **📄 Open Access PDF Discovery:** Automatically finds direct download links for legal, open-access PDFs via Unpaywall.
* **🛠️ One-Click Fixes:** Generates clean, corrected BibTeX blocks for every erroneous entry, ready to copy-paste.
* **⚡ Concurrency Control:** Adjustable API speed settings to balance between performance and rate-limit safety.
* **🛡️ Manual Overrides:** Respects `verified = {true}` tags in your BibTeX to bypass checks for specific entries.

---

## 📦 Installation

### Prerequisites
* Python 3.8 or higher
* pip

### Local Setup

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/Official-Satyam-Tiwari/BiblioAudit.git](https://github.com/Official-Satyam-Tiwari/BiblioAudit.git)
    cd BiblioAudit
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

---

## 🖥️ Usage Guide

1.  **Upload:** Drag and drop your `.bib` file into the sidebar.
2.  **Configure:** Adjust the **Verification Speed** slider (keep it lower for large files to avoid API timeouts).
3.  **Audit:** Click **🚀 Start Verification**.
4.  **Review Results:**
    * **📊 Dashboard:** See high-level health metrics.
    * **⚠️ Attention Needed:** Expand cards to see side-by-side comparisons of your data vs. the official record. Use the **Suggested BibTeX** block to fix errors.
    * **❌ Unverified:** See entries that couldn't be found anywhere (with links to Google Scholar for manual checking).

---

## ⚙️ How It Works

BiblioAudit uses a tiered confidence scoring system to grade your citations:

$$ \text{Score} = \frac{\text{Matching Fields (Title, Year, Journal, Author)}}{\text{Total Fields Checked}} \times 100 $$

| Score | Status | Meaning |
| :--- | :--- | :--- |
| **90-100%** | ✅ Clean | Metadata is perfect. |
| **50-89%** | ⚠️ Warning | Entry exists, but contains typos, wrong years, or missing fields. |
| **0%** | ❌ Unverified | Paper could not be found in any supported database. |

---

## ☁️ Deployment

This app is optimized for **Streamlit Community Cloud**.

1.  Push your code to a **Private** GitHub repository.
2.  Login to [share.streamlit.io](https://share.streamlit.io).
3.  Click **New App** and select your repository.
4.  Deploy! You will get a secure, shareable URL.

> **Privacy Note:** The app runs entirely in memory. No bibliography data is stored on any server.

---

## 📂 Project Structure

```
BiblioAudit/
├── app.py              # Main UI and application entry point
├── processor.py        # Logic for orchestration and grading
├── engines.py          # API clients (Crossref, OpenAlex, PubMed)
├── utils.py            # Helper functions for string matching
└── requirements.txt    # Python dependencies
```
---

## 🤝 Contributing

Contributions are welcome! Please fork the repository and create a pull request for any feature enhancements or bug fixes.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.

---

Created by [Satyam Tiwari](https://github.com/Official-Satyam-Tiwari)
