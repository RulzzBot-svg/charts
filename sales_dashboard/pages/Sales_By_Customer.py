from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st

st.set_page_config(page_title="Sales by Customer", layout="wide")

# Theme (try: "plotly_white", "seaborn", "ggplot2", "simple_white")
px.defaults.template = "seaborn"

MONTH_ORDER = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
YEAR_ORDER = ["2023", "2024", "2025"]

BASE_DIR = Path(__file__).resolve().parent.parent  # .../sales_dashboard
DATA_DIR = BASE_DIR / "sales_dashboard"
if not DATA_DIR.exists():
    DATA_DIR = BASE_DIR  # fallback: same folder as main app

PATHS = {
    "2023": DATA_DIR / "AFC SALES BY CUSTOMER SUMMARY 2023.CSV",
    "2024": DATA_DIR / "AFC SALES BY CUSTOMER SUMMARY 2024.CSV",
    "2025": DATA_DIR / "AFC SALES BY CUSTOMER SUMMARY 2025.CSV",
}

CHLA_ALIASES = {
    "0000587428": "Childrens Hospital of Los Angeles",
    "0000683567": "Childrens Hospital of Los Angeles",
    "0000683569": "Childrens Hospital of Los Angeles",
    "Childrens Hospital of Los Angeles - Other": "Childrens Hospital of Los Angeles",
    "Total Childrens Hospital of Los Angeles": "Childrens Hospital of Los Angeles",
}

def read_csv_safe(path):
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    st.error(f"Could not decode file: {path}\nTried utf-8, utf-8-sig, cp1252, latin1.")
    st.stop()

@st.cache_data(show_spinner=False)
def fig_to_html_bytes(fig_json: str) -> bytes:
    fig = pio.from_json(fig_json)
    return fig.to_html(include_plotlyjs="cdn").encode("utf-8")

@st.cache_data(show_spinner=False)
def load_customer_sales_long(paths: dict) -> pd.DataFrame:
    dfs = []

    for year, path in paths.items():
        df = read_csv_safe(path)

        # Rename first col to Customer
        df = df.rename(columns={df.columns[0]: "Customer"})

        # Normalize customer names (CHLA rollup)
        df["Customer"] = (
            df["Customer"]
            .astype(str)
            .str.strip()
            .replace(CHLA_ALIASES)
        )

        # Drop TOTAL row if present
        df = df[df["Customer"].astype(str).str.upper() != "TOTAL"]
        df["Customer"] = df["Customer"].astype(str).str.strip()

        # If already long-ish (Month + Sales columns)
        cols_lower = {c.lower(): c for c in df.columns}
        if "month" in cols_lower and ("sales" in cols_lower or "amount" in cols_lower):
            month_col = cols_lower["month"]
            val_col = cols_lower.get("sales") or cols_lower.get("amount")

            long_df = df.rename(columns={month_col: "Month", val_col: "Sales"})[
                ["Customer", "Month", "Sales"]
            ].copy()

            long_df["Month"] = long_df["Month"].astype(str).str[:3]
            long_df["Month"] = pd.Categorical(long_df["Month"], categories=MONTH_ORDER, ordered=True)
            long_df["Sales"] = pd.to_numeric(long_df["Sales"], errors="coerce").fillna(0)
            long_df["Year"] = str(year)

            dfs.append(long_df)
            continue

        # Otherwise assume wide format
        month_cols = [c for c in df.columns if c not in ["Customer", "TOTAL", "Total", "total"]]

        long_df = df.melt(
            id_vars="Customer",
            value_vars=month_cols,
            var_name="Month",
            value_name="Sales",
        )

        long_df["Month"] = long_df["Month"].astype(str).str[:3]
        long_df["Month"] = pd.Categorical(long_df["Month"], categories=MONTH_ORDER, ordered=True)
        long_df["Sales"] = pd.to_numeric(long_df["Sales"], errors="coerce").fillna(0)
        long_df["Year"] = str(year)

        dfs.append(long_df)

    data = pd.concat(dfs, ignore_index=True)
    data = data[data["Customer"] != ""]
    return data

data = load_customer_sales_long(PATHS)

