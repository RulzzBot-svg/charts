import csv
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio
import plotly.graph_objects as go
import streamlit as st


# -------------------------
# Paths / Config
# -------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent  # sales_dashboard root

st.set_page_config(page_title="AFC Sales by Item (SKU)", layout="wide")

# Match your global style
px.defaults.template = "seaborn"

MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
YEAR_ORDER = ["2023", "2024", "2025"]

FILES = {
    "2023": DATA_DIR / "AFC SALES BY ITEM SUMMARY 2023.CSV",
    "2024": DATA_DIR / "AFC SALES BY ITEM SUMMARY 2024.CSV",
    "2025": DATA_DIR / "AFC SALES BY ITEM SUMMARY 2025.CSV",
}

# QuickBooks grouping / subtotal labels we do NOT want treated as SKUs
GROUP_HEADERS_EXACT = {
    "uncategorized",
    "inventory",
    "parts",
    "other charges",
}

def is_group_or_total_row(label: str) -> bool:
    s = str(label or "").strip()
    low = s.lower()

    if not s:
        return True

    # Drop grouping buckets (like your screenshot)
    if low in GROUP_HEADERS_EXACT:
        return True

    # Drop totals/subtotals
    if low == "total" or low == "grand total":
        return True
    if low.startswith("total "):
        return True
    if "subtotal" in low:
        return True

    # Some QB exports add these
    if low in {"items", "item", "name", "description"}:
        return True

    return False


# -------------------------
# Cached helper for HTML downloads
# -------------------------
@st.cache_data(show_spinner=False)
def fig_to_html_bytes(fig_json: str) -> bytes:
    fig = pio.from_json(fig_json)
    return fig.to_html(include_plotlyjs="cdn").encode("utf-8")


# -------------------------
# Parsing helpers (simple + robust)
# -------------------------
def _clean_money(x):
    if x is None:
        return 0.0
    s = str(x).strip()
    if s in ("", "-", "—"):
        return 0.0
    s = s.replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _month3(x):
    s = str(x).strip()
    m = s[:3].title()
    return m if m in MONTH_ORDER else ""





@st.cache_data(show_spinner=False)
def parse_qb_sales_by_item_summary(path: str, year: str) -> pd.DataFrame:
    """
    Minimal, robust parser for QuickBooks 'Sales by Item Summary' exports.
    Extracts: Item | Year | Month | Qty | Amount
    Uses csv.reader so ragged rows won't crash pandas.
    Filters out QB grouping rows & total rows so you only get the real item lines.
    """
    rows = None
    last_err = None

    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin1"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                rows = list(csv.reader(f))
            break
        except Exception as e:
            last_err = e
            continue

    if not rows or len(rows) < 3:
        st.error(f"Could not read {Path(path).name}. Last error: {last_err}")
        st.stop()

    header_month = rows[0]
    header_metric = rows[1]

    # map column -> month (carry forward)
    col_month = {}
    metric_len = len(header_metric)
    month_len = len(header_month)

    # QB format in your file:
    # row0 has 14 cols (blank + 12 months + TOTAL)
    # row1 has 53 cols = 1 + 13 * 4 (4 metrics per month block)
    if metric_len == 1 + (month_len - 1) * 4:
        # block mapping: each month header corresponds to 4 metric columns
        for j, mlabel in enumerate(header_month[1:]):  # skip first blank cell
            m = _month3(mlabel)
            start = 1 + j * 4
            for c in range(start, min(start + 4, metric_len)):
                col_month[c] = m  # m will be "" for TOTAL (we’ll ignore it later)
    else:
        # fallback: old carry-forward method (for other QB variants)
        current = ""
        for c in range(1, metric_len):
            if c < month_len:
                m = _month3(header_month[c])
                if m:
                    current = m
            col_month[c] = current

    def is_qty(s):
        return "qty" in str(s).lower()

    def is_amt(s):
        s = str(s).lower()
        return ("amount" in s) or ("total" in s)

    qty_col = {}
    amt_col = {}
    for c in range(1, len(header_metric)):
        m = col_month.get(c)
        if not m:
            continue
        if is_qty(header_metric[c]):
            qty_col[m] = c
        elif is_amt(header_metric[c]):
            amt_col[m] = c

    records = []
    for r in rows[2:]:
        if not r:
            continue

        item = r[0].strip() if len(r) > 0 else ""

        # Drop QB group headings / totals (this is the “umbrella” problem)
        if is_group_or_total_row(item) or item.upper() == "TOTAL":
            continue

        for m in MONTH_ORDER:
            qc = qty_col.get(m)
            ac = amt_col.get(m)

            qty = _clean_money(r[qc]) if qc is not None and qc < len(r) else 0.0
            amt = _clean_money(r[ac]) if ac is not None and ac < len(r) else 0.0

            if qty != 0 or amt != 0:
                records.append({"Item": item, "Year": year, "Month": m, "Qty": qty, "Amount": amt})

    df = pd.DataFrame(records)
    if df.empty:
        return df

    df["Month"] = pd.Categorical(df["Month"], categories=MONTH_ORDER, ordered=True)
    return df.sort_values(["Year", "Month", "Amount"], ascending=[True, True, False])


