from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st

st.set_page_config(page_title="Purchases by Vendor", layout="wide")
px.defaults.template = "plotly_dark"

MONTH_ORDER = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
YEAR_ORDER = ["2023", "2024", "2025"]

# -------------------------
# Bulletproof paths
# -------------------------
BASE_DIR = Path(__file__).resolve().parent.parent  # .../sales_dashboard
DATA_DIR = BASE_DIR / "sales_dashboard"           # optional subfolder for CSVs
if not DATA_DIR.exists():
    DATA_DIR = BASE_DIR                           # fallback: CSVs next to app.py

PATHS = {
    "2023": DATA_DIR / "AFC PURCHASES BY VENDOR SUMMARY 2023.CSV",
    "2024": DATA_DIR / "AFC PURCHASES BY VENDOR SUMMARY 2024.CSV",
    "2025": DATA_DIR / "AFC PURCHASES BY VENDOR SUMMARY 2025.CSV",
}

# -------------------------
# Cached helpers
# -------------------------
@st.cache_data(show_spinner=False)
def load_purchases_long(paths: dict) -> pd.DataFrame:
    dfs = []
    for year, path in paths.items():
        df = pd.read_csv(path)
        df = df.rename(columns={df.columns[0]: "Vendor"})
        df = df[df["Vendor"].astype(str).str.upper() != "TOTAL"]

        month_cols = [c for c in df.columns if c not in ["Vendor", "TOTAL", "Total", "total"]]

        long_df = df.melt(
            id_vars="Vendor",
            value_vars=month_cols,
            var_name="Month",
            value_name="Purchases",
        )

        long_df["Month"] = long_df["Month"].astype(str).str[:3]
        long_df["Month"] = pd.Categorical(long_df["Month"], categories=MONTH_ORDER, ordered=True)

        long_df["Purchases"] = pd.to_numeric(long_df["Purchases"], errors="coerce").fillna(0)
        long_df["Vendor"] = long_df["Vendor"].astype(str).str.strip()
        long_df["Year"] = str(year)

        dfs.append(long_df)

    data = pd.concat(dfs, ignore_index=True)
    data = data[data["Vendor"] != ""]
    return data


@st.cache_data(show_spinner=False)
def fig_to_html_bytes(fig_json: str) -> bytes:
    fig = pio.from_json(fig_json)
    return fig.to_html(include_plotlyjs="cdn").encode("utf-8")


# -------------------------
# Load data
# -------------------------
data = load_purchases_long(PATHS)

# -------------------------
# Sidebar controls
# -------------------------
st.sidebar.header("Filters")
available_years = [y for y in YEAR_ORDER if y in set(data["Year"].unique())]
selected_year = st.sidebar.selectbox("Year", available_years, index=len(available_years)-1)
top_n = st.sidebar.slider("Top N vendors", 3, 70, 10)
enable_downloads = st.sidebar.toggle("Enable downloads (HTML only)", value=False)

# -------------------------
# Header
# -------------------------
st.title("Purchases by Vendor (2023–2025)")
st.caption("High-level view of vendor spend: concentration, top vendors, and year-over-year shifts.")

# -------------------------
# Prep: Selected-year data
# -------------------------
year_df = data[data["Year"] == selected_year].copy()

vendor_totals_year = (
    year_df.groupby("Vendor", as_index=False)["Purchases"]
    .sum()
    .sort_values("Purchases", ascending=False)
)

top_vendor = vendor_totals_year.iloc[0]["Vendor"] if len(vendor_totals_year) else "—"
top_vendor_amt = vendor_totals_year.iloc[0]["Purchases"] if len(vendor_totals_year) else 0
total_year = vendor_totals_year["Purchases"].sum()
top_vendor_share = (top_vendor_amt / total_year * 100) if total_year else 0
active_vendors = year_df["Vendor"].nunique()

top_vendors_year = vendor_totals_year.head(top_n)["Vendor"].tolist()
vendor_order_year = top_vendors_year[:]

