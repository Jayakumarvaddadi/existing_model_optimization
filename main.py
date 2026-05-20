# ==========================================================
# SCC/DC EXISTING NETWORK OPTIMIZATION ENGINE
# ==========================================================

import pandas as pd
import numpy as np
import requests
import folium

from geopy.distance import geodesic
from tqdm import tqdm

# ==========================================================
# FILE PATHS
# ==========================================================

STORES_FILE = "network.xlsx"
DCS_FILE = "SCC_DC_coordinates.xlsx"

OUTPUT_EXCEL = "output/optimized_mapping.xlsx"
OUTPUT_MAP = "output/optimized_network_map.html"

# ==========================================================
# LOAD FILES
# ==========================================================

print("\nLoading files...\n")

stores = pd.read_excel(STORES_FILE)
dcs = pd.read_excel(DCS_FILE)

print("Files loaded successfully.\n")

# ==========================================================
# COLUMN NAMES
# MODIFY ONLY IF COLUMN NAMES DIFFER
# ==========================================================

STORE_ID_COL = "STORE"

STORE_LAT_COL = "STORE_LAT"

STORE_LON_COL = "STORE_LONG"

CURRENT_DC_COL = "SERVING_SCC/DC"

DC_NAME_COL = "SCC/DC"

DC_LAT_COL = "SCC_LAT"

DC_LON_COL = "SCC_LONG"

# ==========================================================
# CLEAN COLUMN NAMES
# ==========================================================

stores.columns = stores.columns.str.strip()
dcs.columns = dcs.columns.str.strip()

# ==========================================================
# REMOVE BLANK ROWS
# ==========================================================

stores = stores.dropna(
    subset=[
        STORE_LAT_COL,
        STORE_LON_COL
    ]
)

dcs = dcs.dropna(
    subset=[
        DC_LAT_COL,
        DC_LON_COL
    ]
)

# ==========================================================
# DISTANCE FUNCTIONS
# ==========================================================

def haversine_distance(lat1, lon1, lat2, lon2):

    return geodesic(
        (lat1, lon1),
        (lat2, lon2)
    ).km


def osrm_distance(lat1, lon1, lat2, lon2):

    try:

        url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{lon1},{lat1};{lon2},{lat2}"
            f"?overview=false"
        )

        response = requests.get(url, timeout=20)

        data = response.json()

        distance_km = (
            data["routes"][0]["distance"] / 1000
        )

        return round(distance_km, 2)

    except:

        return None

# ==========================================================
# OPTIMIZATION LOGIC
# ==========================================================

results = []

print("\nCalculating optimal SCC/DC mapping...\n")

for _, store in tqdm(
    stores.iterrows(),
    total=len(stores)
):

    # ------------------------------------------------------
    # STORE DETAILS
    # ------------------------------------------------------

    store_id = store[STORE_ID_COL]

    s_lat = store[STORE_LAT_COL]

    s_lon = store[STORE_LON_COL]

    current_dc = store[CURRENT_DC_COL]

    # ------------------------------------------------------
    # CURRENT SCC/DC DISTANCE
    # ------------------------------------------------------

    current_dc_row = dcs[
        dcs[DC_NAME_COL] == current_dc
    ]

    if len(current_dc_row) == 0:

        continue

    current_lat = current_dc_row.iloc[0][DC_LAT_COL]

    current_lon = current_dc_row.iloc[0][DC_LON_COL]

    current_distance = osrm_distance(
        s_lat,
        s_lon,
        current_lat,
        current_lon
    )

    # fallback
    if current_distance is None:

        current_distance = (
            haversine_distance(
                s_lat,
                s_lon,
                current_lat,
                current_lon
            ) * 1.25
        )

    # ------------------------------------------------------
    # CHECK ALL AVAILABLE SCC/DCs
    # ------------------------------------------------------

    best_dc = None

    best_distance = 999999

    for _, dc in dcs.iterrows():

        dc_name = dc[DC_NAME_COL]

        d_lat = dc[DC_LAT_COL]

        d_lon = dc[DC_LON_COL]

        # ----------------------------------------------
        # FAST AIR DISTANCE SCREENING
        # ----------------------------------------------

        air_distance = haversine_distance(
            s_lat,
            s_lon,
            d_lat,
            d_lon
        )

        # ----------------------------------------------
        # ROAD DISTANCE
        # ----------------------------------------------

        road_distance = osrm_distance(
            s_lat,
            s_lon,
            d_lat,
            d_lon
        )

        # fallback
        if road_distance is None:

            road_distance = air_distance * 1.25

        # ----------------------------------------------
        # FIND BEST SCC/DC
        # ----------------------------------------------

        if road_distance < best_distance:

            best_distance = road_distance

            best_dc = dc_name

    # ------------------------------------------------------
    # SAVINGS CALCULATION
    # ------------------------------------------------------

    savings = (
        current_distance - best_distance
    )

    savings_percent = (
        (savings / current_distance) * 100
        if current_distance != 0
        else 0
    )

    # ------------------------------------------------------
    # REMAP LOGIC
    # ------------------------------------------------------

    if savings > 75:

        remap = "YES"

    else:

        remap = "NO"

    # ------------------------------------------------------
    # STORE RESULTS
    # ------------------------------------------------------

    results.append({

        "Store": store_id,

        "Current_DC": current_dc,

        "Current_Distance_km":
            round(current_distance, 2),

        "Optimal_DC":
            best_dc,

        "Optimal_Distance_km":
            round(best_distance, 2),

        "Savings_km":
            round(savings, 2),

        "Savings_Percent":
            round(savings_percent, 2),

        "Remap_Required":
            remap
    })

