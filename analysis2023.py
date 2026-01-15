import pandas as pd
import plotly.express as px


paths = {
    2023: "AFC SALES BY CUSTOMER TYPE 2023.CSV",
    2024: "AFC SALES BY CUSTOMER TYPE 2024.CSV",
    2025: "AFC SALES BY CUSTOMER TYPE 2025.CSV",
}

month_order = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

COLOR_MAP = {
    "Commercial": "#4E79A7",
    "Healthcare": "#59A14F",
    "Industrial": "#F28E2B",
    "Education": "#E15759",
    "Government": "#76B7B2",
    "Residential": "#EDC948",
    "Other": "#B07AA1",
}


dfs = []

for year, path in paths.items():
    df = pd.read_csv(path)
    df = df.rename(columns={df.columns[0]: "CustomerType"})
    df = df[df["CustomerType"].str.upper() != "TOTAL"]

    month_cols = [c for c in df.columns if c not in ["CustomerType", "TOTAL"]]

    long_df = df.melt(
        id_vars="CustomerType",
        value_vars=month_cols,
        var_name="Month",
        value_name="Sales"
    )

    # Normalize month labels (Jan 23 → Jan)
    long_df["Month"] = long_df["Month"].str[:3]

    # Force Jan → Dec order
    long_df["Month"] = pd.Categorical(
        long_df["Month"],
        categories=month_order,
        ordered=True
    )

    long_df["Year"] = year
    dfs.append(long_df)

data = pd.concat(dfs, ignore_index=True)


for year in sorted(data["Year"].unique()):
    yearly_data = data[data["Year"] == year]

    monthly_grouped = (
        yearly_data
        .groupby(["Month", "CustomerType"], as_index=False)["Sales"]
        .sum()
    )

    fig = px.bar(
        monthly_grouped,
        x="Month",
        y="Sales",
        color="CustomerType",
        barmode="group",   # 🔥 THIS is the key line
        title=f"Monthly Sales by Customer Type — {year}",
        hover_data={"Sales": ":,.0f"}
    )

    fig.show()


for year in sorted(data["Year"].unique()):
    yearly_data = data[data["Year"] == year]

    customer_totals = (
        yearly_data.groupby("CustomerType", as_index=False)["Sales"]
        .sum()
    )

    fig = px.pie(
        customer_totals,
        names="CustomerType",
        values="Sales",
        title=f"Sales Distribution by Customer Type — {year}",
        hole=0.35
    )

    fig.show()


comparison = (
    data.groupby(["Year", "CustomerType"], as_index=False)["Sales"]
    .sum()
)

comparison["Year"] = comparison["Year"].astype(str)

fig = px.bar(
    comparison,
    x="CustomerType",
    y="Sales",
    color="Year",
    barmode="group",
    title="Customer Type Sales Comparison (2023-2025)",
    hover_data={"Sales":":,.0f"},
    category_orders={"Year":["2023","2024","2025"]}
)

fig.update_layout(bargap=0.2, bargroupgap=0.05)
fig.show()
