import streamlit as st
import bibtexparser
import asyncio
import aiohttp
import pandas as pd
import urllib.parse
from processor import process_entry
from utils import format_source_name, make_bibtex, to_csv
import plotly.express as px

# ==========================================================
# 🎨 PAGE & THEME CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title="BiblioAudit",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Professional Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        border-right: 1px solid #e2e8f0;
    }
    
    /* Make File Uploader Bigger & Centered */
    [data-testid='stFileUploader'] {
        width: 100%;
    }
    [data-testid='stFileUploader'] section {
        padding: 30px;
        border: 2px dashed #cbd5e1;
        border-radius: 12px;
    }
    [data-testid='stFileUploader'] section:hover {
        border-color: #6366f1;
    }

    /* Metric Cards Styling */
    div[data-testid="metric-container"] {
        border: 1px solid #e2e8f0;
        padding: 15px 20px;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    /* Custom Header */
    h1 { color: #0f172a; font-weight: 700; letter-spacing: -0.5px; }
    h2, h3 { color: #334155; }
    
    /* Buttons */
    div.stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# 🖥️ SIDEBAR (REDESIGNED)
# ==========================================================

with st.sidebar:
    st.markdown("## 🎛️ Control Panel")
    
    # 1. Performance Settings
    with st.expander("⚙️ Engine Settings", expanded=True):
        st.markdown("**Verification Speed**")
        concurrency = st.select_slider(
            "Requests per second",
            options=[1, 2, 3, 5, 8, 10],
            value=1,
            help="Higher speeds process files faster but increase the risk of API timeouts."
        )
        
        # Dynamic Status Indicator
        if concurrency <= 3:
            st.caption("🟢 **Safe Mode:** Best for reliability.")
        elif concurrency <= 5:
            st.caption("🟡 **Balanced:** Recommended.")
        else:
            st.caption("🔴 **Turbo:** High risk of rate-limits.")

    st.divider()

    # 2. System Intelligence (Professional List)
    st.markdown("### 📡 Active Databases")
    st.markdown("""
    <div style="padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; font-size: 0.85rem; color: #FFFFFF;">
        <ul style="margin: 0; padding-left: 1.2rem;">
            <li><b>Crossref</b> (Universal DOIs)</li>
            <li><b>OpenAlex</b> (Knowledge Graph)</li>
            <li><b>PubMed</b> (Biomedical)</li>
            <li><b>arXiv</b> (Preprints)</li>
            <li><b>Semantic Scholar</b> (AI)</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # 3. Help / Footer
    st.markdown("### 🆘 Help & Support")
    st.markdown("""
    <div style="font-size: 0.85rem; color: #64748b; line-height: 1.6;">
    If a verification fails, the system auto-retries with backup engines. For persistent issues, try lowering the speed slider.
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("") # Spacer
    st.markdown("**Version:** `2.1.0`")
    st.markdown("[View on GitHub ↗](https://github.com/Official-Satyam-Tiwari)")

# ==========================================================
# 🚀 MAIN CONTENT
# ==========================================================

st.title("BiblioAudit 🧬")
st.markdown("#### The Professional Citation Integrity Architect")

# Initialize Session State
if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None

uploaded_file = st.file_uploader("Upload Bibliography (.bib)", type="bib", key="main_uploader")

if not uploaded_file:
    st.info("☝ Upload your `.bib` file above to begin the audit.")

if uploaded_file:
    try:
        bib_str = uploaded_file.getvalue().decode("utf-8")
        library = bibtexparser.loads(bib_str)
        entry_count = len(library.entries)
    except Exception as e:
        st.error(f"❌ Error parsing BibTeX file: {e}")
        st.stop()
    
    # Pre-run statistics
    col1, col2 = st.columns([3, 1])
    with col1:
        st.success(f"📂 File loaded successfully. Found **{entry_count}** citations ready for verification.")
    with col2:
        start_btn = st.button("🚀 Start Audit", type="primary", use_container_width=True)
    
    if start_btn:
        with st.status("🔍 Running Verification Protocols...", expanded=True) as status_box:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            sem = asyncio.Semaphore(concurrency)
            
            async def run_audit():
                tasks = [process_entry(e, aiohttp.ClientSession(), sem) for e in library.entries]
                results = []
                async with aiohttp.ClientSession() as session:
                    tasks = [process_entry(e, session, sem) for e in library.entries]
                    for i, coro in enumerate(asyncio.as_completed(tasks)):
                        res = await coro
                        results.append(res)
                        progress = (i + 1) / len(tasks)
                        progress_bar.progress(progress)
                        if i % 5 == 0: 
                            status_text.text(f"Verifying: {res.get('key', 'Unknown')} ({int(progress*100)}%)")
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
            
            source_name = format_source_name(r.get("resolution"))
            
            df_rows.append({
                "Key": r["key"], 
                "Source": source_name,
                "Link": r["doi_url"], 
                "PDF": r["pdf_link"],
                "Score": r["confidence"],
                "Status": "✅" if r["confidence"] >= 90 else "⚠️" if r["exists"] else "❌"
            })
        
        needs_work.sort(key=lambda x: x['confidence'], reverse=True)
        df = pd.DataFrame(df_rows)
        
        # --- DASHBOARD UI ---
        st.markdown("### 📊 Audit Report")
        
        m1, m2, m3, m4 = st.columns([1,1,1,1])
        with m1: st.metric("Verified Clean", len(clean))
        with m2: st.metric("Needs Attention", len(needs_work))
        with m3: st.metric("Not Found", len(missing))
        with m4: 
            st.write("") 
            st.download_button(
                label="📥 Download CSV Report", 
                data=to_csv(results), 
                file_name="biblio_audit_report.csv", 
                mime="text/csv",
                type="secondary",
                use_container_width=True
            )

        st.markdown("---")

        tab1, tab2, tab3 = st.tabs(["📈 Analytics & Clean Data", "⚠️ Attention Needed", "❌ Unverified"])
        
        with tab1:
            row1_col1, row1_col2 = st.columns([2, 1])
            with row1_col1:
                st.markdown("#### Clean Citations")
                st.dataframe(
                    df[df["Score"] >= 90],
                    column_config={
                        "Link": st.column_config.LinkColumn("Source", display_text="Open"),
                        "PDF": st.column_config.LinkColumn("PDF", display_text="Download"),
                        "Score": st.column_config.ProgressColumn("Confidence", format="%d%%", min_value=0, max_value=100),
                    },
                    use_container_width=True, hide_index=True, height=400
                )
            with row1_col2:
                st.markdown("#### Citation Timeline")
                years = [int(r['clean_data']['year']) for r in results if r.get('clean_data') and r['clean_data'].get('year')]
                if years:
                    year_counts = pd.Series(years).value_counts().reset_index()
                    year_counts.columns = ['Year', 'Count']
                    fig = px.bar(year_counts, x='Year', y='Count')
                    fig.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=350)
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.info("No date data available.")

        with tab2:
            st.warning(f"Found **{len(needs_work)}** entries with potential issues (Sorted by Confidence).")
            for r in needs_work:
                source_display = format_source_name(r.get("resolution"))
                with st.expander(f"{r['key']} ({r['confidence']}%) - Found via {source_display}"):
                    col_links, col_status = st.columns([3, 1])
                    with col_links:
                        links = []
                        if r.get("doi_url"): links.append(f"[🔗 Source]({r['doi_url']})")
                        if r.get("pdf_link"): links.append(f"[📄 PDF]({r['pdf_link']})")
                        if links: st.markdown(" | ".join(links))
                    st.divider()
                    if not r.get("field_check"):
                        st.info("ℹ️ Metadata sync timed out. Manually verify using the link above.")
                    else:
                        c1, c2 = st.columns(2)
                        with c1:
                            st.caption("YOUR BIBTEX")
                            for f, chk in r.get("field_check", {}).items():
                                if chk["status"] != "ok": 
                                    st.markdown(f"**{f.capitalize()}**: `{chk['bibtex']}`")
                        with c2:
                            st.caption("OFFICIAL RECORD")
                            for f, chk in r.get("field_check", {}).items():
                                if chk["status"] != "ok": 
                                    st.markdown(f"**{f.capitalize()}**: :green[`{chk['correct']}`]")
                        st.markdown("---")
                        st.markdown("#### 📋 Suggested Fix")
                        st.code(make_bibtex(r['key'], r.get('clean_data')), language="latex")

        with tab3:
            st.error(f"**{len(missing)}** entries could not be found in any database.")
            st.markdown("Use the links below to manually search Google Scholar.")
            for r in missing:
                field_check = r.get('field_check', {})
                title_data = field_check.get('title', {}) if field_check else {}
                title_text = title_data.get('bibtex', '') if title_data else r.get('key', '')
                q = urllib.parse.quote(title_text)
                s_url = f"https://scholar.google.com/scholar?q={q}"
                with st.container():
                    c1, c2 = st.columns([0.8, 0.2])
                    with c1:
                        st.code(f"@{r.get('entry_type', 'misc')}{{{r['key']}}}", language="tex")
                    with c2:
                        st.link_button("🔍 Google Scholar", s_url)