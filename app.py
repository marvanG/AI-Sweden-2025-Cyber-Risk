import streamlit as st
import pandas as pd
import altair as alt
import numpy as np  # v3
from pathlib import Path

st.set_page_config(page_title="Swedish Cyber‑Incident Dashboard", layout="wide")

# -----------------------------------------------------------------------------
# 1. DATA LOADING – FOUR SEPARATE DATAFRAMES  (v1)
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_all() -> dict[str, pd.DataFrame]:  # v1
    """Read each CSV separately with correct encoding and return a dict of DataFrames."""
    files = {
        "industry": "industry.csv",
        "region": "regions.csv",
        "size_s": "S-enterprises.csv",
        "size_ml": "M-L-enterprises.csv",
    }
    dfs: dict[str, pd.DataFrame] = {}
    for key, fname in files.items():
        path = Path(__file__).parent / fname
        if not path.exists():
            st.error(f"Missing {fname}. Place all CSVs next to app.py and restart.")
            st.stop()
        df = pd.read_csv(path, sep=";", dtype=str, encoding="cp1252", skiprows=1)
        df.columns = [
            "incident_type",
            "domain",
            "share_2021",
            "share_2023",
            "moe_2021",
            "moe_2023",
        ]
        num_cols = ["share_2021", "share_2023", "moe_2021", "moe_2023"]
        df[num_cols] = df[num_cols].apply(pd.to_numeric, errors="coerce")
        dfs[key] = df
    return dfs

# -----------------------------------------------------------------------------
# 2. GLOBAL PRE‑COMPUTATIONS  (v1 & v4)
# -----------------------------------------------------------------------------

dfs = load_all()

df_global = pd.concat(dfs.values(), ignore_index=True)
df_global["delta"] = df_global["share_2023"] - df_global["share_2021"]

# v4: compute overall max share to use as fixed X‑axis limit
MAX_SHARE = df_global[["share_2021", "share_2023"]].max().max()

abs_top5 = df_global.loc[
    df_global["delta"].abs().sort_values(ascending=False).head(5).index
][[
    "incident_type",
    "domain",
    "share_2021",
    "share_2023",
    "delta",
]]

# -----------------------------------------------------------------------------
# 3. SIDEBAR FILTERS – DIMENSION, DOMAIN, YEAR  (v2)
# -----------------------------------------------------------------------------

st.sidebar.title("Filters")

dimension = st.sidebar.radio("Domain type", ["industry", "size", "region"], index=0)

if dimension == "industry":
    df_dim = dfs["industry"].copy()
elif dimension == "region":
    df_dim = dfs["region"].copy()
else:  # size
    df_dim = pd.concat([dfs["size_s"], dfs["size_ml"]], ignore_index=True)

year_choice = st.sidebar.radio("Year", [2023, 2021, "Average"], index=0, format_func=str)

options = sorted(df_dim["domain"].unique())
if dimension == "industry":
    default_value = "Total (SNI 10-63, 68-75, 77-82, 95.1)"
elif dimension == "size":
    default_value = "10 or more employees in total"
else:
    default_value = "Sweden"

domain = st.sidebar.selectbox("Domain value", options=options, index=options.index(default_value) if default_value in options else 0)

df_sel = df_dim[df_dim["domain"] == domain].copy()

# -----------------------------------------------------------------------------
# 4. CURRENT VIEW – KPI, BAR, PIE  (v3 + v4)
# -----------------------------------------------------------------------------

if year_choice == "Average":
    df_sel["current_share"] = df_sel[["share_2021", "share_2023"]].mean(axis=1)
    share_label = "Average of 2021 & 2023"
else:
    df_sel["current_share"] = df_sel[f"share_{year_choice}"]
    share_label = str(year_choice)

cumulative = df_sel["current_share"].sum(skipna=True)

st.title("Swedish Cyber‑Incident Statistics")
st.subheader(f"{dimension.capitalize()}: {domain}")

st.markdown(
    f"**Total share of enterprises affected ({share_label})**: "
    f"<span style='font-size:48px;font-weight:bold'>{cumulative:.1f}%</span>",
    unsafe_allow_html=True,
)

# v3: differentiate 0 % vs missing data

df_sel["current_share_filled"] = df_sel["current_share"].fillna(0.1)
df_sel["status"] = np.where(df_sel["current_share"].isna(), "Data unavailable", "Reported")

# v4: fixed X‑axis scale using overall MAX_SHARE
bar_chart = (
    alt.Chart(df_sel)
    .mark_bar()
    .encode(
        y=alt.Y("incident_type:N", sort="-x", title="Incident type"),
        x=alt.X(
            "current_share_filled:Q",
            title="Share (%)",
            scale=alt.Scale(domain=[0, MAX_SHARE + 1]),  # v4 fixed scale
        ),
        color=alt.Color(
            "status:N",
            scale=alt.Scale(domain=["Reported", "Data unavailable"], range=["#1f77b4", "#cccccc"]),
            legend=alt.Legend(title=""),
        ),
        tooltip=[
            "incident_type:N",
            alt.Tooltip("current_share_filled:Q", title="Share (%)", format=".1f"),
            "status:N",
        ],
    )
    .properties(height=400)
)
st.altair_chart(bar_chart, use_container_width=True)

# Pie chart unchanged – only uses available data
pie_chart = (
    alt.Chart(df_sel[df_sel["status"] == "Reported"])
    .mark_arc()
    .encode(
        theta="current_share_filled:Q",
        color="incident_type:N",
        tooltip=["incident_type", "current_share_filled"],
    )
    .properties(height=300)
)
st.altair_chart(pie_chart, use_container_width=True)

# -----------------------------------------------------------------------------
# 5. STATIC TOP‑5 DELTAS (2021 → 2023) ACROSS ENTIRE SURVEY  (v1)
# -----------------------------------------------------------------------------
with st.expander("📈 Top 5 largest year‑on‑year changes across Sweden (static)"):
    st.dataframe(abs_top5, use_container_width=True)
    delta_bar = (
        alt.Chart(abs_top5)
        .mark_bar()
        .encode(
            y=alt.Y("incident_type:N", sort="-x", title=""),
            x=alt.X("delta:Q", title="Δ (pp)"),
            color=alt.condition(alt.datum.delta > 0, alt.value("#d62728"), alt.value("#1f77b4")),
            tooltip=["domain", "incident_type", "delta"],
        )
        .properties(height=300)
    )
    st.altair_chart(delta_bar, use_container_width=True)

# -----------------------------------------------------------------------------
# 6. RAW NUMBERS EXPANDER  (v1)
# -----------------------------------------------------------------------------
with st.expander("Raw numbers"):
    st.dataframe(
        df_sel.set_index("incident_type")[["share_2021", "moe_2021", "share_2023", "moe_2023"]],
        use_container_width=True,
    )
    st.download_button(
        "Download CSV",
        data=df_sel.to_csv(index=False, sep=";", encoding="cp1252").encode("cp1252"),
        file_name=f"{dimension}_{domain.replace(' ', '_')}.csv",
        mime="text/csv",
    )

# -----------------------------------------------------------------------------
# 7. ABOUT EXPANDER  (v1)
# -----------------------------------------------------------------------------
with st.expander("About"):
    st.markdown("Data source: *SCB – IT‑relaterade säkerhetsincidenter*, survey years 2021 & 2023.")
