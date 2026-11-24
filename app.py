"""
Canada Housing Market Dashboard
Run with:  streamlit run app.py
"""

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Canada Housing Dashboard", page_icon="🏠", layout="wide")

BLUE = "#1f4e79"

PROVINCE_NAMES = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba", "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador", "NS": "Nova Scotia", "NT": "Northwest Territories",
    "ON": "Ontario", "PE": "Prince Edward Island", "SK": "Saskatchewan", "YT": "Yukon",
}

PROPERTY_TYPES = {
    "Single Family": "A detached house for one household, usually on its own lot of land.",
    "Condo": "A unit (usually an apartment) inside a larger building. You own the unit; "
             "shared areas like hallways and the land are owned jointly and paid for with condo fees.",
    "Townhome": "A multi-storey home joined to its neighbours by side walls, in a row of similar homes.",
    "Condo/Townhome": "A townhome sold under condo ownership — you own the unit and pay condo fees "
                      "for shared upkeep.",
    "Duplex": "One building split into two separate homes (side-by-side or one above the other).",
    "MultiFamily": "A building with several separate homes (e.g. triplex, fourplex, small apartment "
                   "building), often bought as an investment.",
    "Manufactured Home": "A house built in a factory and then moved to its site, often placed on a "
                         "permanent foundation.",
    "Mobile Home": "A factory-built home on a chassis that can be moved, often in a mobile home park.",
    "Vacant Land": "A piece of land with no house on it.",
}

FEATURES = ["Garage", "Parking", "Fireplace", "Balcony", "Garden", "Pool", "Waterfront"]

# Unit conversions
SQFT_TO_M2 = 0.092903
ACRE_TO_M2 = 4046.8564
ACRE_TO_KM2 = 0.0040468564
ACRE_TO_HA = 0.40468564


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("cleaned_canada.csv")

    # Remove obvious data-entry errors so averages are not distorted
    df = df[df["Price"] >= 10_000]
    df = df[(df["Square Footage"] >= 100) & (df["Square Footage"] <= 20_000)]

    df["Province Name"] = df["Province"].map(PROVINCE_NAMES)
    return df


df = load_data()


# ---------------------------------------------------------------------------
# Sidebar: units and filters
# ---------------------------------------------------------------------------
st.sidebar.header("Units")
floor_unit = st.sidebar.radio("Floor area", ["sqft", "m²"], horizontal=True)
lot_unit = st.sidebar.radio("Lot size", ["acres", "hectares", "m²", "km²"], horizontal=True)

floor_factor = 1 if floor_unit == "sqft" else SQFT_TO_M2
lot_factor = {"acres": 1, "hectares": ACRE_TO_HA, "m²": ACRE_TO_M2, "km²": ACRE_TO_KM2}[lot_unit]

df["Floor Area"] = df["Square Footage"] * floor_factor
df["Lot Size"] = df["Acreage"] * lot_factor
df["Price per Area"] = df["Price"] / df["Floor Area"]

st.sidebar.header("Filters")

all_provinces = sorted(df["Province"].unique(), key=lambda p: PROVINCE_NAMES[p])
provinces = st.sidebar.multiselect(
    "Province", all_provinces, default=all_provinces,
    format_func=lambda p: f"{PROVINCE_NAMES[p]} ({p})",
)

all_types = sorted(df["Property Type"].unique())
types = st.sidebar.multiselect(
    "Property type", all_types, default=all_types,
    help="See the 'About the Data' tab for what each type means.",
)

price_range = st.sidebar.slider(
    "Price range (CAD)", 0, 5_000_000, (0, 5_000_000), step=50_000, format="$%d",
    help="Listings above $5M are included when the upper handle is at the maximum.",
)

min_beds = st.sidebar.slider("Minimum bedrooms", 0, 10, 0)
min_baths = st.sidebar.slider("Minimum bathrooms", 0, 10, 0)

max_floor = int(df["Floor Area"].quantile(0.99))
floor_range = st.sidebar.slider(
    f"Floor area ({floor_unit})", 0, max_floor, (0, max_floor),
    help="The largest 1% of homes are included when the upper handle is at the maximum.",
)

must_have = st.sidebar.multiselect(
    "Must have", FEATURES,
    help="Only show listings that have ALL of the selected features.",
)

mask = (
    df["Province"].isin(provinces)
    & df["Property Type"].isin(types)
    & (df["Price"] >= price_range[0])
    & ((df["Price"] <= price_range[1]) | (price_range[1] == 5_000_000))
    & (df["Bedrooms"] >= min_beds)
    & (df["Bathrooms"] >= min_baths)
    & (df["Floor Area"] >= floor_range[0])
    & ((df["Floor Area"] <= floor_range[1]) | (floor_range[1] == max_floor))
)
for feature in must_have:
    mask &= df[feature] == "Yes"

