import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="AFC Sales Dashboard", layout="wide")

# -------------------------
# Header
# -------------------------
st.title("AFC Sales Dashboard (2023–2025)")
st.caption("High-level view: Monthly sales by customer type, distribution, and year-over-year comparison.")

# -------------------------
# Load + reshape
# -------------------------
paths = {
    "2023": "AFC SALES BY CUSTOMER TYPE 2023.CSV",
    "2024": "AFC SALES BY CUSTOMER TYPE 2024.CSV",
    "2025": "AFC SALES BY CUSTOMER TYPE 2025.CSV",
}

MONTH_ORDER = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
YEAR_ORDER = ["2023", "2024", "2025"]

dfs = []
for year_str, path in paths.items():
    df = pd.read_csv(path)
    df = df.rename(columns={df.columns[0]: "CustomerType"})
    df = df[df["CustomerType"].astype(str).str.upper() != "TOTAL"]

    month_cols = [c for c in df.columns if c not in ["CustomerType", "TOTAL"]]

    long_df = df.melt(
        id_vars="CustomerType",
        value_vars=month_cols,
        var_name="Month",
        value_name="Sales"
    )

    # "Jan 23" -> "Jan" and force Jan..Dec order
    long_df["Month"] = long_df["Month"].astype(str).str[:3]
    long_df["Month"] = pd.Categorical(long_df["Month"], categories=MONTH_ORDER, ordered=True)

    long_df["Year"] = year_str  # keep categorical behavior for Plotly
    dfs.append(long_df)

data = pd.concat(dfs, ignore_index=True)

# -------------------------
# Sidebar Controls
# -------------------------
st.sidebar.header("Filters")

years = [y for y in YEAR_ORDER if y in set(data["Year"].unique())]
selected_year = st.sidebar.selectbox("Year", years, index=len(years)-1)

top_n = st.sidebar.slider("Show Top N customer types", 3, 20, 10)

# -------------------------
# Prep: Selected-year data
# -------------------------
year_df = data[data["Year"] == selected_year].copy()

top_types_year = (
    year_df.groupby("CustomerType", as_index=False)["Sales"].sum()
    .sort_values("Sales", ascending=False)
    .head(top_n)["CustomerType"]
)

year_df = year_df[year_df["CustomerType"].isin(top_types_year)]

monthly_grouped = (
    year_df.groupby(["Month", "CustomerType"], as_index=False)["Sales"].sum()
)

# -------------------------
# Prep: All-years summaries
# -------------------------
year_totals = data.groupby("Year", as_index=False)["Sales"].sum()

overall_top_types = (
    data.groupby("CustomerType", as_index=False)["Sales"].sum()
    .sort_values("Sales", ascending=False)
    .head(top_n)["CustomerType"]
)

comparison_by_type = (
    data.groupby(["Year", "CustomerType"], as_index=False)["Sales"].sum()
)
comparison_by_type = comparison_by_type[comparison_by_type["CustomerType"].isin(overall_top_types)]

# For the “8 bars per year” chart, keep a consistent order (small -> large by ALL-years total)


totals_by_year_type = (
    data.groupby(["Year", "CustomerType"], as_index=False)["Sales"].sum()
)

# -------------------------
# KPI Row
# -------------------------
k1, k2, k3, k4 = st.columns(4)

selected_year_total = year_df["Sales"].sum()
all_years_total = data["Sales"].sum()
selected_year_top = (
    year_df.groupby("CustomerType", as_index=False)["Sales"].sum()
    .sort_values("Sales", ascending=False)
    .head(1)
)

top_type_label = selected_year_top.iloc[0]["CustomerType"] if len(selected_year_top) else "—"
top_type_value = selected_year_top.iloc[0]["Sales"] if len(selected_year_top) else 0

k1.metric(f"Total Sales ({selected_year})", f"${selected_year_total:,.0f}")
k2.metric("Total Sales (All Years)", f"${all_years_total:,.0f}")
k3.metric(f"Top Customer Type ({selected_year})", top_type_label)
k4.metric(f"Top Type Sales ({selected_year})", f"${top_type_value:,.0f}")

st.divider()

# -------------------------
# Row 1: Monthly bars + Selected-year pie
# -------------------------
c1, c2 = st.columns([2.2, 1], gap="large")

with c1:
    fig_monthly = px.bar(
        monthly_grouped,
        x="Month",
        y="Sales",
        color="CustomerType",
        barmode="group",
        title=f"Monthly Sales by Customer Type — {selected_year} (Top {top_n})",
        hover_data={"Sales": ":,.0f"},
        category_orders={"Month": MONTH_ORDER},
    )
    fig_monthly.update_layout(bargap=0.2, bargroupgap=0.05, legend_title="Customer Type")
    st.plotly_chart(fig_monthly, use_container_width=True)

with c2:
    pie_df = (
        year_df.groupby("CustomerType", as_index=False)["Sales"].sum()
        .sort_values("Sales", ascending=False)
    )
    fig_pie = px.pie(
        pie_df,
        names="CustomerType",
        values="Sales",
        title=f"Sales Distribution — {selected_year}",
        hole=0.40,
    )
    st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# -------------------------
# Row 2: 3-year donut + "8 bars per year" totals
# -------------------------
c3, c4 = st.columns([1, 2.2], gap="large")

with c3:
    fig_year_donut = px.pie(
        year_totals,
        names="Year",
        values="Sales",
        hole=0.50,
        title="Total Sales Share by Year (2023–2025)",
        category_orders={"Year": YEAR_ORDER},
    )
    st.plotly_chart(fig_year_donut, use_container_width=True)

with c4:
    fig_year_sections = px.bar(
        totals_by_year_type,
        x="Year",
        y="Sales",
        color="CustomerType",
        barmode="group",
        title="Total Sales by Customer Type for Each Year",
        hover_data={"Sales": ":,.0f"},
        category_orders={"Year": YEAR_ORDER},
    )
    fig_year_sections.update_layout(
        xaxis_title="Year",
        yaxis_title="Total Sales",
        legend_title="Customer Type",
        bargap=0.25,
        bargroupgap=0.08,
    )
    st.plotly_chart(fig_year_sections, use_container_width=True)

st.divider()

# -------------------------
# Row 3: CustomerType totals compared across years (grouped)
# -------------------------
fig_compare = px.bar(
    comparison_by_type,
    x="CustomerType",
    y="Sales",
    color="Year",
    barmode="group",
    title=f"Customer Type Totals Compared Across Years (Top {top_n})",
    hover_data={"Sales": ":,.0f"},
    category_orders={"Year": YEAR_ORDER},
)

fig_compare.update_layout(
    xaxis_title="Customer Type",
    yaxis_title="Total Sales",
    legend_title="Year",
)

st.plotly_chart(fig_compare, use_container_width=True)

# -------------------------
# Optional: Underlying data
# -------------------------
with st.expander("Show underlying data (selected year)"):
    st.dataframe(
        year_df.groupby(["CustomerType", "Month"], as_index=False)["Sales"].sum(),
        use_container_width=True
    )