# -------------------------
# Prep: All-years (overall)
# -------------------------
year_totals_all = data.groupby("Year", as_index=False)["Purchases"].sum()

overall_vendor_totals = (
    data.groupby("Vendor", as_index=False)["Purchases"]
    .sum()
    .sort_values("Purchases", ascending=False)
)

top_vendors_overall = overall_vendor_totals.head(top_n)["Vendor"].tolist()
vendor_order_overall = top_vendors_overall[:]

totals_by_year_vendor = (
    data[data["Vendor"].isin(top_vendors_overall)]
    .groupby(["Year", "Vendor"], as_index=False)["Purchases"]
    .sum()
)

# -------------------------
# KPI row
# -------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric(f"Total Purchases ({selected_year})", f"${total_year:,.0f}")
k2.metric("Top Vendor", top_vendor)
k3.metric("Top Vendor Share", f"{top_vendor_share:.1f}%")
k4.metric("Active Vendors", f"{active_vendors:,}")

st.divider()



# ==========================================================
# Row 1: TWO pie/donut charts side-by-side
#   - Left: Spend share (Top vendors) for selected year
#   - Right: Total purchases share by year
# ==========================================================
p1, p2 = st.columns([1, 1], gap="large")

with p1:
    pie_df = vendor_totals_year.head(top_n).copy().sort_values("Purchases", ascending=False)
    pie_df["Pull"] = 0.0
    if not pie_df.empty:
        pie_df.loc[pie_df["Purchases"].idxmax(), "Pull"] = 0.12

    fig_pie = px.pie(
        pie_df,
        names="Vendor",
        values="Purchases",
        hole=0.45,
        title=f"Spend Share by Vendor — {selected_year} (Top {top_n})",
        category_orders={"Vendor": vendor_order_year},
    )
    fig_pie.update_traces(
        pull=pie_df["Pull"],
        marker=dict(line=dict(color="white", width=2)),
        textinfo="percent",
        textfont=dict(size=14, family="Arial Black", color="white"),
    )
    fig_pie.update_layout(
        legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top"),
        margin=dict(r=140),
    )
    st.plotly_chart(fig_pie, use_container_width=True)

with p2:
    year_totals_sorted = year_totals_all.copy()
    year_totals_sorted["Pull"] = 0.0
    if not year_totals_sorted.empty:
        year_totals_sorted.loc[year_totals_sorted["Purchases"].idxmax(), "Pull"] = 0.12

    fig_year_donut = px.pie(
        year_totals_sorted,
        names="Year",
        values="Purchases",
        hole=0.50,
        title="Total Purchases Share by Year (2023–2025)",
        category_orders={"Year": YEAR_ORDER},
    )
    fig_year_donut.update_traces(
        pull=year_totals_sorted["Pull"],
        marker=dict(line=dict(color="white", width=2)),
        textinfo="percent+label",
        textfont=dict(size=14, family="Arial Black", color="white"),
    )
    st.plotly_chart(fig_year_donut, use_container_width=True)

st.divider()

# ==========================================================
# Row 2: Top vendors ranking (horizontal bars)
# ==========================================================
p3, p4 = st.columns([1,1], gap = "large")

with p3:

    rank_df = vendor_totals_year.head(top_n).sort_values("Purchases", ascending=True)

    fig_rank = px.bar(
        rank_df,
        x="Purchases",
        y="Vendor",
        orientation="h",
        title=f"Top {top_n} Vendors by Purchases — {selected_year}",
        hover_data={"Purchases": ":,.0f"},
        category_orders={"Vendor": rank_df["Vendor"].tolist()},
    )
    fig_rank.update_layout(
        xaxis_title="Purchases",
        yaxis_title="Vendor",
        margin=dict(l=10, r=10, t=60, b=10),
    )
    fig_rank.update_yaxes(autorange="reversed")
    st.plotly_chart(fig_rank, use_container_width=True)