# -------------------------
# Header
# -------------------------
st.title("AFC Sales by Item (SKU) — 2023–2025")
st.caption("High-level view: Top SKUs, concentration, monthly patterns, YoY totals, and core vs long-tail.")


# -------------------------
# Load all years
# -------------------------
available_years = [y for y in YEAR_ORDER if FILES.get(y) and FILES[y].exists()]
if not available_years:
    st.error("No 'Sales by Item Summary' CSVs found. Put the files in the sales_dashboard folder.")
    st.stop()

dfs = [parse_qb_sales_by_item_summary(str(FILES[y]), y) for y in available_years]
data = pd.concat([d for d in dfs if d is not None and not d.empty], ignore_index=True)





if data.empty:
    st.error("Parsed data is empty — the export might be a different QuickBooks format.")
    st.stop()


# -------------------------
# Sidebar controls (like your reference)
# -------------------------
st.sidebar.header("Filters")

selected_year = st.sidebar.selectbox("Year", available_years, index=len(available_years) - 1)
top_n = st.sidebar.slider("Show Top N SKUs", 3, 20, 5)

enable_downloads = st.sidebar.toggle("Enable downloads (HTML only)", value=False)

st.sidebar.header("Exclude Labor")
exclude_labor = st.sidebar.toggle("Exclude Labor from charts", value=False)





# -------------------------
# Selected-year slice
# -------------------------
year_df = data[data["Year"] == selected_year].copy()

LABOR_ITEMS = {"LABOR (LABOR)","LABOR-PF (Pre Filter Removal/ Installation/ Disposal)"}

if exclude_labor:
    labor_prefixes = ("LABOR","LABOR-PF","LABOR-FF")
    year_df = year_df[~year_df["Item"].astype(str).str.strip().str.upper().str.startswith(labor_prefixes)]

data_view = data 
if exclude_labor:
    labor_prefixes = ("LABOR","LABOR-PF","LABOR-FF")
    data_view = data_view[~data_view["Item"].astype(str).str.strip().str.upper().str.startswith(labor_prefixes)]
    




if year_df.empty:
    st.warning("No data matches your filters.")
    st.stop()

# Totals by SKU (selected year)
sku_totals = (
    year_df.groupby("Item", as_index=False)["Amount"].sum()
    .sort_values("Amount", ascending=False)
)

# Use Top N in monthly grouped chart
top_items_year = sku_totals.head(top_n)["Item"]
year_top_df = year_df[year_df["Item"].isin(top_items_year)].copy()

# All-years monthly totals (for YoY line)
all_year_monthly = (
    data_view.groupby(["Year", "Month"], as_index=False)["Amount"].sum()
    .sort_values(["Year", "Month"])
)


overall_top_items = (
    data_view.groupby("Item",as_index=False)["Amount"].sum()
    .sort_values("Amount", ascending=False)
    .head(top_n)["Item"]
)

comparison_by_item = (
    data_view.groupby(["Year","Item"], as_index=False)["Amount"].sum()
)
comparison_by_item = comparison_by_item[comparison_by_item["Item"].isin(overall_top_items)]


# -------------------------
# KPI Row (4)
# -------------------------
k1, k2, k3, k4 = st.columns(4)

selected_total = float(year_df["Amount"].sum())
all_years_total = float(data["Amount"].sum())
active_skus = int(sku_totals.shape[0])

top_sku_label = sku_totals.iloc[0]["Item"] if len(sku_totals) else "—"
top_sku_sales = float(sku_totals.iloc[0]["Amount"]) if len(sku_totals) else 0.0
top10_share = (float(sku_totals.head(10)["Amount"].sum()) / selected_total * 100.0) if selected_total else 0.0
top_n_share = (float(sku_totals.head(top_n)["Amount"].sum()) / selected_total * 100.0) if selected_total else 0.0



k1.metric(f"Total Sales ({selected_year})", f"${selected_total:,.0f}")
k2.metric("Active SKUs", f"{active_skus:,}")
k3.metric(f"Top SKU ({selected_year})", top_sku_label)
k4.metric(f"Top {top_n} SKU Share ({selected_year})", f"{top_n_share:.1f}%")

st.divider()


# -------------------------
# Build figures (6 max)
# -------------------------

# Chart 1: Monthly grouped bars for Top N SKUs
monthly_grouped = (
    year_top_df.groupby(["Month", "Item"], as_index=False)["Amount"].sum()
)

fig1 = px.bar(
    monthly_grouped,
    x="Month",
    y="Amount",
    color="Item",
    barmode="group",
    title=f"Monthly Sales by SKU — {selected_year} (Top {top_n})",
    hover_data={"Amount": ":,.0f"},
    category_orders={"Month": MONTH_ORDER},
)
fig1.update_layout(bargap=0.2, bargroupgap=0.05, legend_title="SKU")

