"""Streamlit front-end for the Analytics Chat application."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path so `app.*` imports resolve
# regardless of where Streamlit is launched from.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from app.config import get_config
from app.db import Database
from app.main import run_analysis
from app.utils import setup_logging

setup_logging()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Analytics Chat",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Analytics Chat")
st.caption("Ask natural-language questions about your PostgreSQL data.")

# ---------------------------------------------------------------------------
# Initialise configuration & DB connection (cached across reruns)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _get_db() -> Database:
    cfg = get_config()
    return Database(cfg)


config = get_config()
db = _get_db()

# ---------------------------------------------------------------------------
# Sidebar – connection status, schema & table selection
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Database")

    connected = db.test_connection()
    if connected:
        st.success("Connected to PostgreSQL")
    else:
        st.error("Cannot connect to PostgreSQL – check your .env")
        st.stop()

    schemas = db.list_schemas()
    selected_schema = st.selectbox("Schema", schemas, index=schemas.index("public") if "public" in schemas else 0)

    tables = db.list_tables(selected_schema)
    if not tables:
        st.warning("No tables found in this schema.")
        st.stop()

    selected_tables = st.multiselect("Tables", tables, default=tables[:1])

    if selected_tables and st.button("Preview selected schemas"):
        from app.schema_service import SchemaService
        schema_svc = SchemaService(db, config)
        for tbl in selected_tables:
            meta = schema_svc.get_table_meta(selected_schema, tbl)
            with st.expander(f"{selected_schema}.{tbl}", expanded=True):
                cols_info = []
                for c in meta.columns:
                    pk = " 🔑" if c.is_primary_key else ""
                    null = " (nullable)" if c.is_nullable else ""
                    cols_info.append(f"- **{c.column_name}** `{c.data_type}`{pk}{null}")
                st.markdown("\n".join(cols_info))
                if meta.foreign_keys:
                    st.markdown("**Foreign keys:**")
                    for fk in meta.foreign_keys:
                        st.markdown(
                            f"- {fk.column_name} → {fk.foreign_table_schema}.{fk.foreign_table_name}.{fk.foreign_column_name}"
                        )
                if meta.row_count_estimate is not None:
                    st.markdown(f"**Estimated rows:** {meta.row_count_estimate:,}")

# ---------------------------------------------------------------------------
# Main area – question input & analysis
# ---------------------------------------------------------------------------
question = st.text_area(
    "Ask an analytics question",
    placeholder="e.g. What are the top 10 customers by total revenue last quarter?",
    height=100,
)

run_btn = st.button("Run Analysis", type="primary", disabled=not selected_tables)

if run_btn and question.strip():
    table_pairs = [(selected_schema, t) for t in selected_tables]

    with st.spinner("Generating analysis…"):
        try:
            response = run_analysis(question, table_pairs, config)
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")
            st.stop()

    # --- Warnings / Assumptions banner ---
    if response.warnings:
        with st.expander("⚠️ Warnings", expanded=True):
            for w in response.warnings:
                st.warning(w)

    if response.assumptions:
        with st.expander("📌 Assumptions", expanded=True):
            for a in response.assumptions:
                st.info(a)

    if not response.success:
        st.error(f"Query execution failed: {response.error}")

    # --- Tabbed results ---
    tab_answer, tab_table, tab_sql, tab_code, tab_viz, tab_viz_code, tab_meta = st.tabs(
        ["Answer", "Table", "SQL", "Analysis Code", "Visualization", "Viz Code", "Metadata"]
    )

    with tab_answer:
        st.subheader("Analysis Summary")
        st.markdown(response.analysis_summary)
        if response.result_interpretation:
            st.subheader("Result Interpretation")
            st.markdown(response.result_interpretation)

    with tab_table:
        if response.df is not None:
            st.dataframe(response.df, use_container_width=True)
            if response.query_result and response.query_result.truncated:
                st.caption(
                    f"Showing {len(response.df)} of {response.query_result.row_count} rows."
                )
        else:
            st.info("No result data available.")

    with tab_sql:
        st.code(response.sql, language="sql")

    with tab_code:
        st.code(response.python_analysis_code, language="python")

    with tab_viz:
        if response.figure:
            st.plotly_chart(response.figure, use_container_width=True)
        else:
            st.info("No visualization for this query.")

    with tab_viz_code:
        if response.visualization_code:
            st.code(response.visualization_code, language="python")
        else:
            st.info("No visualization code generated.")

    with tab_meta:
        if response.metadata:
            st.json(response.metadata.model_dump(mode="json"))
        if response.artifacts_path:
            st.caption(f"Artifacts saved to: `{response.artifacts_path}`")
        if response.query_result:
            st.metric("Execution time", f"{response.query_result.execution_time_ms:.1f} ms")
            st.metric("Rows returned", response.query_result.row_count)

elif run_btn:
    st.warning("Please enter a question first.")