with p4:
    
    avg_monthly_vendor = (
        year_df.groupby("Vendor", as_index=False)["Purchases"].mean()
        .rename(columns={"Purchases": "AvgMonthly"})
        .sort_values("AvgMonthly", ascending=False)
    )
    avg_top = avg_monthly_vendor[avg_monthly_vendor["Vendor"].isin(top_vendors_year)]
    avg_top = avg_top.sort_values("AvgMonthly", ascending=True)

    fig_avg_monthly = px.bar(
        avg_top,
        x="AvgMonthly",
        y="Vendor",
        orientation="h",
        title=f"Average Monthly Spend by Vendor — {selected_year} (Top {top_n})",
        hover_data={"AvgMonthly": ":,.0f"},
        category_orders={"Vendor": avg_top["Vendor"].tolist()},
    )
    fig_avg_monthly.update_yaxes(autorange="reversed")
    fig_avg_monthly.update_layout(
        xaxis_title="Avg Monthly Purchases",
        yaxis_title="Vendor",
        margin=dict(l=10, r=10, t=60, b=10),
    )
    st.plotly_chart(fig_avg_monthly, use_container_width=True)


st.divider()


# ==========================================================
# Row 4: Year comparison grouped bars (Top N overall)
# ==========================================================
fig_year_sections = px.bar(
    totals_by_year_vendor,
    x="Year",
    y="Purchases",
    color="Vendor",
    barmode="group",
    title=f"Total Purchases by Vendor for Each Year (Top {top_n} overall)",
    hover_data={"Purchases": ":,.0f"},
    category_orders={"Year": YEAR_ORDER, "Vendor": vendor_order_overall},
)
fig_year_sections.update_layout(
    xaxis_title="Year",
    yaxis_title="Total Purchases",
    legend_title="Vendor",
    bargap=0.25,
    bargroupgap=0.08,
    legend=dict(x=1.02, y=1, xanchor="left", yanchor="top"),
    margin=dict(r=180),
)
st.plotly_chart(fig_year_sections, use_container_width=True)

st.divider()

# ==========================================================
# Downloads (HTML only)
# ==========================================================
if enable_downloads:
    st.subheader("Downloads (HTML only)")

    fig_json = {
        "vendor_share": fig_pie.to_json(),
        "year_share": fig_year_donut.to_json(),
        "rank": fig_rank.to_json(),
        "avg_monthly": fig_avg_monthly.to_json(),
        "year_sections": fig_year_sections.to_json(),
    }

    d1, d2, d3 = st.columns(3)

    with d1:
        st.download_button(
            "Vendor Share (HTML)",
            data=fig_to_html_bytes(fig_json["vendor_share"]),
            file_name=f"purchases_vendor_share_{selected_year}_top{top_n}.html",
            mime="text/html",
        )
        st.download_button(
            "Year Share (HTML)",
            data=fig_to_html_bytes(fig_json["year_share"]),
            file_name="purchases_share_by_year.html",
            mime="text/html",
        )

    with d2:
        st.download_button(
            "Top Vendors (HTML)",
            data=fig_to_html_bytes(fig_json["rank"]),
            file_name=f"purchases_top_vendors_{selected_year}.html",
            mime="text/html",
        )
        st.download_button(
            "Avg Monthly (HTML)",
            data=fig_to_html_bytes(fig_json["avg_monthly"]),
            file_name=f"purchases_avg_monthly_{selected_year}_top{top_n}.html",
            mime="text/html",
        )

    with d3:
        st.download_button(
            "Variability (HTML)",
            data=fig_to_html_bytes(fig_json["variability"]),
            file_name=f"purchases_variability_{selected_year}_top{top_n}.html",
            mime="text/html",
        )
        st.download_button(
            "Year Comparison (HTML)",
            data=fig_to_html_bytes(fig_json["year_sections"]),
            file_name=f"purchases_by_vendor_each_year_top{top_n}.html",
            mime="text/html",
        )

# ==========================================================
# Underlying data (optional)
# ==========================================================
with st.expander("Show underlying data (selected year totals)"):
    st.dataframe(vendor_totals_year, use_container_width=True)
