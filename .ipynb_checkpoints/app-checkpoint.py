"""
Canada Housing Market Dashboard
Run with:  streamlit run app.py
"""

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Canada Housing Dashboard", page_icon="🏠", layout="wide")

PROVINCE_NAMES = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba", "NB": "New Brunswick",
    "NL": "Newfoundland & Labrador", "NS": "Nova Scotia", "NT": "Northwest Territories",
    "ON": "Ontario", "PE": "Prince Edward Island", "SK": "Saskatchewan", "YT": "Yukon",
}
BLUE = "#1f4e79"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("cleaned_canada.csv")

    # Remove obvious data-entry errors so averages are not distorted
    df = df[(df["Price"] >= 10_000)]
    df = df[(df["Square Footage"] >= 100) & (df["Square Footage"] <= 20_000)]

    df["Price per Sqft"] = df["Price"] / df["Square Footage"]
    df["Province Name"] = df["Province"].map(PROVINCE_NAMES)
    return df


df = load_data()


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")

provinces = st.sidebar.multiselect(
    "Province", sorted(df["Province"].unique()), default=sorted(df["Province"].unique())
)
types = st.sidebar.multiselect(
    "Property type", sorted(df["Property Type"].unique()), default=sorted(df["Property Type"].unique())
)
price_range = st.sidebar.slider(
    "Price range (CAD)",
    min_value=0,
    max_value=5_000_000,
    value=(0, 5_000_000),
    step=50_000,
    format="$%d",
    help="Listings above $5M are included when the upper handle is at the maximum.",
)
min_beds = st.sidebar.slider("Minimum bedrooms", 0, 10, 0)

filtered = df[
    df["Province"].isin(provinces)
    & df["Property Type"].isin(types)
    & (df["Price"] >= price_range[0])
    & ((df["Price"] <= price_range[1]) | (price_range[1] == 5_000_000))
    & (df["Bedrooms"] >= min_beds)
]

st.sidebar.markdown("---")
st.sidebar.caption(f"Showing **{len(filtered):,}** of {len(df):,} listings")

if filtered.empty:
    st.warning("No listings match the selected filters.")
    st.stop()


# ---------------------------------------------------------------------------
# Header + KPIs
# ---------------------------------------------------------------------------
st.title("🏠 Canada Housing Market Dashboard")
st.caption("Snapshot of active residential listings across Canadian provinces and territories.")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total listings", f"{len(filtered):,}")
k2.metric("Median price", f"${filtered['Price'].median():,.0f}")
k3.metric("Average price", f"${filtered['Price'].mean():,.0f}")
k4.metric("Median price / sqft", f"${filtered['Price per Sqft'].median():,.0f}")
k5.metric("Median size", f"{filtered['Square Footage'].median():,.0f} sqft")

st.markdown("")

tab_overview, tab_map, tab_drivers, tab_data = st.tabs(
    ["📊 Market Overview", "🗺️ Geographic Map", "🔍 Price Drivers", "📄 Data"]
)