filtered = df[mask]

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
k4.metric(f"Median price / {floor_unit}", f"${filtered['Price per Area'].median():,.0f}")
k5.metric("Median floor area", f"{filtered['Floor Area'].median():,.0f} {floor_unit}")

st.markdown("")

tab_overview, tab_map, tab_property, tab_features, tab_data, tab_about = st.tabs(
    ["📊 Market Overview", "🗺️ Geographic Map", "🏡 Property Characteristics",
     "✨ Home Features", "📄 Data", "ℹ️ About the Data"]
)


def hbar(data, x, y, text_format, x_title, height=420):
    """Horizontal bar chart used across the dashboard."""
    fig = px.bar(data, x=x, y=y, orientation="h", color_discrete_sequence=[BLUE], text=x)
    fig.update_traces(texttemplate=text_format, textposition="outside")
    fig.update_layout(yaxis_title=None, xaxis_title=x_title, height=height)
    return fig


# ---------------------------------------------------------------------------
# Tab 1: Market overview
# ---------------------------------------------------------------------------
with tab_overview:
    by_prov = (
        filtered.groupby("Province Name")
        .agg(Listings=("Price", "size"), Median_Price=("Price", "median"))
        .reset_index()
    )

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Listings by province")
        st.plotly_chart(
            hbar(by_prov.sort_values("Listings"), "Listings", "Province Name",
                 "%{text:,}", "Number of listings"),
            width="stretch",
        )
    with c2:
        st.subheader("Median price by province")
        st.plotly_chart(
            hbar(by_prov.sort_values("Median_Price"), "Median_Price", "Province Name",
                 "$%{text:,.0f}", "Median price (CAD)"),
            width="stretch",
        )

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
        filtered.groupby(["City", "Province Name"])
        .agg(
            Listings=("Price", "size"),
            Median_Price=("Price", "median"),
            Median_Price_per_Area=("Price per Area", "median"),
            Median_Floor_Area=("Floor Area", "median"),
        )
        .sort_values("Listings", ascending=False)
        .head(15)
        .reset_index()
    )
    st.dataframe(
        top_cities, hide_index=True, width="stretch",
        column_config={
            "Province Name": "Province",
            "Median_Price": st.column_config.NumberColumn("Median price", format="$%,.0f"),
            "Median_Price_per_Area": st.column_config.NumberColumn(f"Median $/{floor_unit}", format="$%,.0f"),
            "Median_Floor_Area": st.column_config.NumberColumn(f"Median floor area ({floor_unit})", format="%,.0f"),
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
            hover_data={"City": True, "Province Name": True, "Price": ":$,.0f"},
        )
        st.caption("Brighter areas = more listings concentrated in that area.")
    else:
        # Cap the color scale at the 95th percentile so a few mansions don't wash out the colors
        cap = filtered["Price"].quantile(0.95)
        fig = px.scatter_map(
            filtered, lat="Latitude", lon="Longitude", color="Price",
            range_color=(0, cap), color_continuous_scale="Viridis", opacity=0.6,
            center=dict(lat=52, lon=-100), zoom=2.8, map_style="carto-positron",
            hover_name="City",
            hover_data={"Province Name": True, "Property Type": True, "Price": ":$,.0f",
                        "Bedrooms": True, "Floor Area": ":,.0f",
                        "Latitude": False, "Longitude": False},
        )
        fig.update_traces(marker=dict(size=5))
        st.caption(f"Color scale capped at ${cap:,.0f} (95th percentile). Floor area in {floor_unit}.")

    fig.update_layout(height=650, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------------------
# Tab 3: Property characteristics
# ---------------------------------------------------------------------------
with tab_property:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Median price by number of bedrooms")
        beds = (
            filtered[filtered["Bedrooms"].between(0, 8)]
            .groupby("Bedrooms")
            .agg(Price=("Price", "median"), Listings=("Price", "size"))
            .reset_index()
        )
        fig = px.bar(beds, x="Bedrooms", y="Price", color_discrete_sequence=[BLUE], text="Price",
                     hover_data={"Listings": ":,"})
        fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig.update_layout(yaxis_title="Median price (CAD)", height=420)
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.subheader("Median price by property type")
        ptype = filtered.groupby("Property Type")["Price"].median().sort_values().reset_index()
        st.plotly_chart(
            hbar(ptype, "Price", "Property Type", "$%{text:,.0f}", "Median price (CAD)"),
            width="stretch",
        )

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Floor area by property type")
        fig = px.box(
            filtered[filtered["Floor Area"] <= filtered["Floor Area"].quantile(0.99)],
            x="Property Type", y="Floor Area", color_discrete_sequence=[BLUE],
        )
        fig.update_layout(yaxis_title=f"Floor area ({floor_unit})", xaxis_title=None, height=420)
        st.plotly_chart(fig, width="stretch")
        st.caption("Box = middle 50% of homes, line = median. Largest 1% hidden.")
    with c4:
        st.subheader("Lot size by property type")
        lots = filtered[filtered["Lot Size"] > 0]
        lot_summary = (
            lots.groupby("Property Type")
            .agg(Median_Lot=("Lot Size", "median"), Listings=("Lot Size", "size"))
            .sort_values("Median_Lot")
            .reset_index()
        )
        fmt = "%{text:,.4f}" if lot_unit == "km²" else "%{text:,.2f}" if lot_unit != "m²" else "%{text:,.0f}"
        st.plotly_chart(
            hbar(lot_summary, "Median_Lot", "Property Type", fmt, f"Median lot size ({lot_unit})"),
            width="stretch",
        )
        st.caption(
            f"Only listings with a reported lot size ({len(lots):,} of {len(filtered):,}). "
            "Condos usually have no lot of their own."
        )

    st.subheader("Price vs. floor area")
    sample = filtered[filtered["Price"] <= filtered["Price"].quantile(0.95)]
    sample = sample.sample(min(5_000, len(sample)), random_state=42)
    fig = px.scatter(
        sample, x="Floor Area", y="Price", color="Property Type", opacity=0.5, hover_name="City",
    )
    fig.update_layout(xaxis_title=f"Floor area ({floor_unit})", yaxis_title="Price (CAD)", height=480)
    st.plotly_chart(fig, width="stretch")
    st.caption("Random sample of up to 5,000 listings (top 5% prices excluded) so the chart stays fast.")


# ---------------------------------------------------------------------------
# Tab 4: Home features
# ---------------------------------------------------------------------------
with tab_features:
    st.subheader("How common is each feature?")
    share = pd.DataFrame({
        "Feature": FEATURES,
        "Share": [(filtered[f] == "Yes").mean() * 100 for f in FEATURES],
        "Listings": [(filtered[f] == "Yes").sum() for f in FEATURES],
    }).sort_values("Share")
    fig = px.bar(share, x="Share", y="Feature", orientation="h", text="Share",
                 color_discrete_sequence=[BLUE], hover_data={"Listings": ":,"})
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(xaxis_title="% of listings with the feature", yaxis_title=None, height=380)
    st.plotly_chart(fig, width="stretch")

    st.subheader("Breakdown by home detail")
    detail = st.selectbox(
        "Choose a detail", ["Heating", "Basement", "Exterior", "Flooring", "Roof", "Sewer"],
    )
    counts = (
        filtered[detail].fillna("Not reported")
        .value_counts().rename_axis(detail).reset_index(name="Listings")
        .sort_values("Listings")
    )
    st.plotly_chart(
        hbar(counts, "Listings", detail, "%{text:,}", "Number of listings"),
        width="stretch",
    )
    st.caption("'Not reported' means the listing did not include this detail.")


# ---------------------------------------------------------------------------
# Tab 5: Data
# ---------------------------------------------------------------------------
with tab_data:
    st.subheader("Filtered listings")
    show_cols = ["City", "Province Name", "Property Type", "Price", "Bedrooms", "Bathrooms",
                 "Floor Area", "Lot Size"] + FEATURES + ["Heating", "Basement", "Exterior",
                 "Flooring", "Roof", "Sewer", "Latitude", "Longitude"]
    table = filtered[show_cols].rename(columns={
        "Province Name": "Province",
        "Floor Area": f"Floor Area ({floor_unit})",
        "Lot Size": f"Lot Size ({lot_unit})",
    })
    st.dataframe(table, width="stretch", height=500, hide_index=True)
    st.download_button(
        "Download filtered data (CSV)",
        table.to_csv(index=False).encode("utf-8"),
        file_name="canada_housing_filtered.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Tab 6: About the data
# ---------------------------------------------------------------------------
with tab_about:
    st.subheader("Dataset overview")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Listings (after cleaning)", f"{len(df):,}")
    a2.metric("Provinces & territories", df["Province"].nunique())
    a3.metric("Cities / towns", f"{df['City'].nunique():,}")
    a4.metric("Columns", 23)
    st.markdown(
        """
- **Source:** Canadian residential real estate listings (Kaggle), cleaned in `housing.ipynb`.
- **Snapshot only:** there are no listing or sale dates, so the data describes the market at one
  point in time. It cannot show trends over time.
- **Asking prices, not sale prices:** the price is what the seller is asking, which may differ
  from what the home finally sells for.
- **Extra cleaning in this dashboard:** listings priced under \\$10,000 and listings under 100 or over
  20,000 sqft were removed as likely data-entry errors.
- **Coverage is uneven:** British Columbia has more than half of all listings, while Manitoba, Yukon
  and the Northwest Territories have very few. Nunavut has no data.
        """
    )

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Province codes")
        prov_table = (
            df.groupby("Province").size().rename("Listings").reset_index()
            .assign(Name=lambda d: d["Province"].map(PROVINCE_NAMES))
            [["Province", "Name", "Listings"]]
            .rename(columns={"Province": "Code"})
            .sort_values("Listings", ascending=False)
        )
        st.dataframe(prov_table, hide_index=True, width="stretch",
                     column_config={"Listings": st.column_config.NumberColumn(format="%,d")})
    with c2:
        st.subheader("Property types")
        type_table = pd.DataFrame({
            "Type": list(PROPERTY_TYPES.keys()),
            "What it means": list(PROPERTY_TYPES.values()),
            "Listings": [int((df["Property Type"] == t).sum()) for t in PROPERTY_TYPES],
        })
        st.dataframe(type_table, hide_index=True, width="stretch",
                     column_config={"What it means": st.column_config.TextColumn(width="large")})

    st.subheader("Units of measurement")
    st.markdown(
        f"""
- **Floor area** (`Square Footage`) is the living space inside the home, recorded in **square feet**.
  1 sqft = 0.0929 m².
- **Lot size** (`Acreage`) is the land the property sits on, recorded in **acres**.
  1 acre = 4,046.86 m² = 0.4047 hectares = 0.004047 km² (1 km² ≈ 247 acres).
- A lot size of **0 means it was not reported**. This applies to about
  {(df['Acreage'] == 0).mean():.0%} of listings, mostly condos and townhomes, which don't have their
  own lot. These are left out of lot size charts.
- Use the **Units** options in the sidebar to switch between imperial and metric.
        """
    )

    st.subheader("Column dictionary")
    dictionary = pd.DataFrame([
        ("City", "City or town of the listing"),
        ("Province", "Province or territory (2-letter code)"),
        ("Latitude / Longitude", "Map coordinates of the listing"),
        ("Price", "Asking price in Canadian dollars (CAD)"),
        ("Bedrooms", "Number of bedrooms"),
        ("Bathrooms", "Number of bathrooms"),
        ("Acreage", "Lot size in acres (0 = not reported)"),
        ("Property Type", "Kind of home, e.g. Single Family, Condo (see Property types above)"),
        ("Square Footage", "Interior floor area in square feet"),
        ("Garage", "Yes if the listing has a garage"),
        ("Parking", "Yes if it has other dedicated parking (underground, carport, covered, visitor)"),
        ("Fireplace", "Yes if the home has at least one fireplace"),
        ("Balcony / Garden / Pool", "Yes if mentioned in the listing's exterior features"),
        ("Waterfront", "Yes if the property is on the water"),
        ("Heating", "Main heating type (forced air, radiant, heat pump, boiler, ...)"),
        ("Basement", "Finished, Partial, or No basement"),
        ("Exterior", "Main exterior finish (vinyl, brick, concrete, wood, ...)"),
        ("Flooring", "Main flooring type"),
        ("Roof", "Main roofing material"),
        ("Sewer", "Sewer connection (municipal, septic, ... 'none' = not reported)"),
    ], columns=["Column", "Description"])
    st.dataframe(dictionary, hide_index=True, width="stretch")

    st.subheader("Data completeness")
    detail_cols = ["Heating", "Basement", "Exterior", "Flooring", "Roof"]
    completeness = pd.DataFrame({
        "Column": detail_cols + ["Lot size (Acreage)"],
        "Reported": [df[c].notna().mean() * 100 for c in detail_cols]
                    + [(df["Acreage"] > 0).mean() * 100],
    }).sort_values("Reported")
    fig = px.bar(completeness, x="Reported", y="Column", orientation="h", text="Reported",
                 color_discrete_sequence=[BLUE], range_x=[0, 110])
    fig.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
    fig.update_layout(xaxis_title="% of listings with this detail", yaxis_title=None, height=320)
    st.plotly_chart(fig, width="stretch")
    st.caption("All other columns are 100% complete. Keep low-completeness columns in mind when drawing conclusions.")
