import io
import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st

st.set_page_config(page_title="AFC Sales Dashboard", layout="wide")

# -------------------------
# Global Plotly styling (fixes black/white exports)
# -------------------------
px.defaults.template = "plotly_dark"  # important for consistent export styling

# A nicer, consistent qualitative palette
QUAL_COLORS = px.colors.qualitative.Set2

# -------------------------
# Cached helpers (major speed boost)
# -------------------------
@st.cache_data(show_spinner=False)
def fig_to_png_bytes(fig_json: str, scale: float = 1.4) -> bytes:
    fig = pio.from_json(fig_json)
    return fig.to_image(format="png", scale=scale, engine="kaleido")

@st.cache_data(show_spinner=False)
def fig_to_html_bytes(fig_json: str) -> bytes:
    fig = pio.from_json(fig_json)
    return fig.to_html(include_plotlyjs="cdn").encode("utf-8")

@st.cache_data(show_spinner=False)
def build_excel_report(fig_json_map: dict) -> bytes:
    """
    Very lightweight Excel: one sheet with embedded chart PNGs.
    (No data tabs to keep it fast; add them back later if needed.)
    """
    import xlsxwriter

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    ws = workbook.add_worksheet("Dashboard")

    title_fmt = workbook.add_format({"bold": True, "font_size": 16})
    ws.write("A1", "AFC Sales Dashboard (2023–2025)", title_fmt)

    # Layout positions
    layout = [
        ("monthly", "A3", 0.55),
        ("year_pie", "K3", 0.70),
        ("year_donut", "A22", 0.75),
        ("year_sections", "K22", 0.55),
        ("compare", "A41", 0.55),
    ]

    for key, cell, scale in layout:
        if key not in fig_json_map:
            continue
        png = fig_to_png_bytes(fig_json_map[key], scale=1.35)
        ws.insert_image(cell, f"{key}.png", {"image_data": io.BytesIO(png), "x_scale": scale, "y_scale": scale})

    workbook.close()
    output.seek(0)
    return output.read()

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

    long_df["Month"] = long_df["Month"].astype(str).str[:3]
    long_df["Month"] = pd.Categorical(long_df["Month"], categories=MONTH_ORDER, ordered=True)
    long_df["Year"] = year_str
    dfs.append(long_df)

data = pd.concat(dfs, ignore_index=True)

# -------------------------
# Sidebar controls
# -------------------------
st.sidebar.header("Filters")
years = [y for y in YEAR_ORDER if y in set(data["Year"].unique())]
selected_year = st.sidebar.selectbox("Year", years, index=len(years)-1)
top_n = st.sidebar.slider("Show Top N customer types", 3, 20, 10)

# IMPORTANT: downloads toggle (prevents lag unless you want downloads)
enable_downloads = st.sidebar.toggle("Enable downloads (PNG/HTML/Excel)", value=False)

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

customer_order_small_to_big = (
    data.groupby("CustomerType", as_index=False)["Sales"]
    .sum()
    .sort_values("Sales")["CustomerType"]
    .tolist()
)

comparison_by_type = (
    data.groupby(["Year", "CustomerType"], as_index=False)["Sales"].sum()
)

overall_top_types = (
    data.groupby("CustomerType", as_index=False)["Sales"].sum()
    .sort_values("Sales", ascending=False)
    .head(top_n)["CustomerType"]
)
comparison_by_type = comparison_by_type[comparison_by_type["CustomerType"].isin(overall_top_types)]

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
# Build figures (use consistent colors)
# -------------------------
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

fig_year_donut = px.pie(
    year_totals,
    names="Year",
    values="Sales",
    hole=0.50,
    title="Total Sales Share by Year (2023–2025)",
    category_orders={"Year": YEAR_ORDER},
)

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

# JSON snapshots for fast cached export
fig_json = {
    "monthly": fig_monthly.to_json(),
    "year_pie": fig_pie.to_json(),
    "year_donut": fig_year_donut.to_json(),
    "year_sections": fig_year_sections.to_json(),
    "compare": fig_compare.to_json(),
}

# -------------------------
# Layout
# -------------------------
# Row 1
c1, c2 = st.columns([2.2, 1], gap="large")
with c1:
    st.plotly_chart(fig_monthly, use_container_width=True)
with c2:
    st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# Row 2
c3, c4 = st.columns([1, 2.2], gap="large")
with c3:
    st.plotly_chart(fig_year_donut, use_container_width=True)
with c4:
    st.plotly_chart(fig_year_sections, use_container_width=True)

st.divider()

# Row 3
st.plotly_chart(fig_compare, use_container_width=True)

# -------------------------
# Downloads (optional + fast)
# -------------------------
if enable_downloads:
    st.subheader("Downloads")

    d1, d2, d3 = st.columns(3)

    with d1:
        st.markdown("**Monthly chart**")
        st.download_button(
            "PNG",
            data=fig_to_png_bytes(fig_json["monthly"], scale=1.35),
            file_name=f"monthly_{selected_year}.png",
            mime="image/png",
        )
        st.download_button(
            "HTML (interactive)",
            data=fig_to_html_bytes(fig_json["monthly"]),
            file_name=f"monthly_{selected_year}.html",
            mime="text/html",
        )

    with d2:
        st.markdown("**Selected-year pie**")
        st.download_button(
            "PNG",
            data=fig_to_png_bytes(fig_json["year_pie"], scale=1.35),
            file_name=f"pie_{selected_year}.png",
            mime="image/png",
        )
        st.download_button(
            "HTML (interactive)",
            data=fig_to_html_bytes(fig_json["year_pie"]),
            file_name=f"pie_{selected_year}.html",
            mime="text/html",
        )

    with d3:
        st.markdown("**Full Excel (charts embedded)**")
        st.download_button(
            "Download Excel",
            data=build_excel_report(fig_json),
            file_name=f"AFC_Sales_Report_{selected_year}_Top{top_n}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# -------------------------
# Optional: Underlying data
# -------------------------
with st.expander("Show underlying data (selected year)"):
    st.dataframe(
        year_df.groupby(["CustomerType", "Month"], as_index=False)["Sales"].sum(),
        use_container_width=True
    )
