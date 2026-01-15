import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="AFC Sales Dashboard", layout="wide")

st.title("AFC Sales Dashboard (2023–2025)")
st.caption("High-level view: Monthly sales by customer type, distribution, and year-over-year comparison.")

# ---------- Load + reshape ----------
paths = {
    "2023": "AFC SALES BY CUSTOMER TYPE 2023.CSV",
    "2024": "AFC SALES BY CUSTOMER TYPE 2024.CSV",
    "2025": "AFC SALES BY CUSTOMER TYPE 2025.CSV",
}

month_order = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

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

    # Normalize month labels like "Jan 23" -> "Jan" and order Jan..Dec
    long_df["Month"] = long_df["Month"].astype(str).str[:3]
    long_df["Month"] = pd.Categorical(long_df["Month"], categories=month_order, ordered=True)

    # IMPORTANT: Year as string (keeps grouped bars from becoming stacked-ish)
    long_df["Year"] = year_str

    dfs.append(long_df)

data = pd.concat(dfs, ignore_index=True)

# ---------- Sidebar controls ----------
st.sidebar.header("Filters")
years = sorted(data["Year"].unique())
selected_year = st.sidebar.selectbox("Year", years, index=len(years)-1)

top_n = st.sidebar.slider("Show Top N customer types (keeps charts readable)", 3, 20, 10)

# Filter to selected year
year_df = data[data["Year"] == selected_year].copy()

# Top N by yearly total
top_types = (
    year_df.groupby("CustomerType", as_index=False)["Sales"].sum()
    .sort_values("Sales", ascending=False)
    .head(top_n)["CustomerType"]
)
year_df = year_df[year_df["CustomerType"].isin(top_types)]

# Pre-aggregate monthly
monthly_grouped = (
    year_df.groupby(["Month", "CustomerType"], as_index=False)["Sales"].sum()
)

# ---------- Layout ----------
col1, col2 = st.columns([2, 1], gap="large")

with col1:
    fig_monthly = px.bar(
        monthly_grouped,
        x="Month",
        y="Sales",
        color="CustomerType",
        barmode="group",  # ✅ side-by-side
        title=f"Monthly Sales by Customer Type — {selected_year}",
        hover_data={"Sales": ":,.0f"},
    )
    fig_monthly.update_layout(bargap=0.2, bargroupgap=0.05)
    st.plotly_chart(fig_monthly, use_container_width=True)

with col2:
    pie_df = (
        year_df.groupby("CustomerType", as_index=False)["Sales"].sum()
        .sort_values("Sales", ascending=False)
    )
    fig_pie = px.pie(
        pie_df,
        names="CustomerType",
        values="Sales",
        title=f"Sales Distribution — {selected_year}",
        hole=0.35,
    )
    st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# ---------- 3-year comparison chart ----------
comparison = (
    data.groupby(["Year", "CustomerType"], as_index=False)["Sales"].sum()
)

# Optionally keep only top customer types overall (based on all years combined)
overall_top_types = (
    data.groupby("CustomerType", as_index=False)["Sales"].sum()
    .sort_values("Sales", ascending=False)
    .head(top_n)["CustomerType"]
)
comparison = comparison[comparison["CustomerType"].isin(overall_top_types)]

fig_compare = px.bar(
    comparison,
    x="CustomerType",
    y="Sales",
    color="Year",
    barmode="group",  # ✅ side-by-side
    title=f"Customer Type Totals Compared Across Years (Top {top_n})",
    hover_data={"Sales": ":,.0f"},
    category_orders={"Year": ["2023", "2024", "2025"]},
)
st.plotly_chart(fig_compare, use_container_width=True)

# ---------- Optional: show data ----------
with st.expander("Show underlying data (selected year)"):
    st.dataframe(
        year_df.groupby(["CustomerType", "Month"], as_index=False)["Sales"].sum(),
        use_container_width=True
    )