# -------------------------
# Sidebar filters
# -------------------------
st.sidebar.header("Filters")
available_years = [y for y in YEAR_ORDER if y in set(data["Year"].unique())]
selected_year = st.sidebar.selectbox("Year", available_years, index=len(available_years)-1)

top_n = st.sidebar.slider("Top N customers", 5, 50, 15)
enable_downloads = st.sidebar.toggle("Enable downloads (HTML only)", value=False)

# -------------------------
# Page header
# -------------------------
st.title("Sales by Customer (2023–2025)")
st.caption("High-level view: top customers, concentration, and year-over-year comparison.")

year_df = data[data["Year"] == selected_year].copy()

customer_totals_year = (
    year_df.groupby("Customer", as_index=False)["Sales"]
    .sum()
    .sort_values("Sales", ascending=False)
)

total_year = customer_totals_year["Sales"].sum()
top_customer = customer_totals_year.iloc[0]["Customer"] if len(customer_totals_year) else "—"
top_customer_amt = customer_totals_year.iloc[0]["Sales"] if len(customer_totals_year) else 0
top_customer_share = (top_customer_amt / total_year * 100) if total_year else 0
active_customers = year_df["Customer"].nunique()

year_totals_all = data.groupby("Year", as_index=False)["Sales"].sum()

overall_customer_totals = (
    data.groupby("Customer", as_index=False)["Sales"]
    .sum()
    .sort_values("Sales", ascending=False)
)

top_customers_overall = overall_customer_totals.head(top_n)["Customer"].tolist()

totals_by_year_customer = (
    data[data["Customer"].isin(top_customers_overall)]
    .groupby(["Year", "Customer"], as_index=False)["Sales"]
    .sum()
)

# -------------------------
# KPI row
# -------------------------
k1, k2, k3 = st.columns(3)
k1.metric("Top Customer", top_customer)
k2.metric("Top Customer Share", f"{top_customer_share:.1f}%")
k3.metric("Active Customers", f"{active_customers:,}")

st.divider()

# -------------------------
# Pie charts
# -------------------------
p1, p2 = st.columns([1, 1], gap="large")

with p1:
    st.caption(
        "Shows how concentrated sales are across your biggest accounts for the selected year. "
        "Each slice is one customer (Top N), and the largest slice is highlighted."
    )

    pie_df = customer_totals_year.head(top_n).copy().sort_values("Sales", ascending=False)
    pie_df["Pull"] = 0.0
    if not pie_df.empty:
        pie_df.loc[pie_df["Sales"].idxmax(), "Pull"] = 0.12

    fig_share_customers = px.pie(
        pie_df,
        names="Customer",
        values="Sales",
        hole=0.45,
        title=f"Sales Share by Customer — {selected_year} (Top {top_n})",
    )
    fig_share_customers.update_traces(
        pull=pie_df["Pull"],
        marker=dict(line=dict(color="white", width=2)),
        textinfo="percent",
    )
    fig_share_customers.update_layout(
        legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top"),
        margin=dict(r=160),
    )
    st.plotly_chart(fig_share_customers, use_container_width=True)

with p2:
    st.caption(
        "Compares total sales by year (2023–2025). Useful for quickly seeing which year contributed "
        "the largest share of total revenue."
    )

    year_totals_sorted = year_totals_all.copy()
    year_totals_sorted["Pull"] = 0.0
    if not year_totals_sorted.empty:
        year_totals_sorted.loc[year_totals_sorted["Sales"].idxmax(), "Pull"] = 0.12

    fig_year_share = px.pie(
        year_totals_sorted,
        names="Year",
        values="Sales",
        hole=0.50,
        title="Total Sales Share by Year (2023–2025)",
        category_orders={"Year": YEAR_ORDER},
    )
    fig_year_share.update_traces(
        pull=year_totals_sorted["Pull"],
        marker=dict(line=dict(color="white", width=2)),
        textinfo="percent+label",
    )
    st.plotly_chart(fig_year_share, use_container_width=True)

st.divider()

# -------------------------
# Top 10 customers (selected year)
# -------------------------
st.caption(f"""
    Ranks the top {top_n} customers for the selected year by total sales.
    This helps identify your highest-value accounts at a glance.
           """

)

top10 = top_n
rank_df = customer_totals_year.head(top10).sort_values("Sales", ascending=True)

