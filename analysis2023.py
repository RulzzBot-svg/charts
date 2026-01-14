import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="white", font_scale=1.1)

# -----------------------------
# Load + clean
# -----------------------------
df = pd.read_csv("AFC SALES BY CUSTOMER TYPE 2023.CSV")

df = df.rename(columns={df.columns[0]: "Category"})
df = df[~df["Category"].str.upper().isin(["TOTAL", "GRAND TOTAL"])]

if "TOTAL" in df.columns:
    df = df.drop(columns=["TOTAL"])

month_cols = [c for c in df.columns if "23" in c]

for c in month_cols:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

df["YearlyTotal"] = df[month_cols].sum(axis=1)

monthly_totals = df[month_cols].sum().reset_index()
monthly_totals.columns = ["Month", "Sales"]

yearly_sorted = df.sort_values("YearlyTotal", ascending=False)
top3 = yearly_sorted.head(3)

# -----------------------------
# Layout
# -----------------------------
fig = plt.figure(figsize=(16, 10))
gs = fig.add_gridspec(3, 2, height_ratios=[1.2, 1, 1], hspace=0.45, wspace=0.35)

# -----------------------------
# 1) Monthly trend (LINE)
# -----------------------------
ax1 = fig.add_subplot(gs[0, :])
sns.lineplot(
    data=monthly_totals,
    x="Month",
    y="Sales",
    marker="o",
    linewidth=3,
    ax=ax1
)
ax1.set_title("Monthly Sales Trend — 2023", fontsize=15)
ax1.set_ylabel("Sales ($)")
ax1.set_xlabel("")
ax1.tick_params(axis="x", rotation=30)

# Label only max & min
max_row = monthly_totals.loc[monthly_totals["Sales"].idxmax()]
min_row = monthly_totals.loc[monthly_totals["Sales"].idxmin()]

ax1.annotate(f"${max_row.Sales:,.0f}", (max_row.name, max_row.Sales),
             xytext=(0,10), textcoords="offset points", ha="center")

ax1.annotate(f"${min_row.Sales:,.0f}", (min_row.name, min_row.Sales),
             xytext=(0,-15), textcoords="offset points", ha="center")

# -----------------------------
# 2) Yearly totals (HORIZONTAL)
# -----------------------------
ax2 = fig.add_subplot(gs[1, 0])
sns.barplot(
    data=yearly_sorted,
    y="Category",
    x="YearlyTotal",
    ax=ax2
)
ax2.set_title("Yearly Sales by Customer Type")
ax2.set_xlabel("Sales ($)")
ax2.set_ylabel("")

# -----------------------------
# 3) Top 3 yearly
# -----------------------------
ax3 = fig.add_subplot(gs[1, 1])
sns.barplot(
    data=top3,
    x="Category",
    y="YearlyTotal",
    ax=ax3
)
ax3.set_title("Top 3 Customer Types — 2023")
ax3.set_ylabel("Sales ($)")
ax3.set_xlabel("")

for c in ax3.containers:
    ax3.bar_label(c, fmt="$%.0f", padding=3)

# -----------------------------
# 4) Pie chart (TOP 5 ONLY)
# -----------------------------
ax4 = fig.add_subplot(gs[2, :])
top5 = yearly_sorted.head(5)

ax4.pie(
    top5["YearlyTotal"],
    labels=top5["Category"],
    autopct="%1.1f%%",
    startangle=90,
    wedgeprops={"edgecolor": "white"}
)
ax4.set_title("Customer Mix — Top 5 Only")

# -----------------------------
# Title
# -----------------------------
plt.suptitle("AFC Sales Dashboard — 2023", fontsize=18, y=0.97)
plt.show()
