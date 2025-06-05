import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path

st.set_page_config(page_title="Swedish Cyber-Incident Dashboard", layout="wide")

FILES = {
    "industry": "industry.csv",
    "region": "regions.csv",
    "size_s": "S-enterprises.csv",
    "size_ml": "M-L-enterprises.csv",
}

@st.cache_data(show_spinner=False)
def load_all() -> dict[str, pd.DataFrame]:
    dfs = {}
    for key, fname in FILES.items():
        path = Path(__file__).parent / fname
        if not path.exists():
            st.error(f"{fname} missing")
            st.stop()

        df = pd.read_csv(
            path,
            sep=";",
            dtype=str,
            encoding="cp1252",
            skiprows=1,
        )
        df.columns = [
            "incident_type",
            "domain",
            "share_2021",
            "share_2023",
            "moe_2021",
            "moe_2023",
        ]
        df[["share_2021", "share_2023", "moe_2021", "moe_2023"]] = df[
            ["share_2021", "share_2023", "moe_2021", "moe_2023"]
        ].apply(pd.to_numeric, errors="coerce")
        dfs[key] = df

    return dfs

dfs = load_all()

st.sidebar.title("Filters")
dimension = st.sidebar.radio(
    "Domain type",
    options=["industry", "size", "region"],
    index=0,
)

if dimension == "industry":
    df_dim = dfs["industry"]
elif dimension == "region":
    df_dim = dfs["region"]
else:  # size -> combine the two size files
    df_dim = pd.concat([dfs["size_s"], dfs["size_ml"]], ignore_index=True)

domain_list = sorted(df_dim["domain"].unique())
domain = st.sidebar.selectbox("Domain value", options=domain_list)

compare_sweden = st.sidebar.checkbox("Compare to Sweden average", value=False)
year_selected = st.sidebar.radio("Year", [2023, 2021], index=0, format_func=str)

df_sel = df_dim[df_dim["domain"] == domain]

if compare_sweden:
    df_sweden = df_dim[df_dim["domain"] == "Sweden"].copy()
    df_sweden["domain"] = "Sweden"
    plot_df = pd.concat([df_sel, df_sweden], ignore_index=True)
else:
    plot_df = df_sel.copy()

share_col = f"share_{year_selected}"
prev_col = "share_2021" if year_selected == 2023 else "share_2023"

st.title("Swedish Cyber-Incident Statistics")
st.subheader(f"{dimension.capitalize()}: {domain}")

kpi, _ = st.columns([1, 5])
with kpi:
    cur = df_sel[share_col].mean()
    prev = df_sel[prev_col].mean()
    st.metric(
        label=f"Average share of enterprises ({year_selected})",
        value=f"{cur:.1f} %",
        delta=f"{cur - prev:+.1f} pp",
    )

bar = (
    alt.Chart(plot_df)
    .mark_bar()
    .encode(
        y=alt.Y("incident_type:N", sort="-x"),
        x=alt.X(f"{share_col}:Q", title="Share (%)"),
        color=alt.Color(
            "domain:N",
            legend=None if not compare_sweden else alt.Legend(title="Domain"),
        ),
        tooltip=["domain", "incident_type", share_col],
    )
    .properties(height=400)
)
st.altair_chart(bar, use_container_width=True)

trend = (
    plot_df.melt(
        id_vars=["incident_type", "domain"],
        value_vars=["share_2021", "share_2023"],
        var_name="year",
        value_name="share",
    )
)
trend["year"] = trend["year"].str.extract(r"(\d{4})").astype(int)

line = (
    alt.Chart(trend)
    .mark_line(point=True)
    .encode(
        x=alt.X("year:O"),
        y=alt.Y("share:Q", title="Share (%)"),
        color=alt.Color(
            "domain:N",
            legend=None if not compare_sweden else alt.Legend(title="Domain"),
        ),
        strokeDash="domain:N",
        tooltip=["domain", "incident_type", "year", "share"],
    )
    .properties(height=300)
)
st.altair_chart(line, use_container_width=True)

with st.expander("Raw numbers"):
    st.dataframe(
        df_sel.set_index("incident_type")[
            ["share_2021", "moe_2021", "share_2023", "moe_2023"]
        ],
        use_container_width=True,
    )
    st.download_button(
        "Download CSV",
        data=df_sel.to_csv(index=False, sep=";").encode("cp1252"),
        file_name=f"{dimension}_{domain.replace(' ', '_')}.csv",
        mime="text/csv",
    )