# ---------------------------------------------------------------------------
# Tab 1: Market overview
# ---------------------------------------------------------------------------
with tab_overview:
    c1, c2 = st.columns(2)

    by_prov = (
        filtered.groupby("Province Name")
        .agg(Listings=("Price", "size"), Median_Price=("Price", "median"))
        .reset_index()
    )

    with c1:
        st.subheader("Listings by province")
        fig = px.bar(
            by_prov.sort_values("Listings"), x="Listings", y="Province Name",
            orientation="h", color_discrete_sequence=[BLUE], text="Listings",
        )
        fig.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig.update_layout(yaxis_title=None, xaxis_title="Number of listings", height=420)
        st.plotly_chart(fig, width="stretch")

    with c2:
        st.subheader("Median price by province")
        fig = px.bar(
            by_prov.sort_values("Median_Price"), x="Median_Price", y="Province Name",
            orientation="h", color_discrete_sequence=[BLUE], text="Median_Price",
        )
        fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig.update_layout(yaxis_title=None, xaxis_title="Median price (CAD)", height=420)
        st.plotly_chart(fig, width="stretch")

    c3, c4 = st.columns(2)

    with c3:
        st.subheader("Property type mix")
        type_counts = filtered["Property Type"].value_counts().reset_index()
        type_counts.columns = ["Property Type", "Listings"]
        fig = px.pie(
            type_counts, names="Property Type", values="Listings", hole=0.5,
            color_discrete_sequence=px.colors.sequential.Blues_r,
        )
        fig.update_layout(height=420)
        st.plotly_chart(fig, width="stretch")

    with c4:
        st.subheader("Price distribution")
        fig = px.histogram(
            filtered[filtered["Price"] <= filtered["Price"].quantile(0.95)],
            x="Price", nbins=60, color_discrete_sequence=[BLUE],
        )
        fig.update_layout(xaxis_title="Price (CAD)", yaxis_title="Listings", height=420, bargap=0.05)
        st.plotly_chart(fig, width="stretch")
        st.caption("Top 5% most expensive listings hidden to keep the chart readable.")

    st.subheader("Top 15 cities by number of listings")
    top_cities = (
        filtered.groupby(["City", "Province"])
        .agg(
            Listings=("Price", "size"),
            Median_Price=("Price", "median"),
            Median_Price_per_Sqft=("Price per Sqft", "median"),
            Median_Sqft=("Square Footage", "median"),
        )
        .sort_values("Listings", ascending=False)
        .head(15)
        .reset_index()
    )
    st.dataframe(
        top_cities,
        hide_index=True,
        width="stretch",
        column_config={
            "Median_Price": st.column_config.NumberColumn("Median price", format="$%,.0f"),
            "Median_Price_per_Sqft": st.column_config.NumberColumn("Median $/sqft", format="$%,.0f"),
            "Median_Sqft": st.column_config.NumberColumn("Median sqft", format="%,.0f"),
        },
    )