# ==========================================================
# RESULTS DATAFRAME
# ==========================================================

results_df = pd.DataFrame(results)

# ==========================================================
# SAVE EXCEL OUTPUT
# ==========================================================

results_df.to_excel(
    OUTPUT_EXCEL,
    index=False
)

print("\nExcel output generated.\n")

# ==========================================================
# CREATE INTERACTIVE MAP
# ==========================================================

print("\nGenerating interactive map...\n")

center_lat = stores[STORE_LAT_COL].mean()

center_lon = stores[STORE_LON_COL].mean()

m = folium.Map(

    location=[
        center_lat,
        center_lon
    ],

    zoom_start=5
)

# ==========================================================
# SCC/DC MARKERS
# ==========================================================

for _, dc in dcs.iterrows():

    folium.Marker(

        location=[
            dc[DC_LAT_COL],
            dc[DC_LON_COL]
        ],

        popup=f"""
        SCC/DC: {dc[DC_NAME_COL]}
        """,

        icon=folium.Icon(
            color="red",
            icon="industry"
        )

    ).add_to(m)

# ==========================================================
# STORE MARKERS
# ==========================================================

for _, row in results_df.iterrows():

    store_row = stores[
        stores[STORE_ID_COL] == row["Store"]
    ].iloc[0]

    s_lat = store_row[STORE_LAT_COL]

    s_lon = store_row[STORE_LON_COL]

    optimal_dc_row = dcs[
        dcs[DC_NAME_COL]
        == row["Optimal_DC"]
    ].iloc[0]

    d_lat = optimal_dc_row[DC_LAT_COL]

    d_lon = optimal_dc_row[DC_LON_COL]

    # ------------------------------------------------------
    # COLOR LOGIC
    # ------------------------------------------------------

    if row["Remap_Required"] == "YES":

        color = "red"

    else:

        color = "blue"

    # ------------------------------------------------------
    # STORE POINT
    # ------------------------------------------------------

    folium.CircleMarker(

        location=[
            s_lat,
            s_lon
        ],

        radius=4,

        color=color,

        fill=True,

        fill_opacity=0.7,

        popup=f"""
        <b>Store:</b> {row['Store']}<br>
        <b>Current DC:</b> {row['Current_DC']}<br>
        <b>Optimal DC:</b> {row['Optimal_DC']}<br>
        <b>Current Distance:</b>
        {row['Current_Distance_km']} km<br>
        <b>Optimal Distance:</b>
        {row['Optimal_Distance_km']} km<br>
        <b>Savings:</b>
        {row['Savings_km']} km
        """

    ).add_to(m)

    # ------------------------------------------------------
    # CONNECTION LINE
    # ------------------------------------------------------

    folium.PolyLine(

        locations=[
            [s_lat, s_lon],
            [d_lat, d_lon]
        ],

        color="green",

        weight=1,

        opacity=0.5

    ).add_to(m)

# ==========================================================
# SAVE MAP
# ==========================================================

m.save(OUTPUT_MAP)

print("\nInteractive map generated.\n")

# ==========================================================
# KPI SUMMARY
# ==========================================================

total_current = (
    results_df[
        "Current_Distance_km"
    ].sum()
)

total_optimized = (
    results_df[
        "Optimal_Distance_km"
    ].sum()
)

total_savings = (
    total_current - total_optimized
)

stores_remap = len(

    results_df[
        results_df["Remap_Required"] == "YES"
    ]
)

# ==========================================================
# PRINT KPI SUMMARY
# ==========================================================

print("\n========================================")

print("NETWORK OPTIMIZATION SUMMARY")

print("========================================\n")

print(
    f"Total Current Distance : "
    f"{round(total_current,2)} km"
)

print(
    f"Total Optimized Distance : "
    f"{round(total_optimized,2)} km"
)

print(
    f"Total Savings : "
    f"{round(total_savings,2)} km"
)

print(
    f"Stores Suggested For Remap : "
    f"{stores_remap}"
)

print("\n========================================\n")

print("PROCESS COMPLETED SUCCESSFULLY.\n")