# Chart 2: Pie/Donut: Top N only (NO 'All Other')
pie_df = (
    sku_totals.head(top_n)
    .rename(columns={"Amount": "Sales"})[["Item", "Sales"]]
    .sort_values("Sales", ascending=False)
)
max_item = pie_df.iloc[0]["Item"] if len(pie_df) else ""
pie_df["Pull"] = pie_df["Item"].apply(lambda x: 0.12 if x == max_item else 0.0)

fig2 = px.pie(
    pie_df,
    names="Item",
    values="Sales",
    hole=0.55,
    title=f"Sales Share — Top {top_n} SKUs ({selected_year})",
)
fig2.update_traces(
    pull=pie_df["Pull"],
    textinfo="percent+label",
    marker=dict(line=dict(color="white", width=2)),
)
fig2.update_layout(
    legend=dict(
        orientation = "h",
        yanchor="top",
        y=-0.15,
        xanchor="center",
        x=0.5
    ),
    margin=dict(b=120)
)

# Chart 3: Top N SKUs by total (horizontal bar)
top_bar = sku_totals.head(top_n).sort_values("Amount", ascending=True)
fig3 = px.bar(
    top_bar,
    x="Amount",
    y="Item",
    orientation="h",
    title=f"Top {top_n} SKUs by Total Sales — {selected_year}",
    hover_data={"Amount": ":,.0f"},
)
fig3.update_layout(yaxis_title="SKU", xaxis_title="Sales")



# Chart 6: Core vs Long Tail (Top 5 SKUs vs All Other) for selected year
top5_items = sku_totals.head(5)["Item"].tolist()

top5_month = (
    year_df[year_df["Item"].isin(top5_items)]
    .groupby("Month", as_index=False)["Amount"].sum()
    .rename(columns={"Amount": "Top 5"})
)
total_month = (
    year_df.groupby("Month", as_index=False)["Amount"].sum()
    .rename(columns={"Amount": "Total"})
)
mix = total_month.merge(top5_month, on="Month", how="left")
mix["Top 5"] = mix["Top 5"].fillna(0.0)
mix["All Other"] = mix["Total"] - mix["Top 5"]


fig6 = px.bar(
    comparison_by_item,
    x="Year",
    y="Amount",
    color="Item",
    barmode="group",
    title=f"Top {top_n} Items Compared Across Years ",
    hover_data={"Amount":":,.0f"},
    category_orders={"Year":YEAR_ORDER}
)

fig6.update_layout(
    xaxis_title="Year",
    yaxis_title="Totals Sales",
    legend=dict(
        orientation = "h",
        yanchor="top",
        y=-0.15,
        xanchor="center",
        x=0.5
    ),
    margin=dict(b=120)
)



# JSON snapshots for cached HTML export
fig_json = {
    "monthly_top": fig1.to_json(),
    "share_topn": fig2.to_json(),
    "top_skus": fig3.to_json(),


}


# -------------------------
# Layout (match your style)
# -------------------------
# Row 1: Monthly grouped bars + Donut

st.plotly_chart(fig1, use_container_width=True)

st.divider()


st.plotly_chart(fig2, use_container_width=True)


st.divider()


# Row 2: Top SKUs (barh) + Pareto

st.plotly_chart(fig3, use_container_width=True)

st.divider()

# Row 3: YoY totals + Core vs Tail

st.plotly_chart(fig6, use_container_width=True)


# -------------------------
# HTML Downloads (safe for deployment)
# -------------------------
if enable_downloads:
    st.subheader("Downloads (HTML only)")

    d1, d2, d3 = st.columns(3)

    with d1:
        st.markdown("**Selected-year charts**")
        st.download_button(
            "Monthly Top N (HTML)",
            data=fig_to_html_bytes(fig_json["monthly_top"]),
            file_name=f"monthly_top{top_n}_{selected_year}.html",
            mime="text/html",
        )
        st.download_button(
            "Share Top N (HTML)",
            data=fig_to_html_bytes(fig_json["share_topn"]),
            file_name=f"share_top{top_n}_{selected_year}.html",
            mime="text/html",
        )

    with d2:
        st.markdown("**Rank / Concentration**")
        st.download_button(
            "Top N Totals (HTML)",
            data=fig_to_html_bytes(fig_json["top_skus"]),
            file_name=f"top{top_n}_totals_{selected_year}.html",
            mime="text/html",
        )
        st.download_button(
            "Pareto (HTML)",
            data=fig_to_html_bytes(fig_json["pareto"]),
            file_name=f"pareto_{selected_year}.html",
            mime="text/html",
        )

    with d3:
        st.markdown("**Trends**")
        st.download_button(
            "YoY Total (HTML)",
            data=fig_to_html_bytes(fig_json["yoy_total"]),
            file_name="yoy_total_all_years.html",
            mime="text/html",
        )
        st.download_button(
            "Core vs Tail (HTML)",
            data=fig_to_html_bytes(fig_json["core_vs_tail"]),
            file_name=f"core_vs_tail_{selected_year}.html",
            mime="text/html",
        )


# -------------------------
# Optional: underlying data
# -------------------------
with st.expander("Show underlying data (selected year)"):
    st.dataframe(
        year_df.groupby(["Item", "Month"], as_index=False)[["Amount", "Qty"]].sum(),
        use_container_width=True,
    )
