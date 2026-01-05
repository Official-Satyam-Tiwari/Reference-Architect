import streamlit as st
import bibtexparser
import asyncio
import aiohttp
import pandas as pd
import urllib.parse
from processor import process_entry
from utils import format_source_name, make_bibtex

# ==========================================================
# 🎨 UI CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title="BiblioAudit",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stExpander {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 10px;
    }
    h1 { font-family: 'Helvetica Neue', sans-serif; font-weight: 700; color: #2c3e50; }
    .stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# 🖥️ SIDEBAR & HEADER
# ==========================================================

with st.sidebar:
    st.title("Settings")
    uploaded_file = st.file_uploader("Upload .bib file", type="bib")
    st.markdown("---")
    
    concurrency = st.slider("Verification Speed", 1, 10, 1)
    st.caption("Lower speed (1-3) is safer for large files to avoid API timeouts.")
    
    st.markdown("---")
    st.markdown("**Created by:**")
    st.markdown("[Satyam Tiwari](https://github.com/Official-Satyam-Tiwari)")

st.title("BiblioAudit 🧬")
st.info("""
**Reference Integrity System**

This tool validates bibliography against **Crossref, OpenAlex, and PubMed**.
It ensures citation existence, metadata accuracy, and discovers **Open Access PDFs**.

**Confidence Score:**
$$ \\text{Score} = \\frac{\\text{Matching Fields (Title, Year, Journal, Author)}}{\\text{Total Fields Present}} \\times 100 $$
""")

# ==========================================================
# 🚀 MAIN LOGIC
# ==========================================================

if uploaded_file:
    try:
        bib_str = uploaded_file.getvalue().decode("utf-8")
        library = bibtexparser.loads(bib_str)
    except Exception as e:
        st.error(f"Error parsing BibTeX file: {e}")
        st.stop()
    
    if st.button("🚀 Audit References", type="primary"):
        status_box = st.status("Initializing verification protocols...", expanded=True)
        progress_bar = status_box.progress(0)
        
        sem = asyncio.Semaphore(concurrency)
        
        async def run_audit():
            tasks = [process_entry(e, aiohttp.ClientSession(), sem) for e in library.entries]
            results = []
            async with aiohttp.ClientSession() as session:
                tasks = [process_entry(e, session, sem) for e in library.entries]
                for i, coro in enumerate(asyncio.as_completed(tasks)):
                    res = await coro
                    results.append(res)
                    progress_bar.progress((i + 1) / len(tasks))
                    status_box.update(label=f"Scanning: {res['key']}")
            return results

        results = asyncio.run(run_audit())
        status_box.update(label="✅ Audit Complete!", state="complete", expanded=False)
        st.toast("Verification successful!", icon="🎉")
        
        # --- DATA PROCESSING ---
        df_rows = []
        clean, needs_work, missing = [], [], []
        
        for r in results:
            if r["confidence"] >= 90: clean.append(r)
            elif r["exists"]: needs_work.append(r)
            else: missing.append(r)
            
            df_rows.append({
                "Key": r["key"], "Source": format_source_name(r["resolution"]),
                "DOI Link": r["doi_url"], 
                "PDF": r["pdf_link"],
                "Confidence": r["confidence"],
                "Status": "✅" if r["confidence"] >= 90 else "⚠️" if r["exists"] else "❌"
            })
        
        needs_work.sort(key=lambda x: x['confidence'], reverse=True)
        df = pd.DataFrame(df_rows)
        
        # --- TABS ---
        tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "⚠️ Attention Needed", "❌ Unverified"])
        
        with tab1:
            col1, col2, col3 = st.columns(3)
            col1.metric("Verified Clean", len(clean), delta_color="normal")
            col2.metric("Attention Needed", len(needs_work), delta_color="inverse")
            col3.metric("Unverified", len(missing), delta_color="inverse")
            
            st.dataframe(
                df,
                column_config={
                    "DOI Link": st.column_config.LinkColumn("DOI", display_text="Source"),
                    "PDF": st.column_config.LinkColumn("PDF", display_text="Download"),
                    "Confidence": st.column_config.ProgressColumn("Score", format="%d%%", min_value=0, max_value=100),
                },
                use_container_width=True, hide_index=True
            )

        with tab2:
            st.warning(f"{len(needs_work)} entries require review (Sorted by Confidence).")
            for r in needs_work:
                with st.expander(f"{r['key']} ({r['confidence']}%)"):
                    # Links
                    links = []
                    if r.get("doi_url"): links.append(f"[🔗 Source]({r['doi_url']})")
                    if r.get("pdf_link"): links.append(f"[📄 PDF]({r['pdf_link']})")
                    if links: st.markdown(" | ".join(links))

                    if not r.get("field_check"):
                        st.info("ℹ️ Metadata sync timed out. Manually verify using the link above.")
                    else:
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown("#### 📝 BibTeX")
                            for f, chk in r.get("field_check", {}).items():
                                if chk["status"] != "ok": st.markdown(f"**{f.capitalize()}**: `{chk['bibtex']}`")
                        with c2:
                            st.markdown("#### ✅ Official")
                            for f, chk in r.get("field_check", {}).items():
                                if chk["status"] != "ok": st.markdown(f"**{f.capitalize()}**: `{chk['correct']}`")
                        
                        st.markdown("---")
                        st.markdown("#### 📋 Suggested BibTeX")
                        st.code(make_bibtex(r['key'], r.get('clean_data')), language="latex")

        with tab3:
            st.error(f"{len(missing)} entries not found.")
            for r in missing:
                q = urllib.parse.quote(r.get('field_check', {}).get('title', {}).get('bibtex', ''))
                s_url = f"https://scholar.google.com/scholar?q={q}"
                
                with st.container():
                    c1, c2 = st.columns([0.8, 0.2])
                    c1.code(f"@{r.get('entry_type', 'misc')}{{{r['key']}}}", language="tex")
                    if q: c2.link_button("🔍 Search", s_url)