# ---------------------------------------------------------------------------
# Tab 2: Geographic map
# ---------------------------------------------------------------------------
with tab_map:
    view = st.radio(
        "Map view",
        ["Listing density (heatmap)", "Individual listings (colored by price)"],
        horizontal=True,
    )

    if view.startswith("Listing density"):
        fig = px.density_map(
            filtered, lat="Latitude", lon="Longitude", radius=6,
            center=dict(lat=52, lon=-100), zoom=2.8,
            map_style="carto-positron", color_continuous_scale="YlOrRd",
            hover_data={"City": True, "Price": ":$,.0f"},
        )
        st.caption("Brighter areas = more listings concentrated in that area.")
    else:
        # Cap color scale at the 95th percentile so a few mansions don't wash out the colors
        cap = filtered["Price"].quantile(0.95)
        fig = px.scatter_map(
            filtered, lat="Latitude", lon="Longitude", color="Price",
            range_color=(0, cap), color_continuous_scale="Viridis", opacity=0.6,
            center=dict(lat=52, lon=-100), zoom=2.8, map_style="carto-positron",
            hover_name="City",
            hover_data={"Property Type": True, "Price": ":$,.0f", "Bedrooms": True,
                        "Square Footage": ":,.0f", "Latitude": False, "Longitude": False},
        )
        fig.update_traces(marker=dict(size=5))
        st.caption(f"Color scale capped at ${cap:,.0f} (95th percentile).")

    fig.update_layout(height=650, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------------------
# Tab 3: Price drivers
# ---------------------------------------------------------------------------
with tab_drivers:
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Median price by number of bedrooms")
        beds = (
            filtered[filtered["Bedrooms"].between(0, 8)]
            .groupby("Bedrooms")["Price"].median().reset_index()
        )
        fig = px.bar(beds, x="Bedrooms", y="Price", color_discrete_sequence=[BLUE], text="Price")
        fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig.update_layout(yaxis_title="Median price (CAD)", height=420)
        st.plotly_chart(fig, width="stretch")

    with c2:
        st.subheader("Median price by property type")
        ptype = filtered.groupby("Property Type")["Price"].median().sort_values().reset_index()
        fig = px.bar(
            ptype, x="Price", y="Property Type", orientation="h",
            color_discrete_sequence=[BLUE], text="Price",
        )
        fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig.update_layout(xaxis_title="Median price (CAD)", yaxis_title=None, height=420)
        st.plotly_chart(fig, width="stretch")

    st.subheader("Price vs. square footage")
    sample = filtered[filtered["Price"] <= filtered["Price"].quantile(0.95)]
    sample = sample.sample(min(5_000, len(sample)), random_state=42)
    fig = px.scatter(
        sample, x="Square Footage", y="Price", color="Property Type", opacity=0.5,
        hover_name="City", trendline="ols", trendline_scope="overall",
        trendline_color_override="black",
    )
    fig.update_layout(yaxis_title="Price (CAD)", height=480)
    st.plotly_chart(fig, width="stretch")
    st.caption("Random sample of up to 5,000 listings (top 5% prices excluded). Black line = overall linear trend.")

    st.subheader("Feature premium: median price with vs. without each feature")
    features = ["Garage", "Parking", "Fireplace", "Waterfront", "Pool", "Garden", "Balcony"]
    rows = []
    for f in features:
        with_f = filtered.loc[filtered[f] == "Yes", "Price"]
        without_f = filtered.loc[filtered[f] == "No", "Price"]
        if len(with_f) and len(without_f):
            rows.append({
                "Feature": f,
                "With": with_f.median(),
                "Without": without_f.median(),
                "Listings with feature": len(with_f),
            })
    prem = pd.DataFrame(rows)
    prem["Difference"] = prem["With"] - prem["Without"]
    prem["Difference %"] = prem["Difference"] / prem["Without"] * 100
    prem = prem.sort_values("Difference %", ascending=False)

    fig = px.bar(
        prem, x="Difference %", y="Feature", orientation="h", text="Difference %",
        color="Difference %", color_continuous_scale="RdBu", color_continuous_midpoint=0,
    )
    fig.update_traces(texttemplate="%{text:+.0f}%", textposition="outside")
    fig.update_layout(xaxis_title="Median price difference (%)", yaxis_title=None,
                      coloraxis_showscale=False, height=380)
    st.plotly_chart(fig, width="stretch")
    st.dataframe(
        prem, hide_index=True, width="stretch",
        column_config={
            "With": st.column_config.NumberColumn("Median price (with)", format="$%,.0f"),
            "Without": st.column_config.NumberColumn("Median price (without)", format="$%,.0f"),
            "Difference": st.column_config.NumberColumn(format="$%,.0f"),
            "Difference %": st.column_config.NumberColumn(format="%+.1f%%"),
        },
    )
    st.caption(
        "This compares medians only — it shows association, not cause. "
        "For example, waterfront homes may also be larger or in pricier regions."
    )


# ---------------------------------------------------------------------------
# Tab 4: Data
# ---------------------------------------------------------------------------
with tab_data:
    st.subheader("Filtered listings")
    st.dataframe(filtered.drop(columns=["Province Name"]), width="stretch", height=500)
    st.download_button(
        "Download filtered data (CSV)",
        filtered.to_csv(index=False).encode("utf-8"),
        file_name="canada_housing_filtered.csv",
        mime="text/csv",
    )

    with st.expander("About the data"):
        st.markdown(
            """
- **Source:** Canadian residential real estate listings (Kaggle), one row per listing.
- **Snapshot only:** the data has no listing/sale dates, so it describes the market at a single
  point in time — there is no trend over time.
- **Cleaning applied in this dashboard:** removed listings priced under \\$10,000 and listings
  with square footage under 100 or over 20,000 (likely data-entry errors).
- **Price per sqft** = Price ÷ Square Footage.
            """
        )