fig_top10 = px.bar(
    rank_df,
    x="Sales",
    y="Customer",
    orientation="h",
    title=f"Top {top10} Customers — {selected_year}",
    hover_data={"Sales": ":,.0f"},
    category_orders={"Customer": rank_df["Customer"].tolist()},
)
fig_top10.update_yaxes(autorange="reversed")
fig_top10.update_layout(margin=dict(l=10, r=10, t=60, b=10))
st.plotly_chart(fig_top10, use_container_width=True)

st.divider()

# -------------------------
# Monthly YoY totals
# -------------------------
st.caption(
    "Shows the monthly total sales trend for each year on the same chart. "
    "This is useful for spotting seasonality and comparing year-over-year performance by month."
)

monthly_yoy = (
    data.groupby(["Year", "Month"], as_index=False)["Sales"]
    .sum()
)

fig_yoy_monthly = px.line(
    monthly_yoy,
    x="Month",
    y="Sales",
    color="Year",
    markers=True,
    title="Monthly Total Sales — Year-over-Year (2023–2025)",
    hover_data={"Sales": ":,.0f"},
    category_orders={"Month": MONTH_ORDER, "Year": YEAR_ORDER},
)

fig_yoy_monthly.update_layout(
    xaxis_title="Month",
    yaxis_title="Sales",
    legend_title="Year",
)
st.plotly_chart(fig_yoy_monthly, use_container_width=True)

st.divider()

# -------------------------
# Customer totals by year (Top N overall)
# -------------------------
st.caption(
    "Compares total sales for the Top N customers (overall across 2023–2025) in each year. "
    "Great for seeing whether key accounts are growing, shrinking, or staying consistent year-to-year."
)

fig_year_sections = px.bar(
    totals_by_year_customer,
    x="Year",
    y="Sales",
    color="Customer",
    barmode="group",
    title=f"Total Sales by Customer for Each Year (Top {top_n} overall)",
    hover_data={"Sales": ":,.0f"},
    category_orders={"Year": YEAR_ORDER},
)
fig_year_sections.update_layout(
    xaxis_title="Year",
    yaxis_title="Total Sales",
    legend_title="Customer",
    bargap=0.25,
    bargroupgap=0.08,
    legend=dict(x=1.02, y=1, xanchor="left", yanchor="top"),
    margin=dict(r=220),
)
st.plotly_chart(fig_year_sections, use_container_width=True)

st.divider()

# -------------------------
# Downloads
# -------------------------
if enable_downloads:
    st.subheader("Downloads (HTML only)")
    st.caption("Download interactive versions of the charts as standalone HTML files.")

    fig_json = {
        "share_customers": fig_share_customers.to_json(),
        "year_share": fig_year_share.to_json(),
        "top10": fig_top10.to_json(),
        "yoy_monthly": fig_yoy_monthly.to_json(),
        "year_sections": fig_year_sections.to_json(),
    }

    d1, d2, d3 = st.columns(3)

    with d1:
        st.download_button(
            "Customer Share (HTML)",
            data=fig_to_html_bytes(fig_json["share_customers"]),
            file_name=f"customer_share_{selected_year}_top{top_n}.html",
            mime="text/html",
        )
        st.download_button(
            "Year Share (HTML)",
            data=fig_to_html_bytes(fig_json["year_share"]),
            file_name="sales_share_by_year.html",
            mime="text/html",
        )

    with d2:
        st.download_button(
            "Top 10 Customers (HTML)",
            data=fig_to_html_bytes(fig_json["top10"]),
            file_name=f"top10_customers_{selected_year}.html",
            mime="text/html",
        )

    with d3:
        st.download_button(
            "YoY Monthly (HTML)",
            data=fig_to_html_bytes(fig_json["yoy_monthly"]),
            file_name="monthly_yoy_2023_2025.html",
            mime="text/html",
        )
        st.download_button(
            "Year Sections (HTML)",
            data=fig_to_html_bytes(fig_json["year_sections"]),
            file_name=f"customer_year_sections_top{top_n}.html",
            mime="text/html",
        )

with st.expander("Show underlying data (selected year totals)"):
    st.dataframe(customer_totals_year, use_container_width=True)
