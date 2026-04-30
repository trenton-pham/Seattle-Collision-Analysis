### Vision Zero Collision Dashboard
### Courtesy of Claude Code, adopted by trentonpham

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
from matplotlib.colors import LogNorm
from scipy.stats import gaussian_kde

st.set_page_config(
    page_title="Seattle Collision Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_PATH = "data/processed/Collision_Processed.parquet"
NEIGHBORHOODS_PATH = "data/processed/Neighborhood_Map_Atlas_Neighborhoods.geojson"
DOWNTOWN_BBOX = {"y_min": 47.595, "y_max": 47.620, "x_min": -122.345, "x_max": -122.320}
HEATMAP_GRID_N = 150

DARK_BG = "#0E1117"
PANEL_BG = "#161B22"
GRID_COLOR = "#30363D"  
TEXT_COLOR = "#E6EDF3"
ACCENT = "#3B82F6"
ACCENT_WARM = "#F97316"

st.markdown(
    """
    <style>
      .block-container { padding-top: 1rem; padding-bottom: 1rem; padding-left: 2rem; padding-right: 2rem; }
      [data-testid="stMetric"] {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 12px 16px;
      }
      [data-testid="stMetricLabel"] p { font-size: 0.8rem; color: #8B949E; }
      [data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
      div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #161B22;
        border-radius: 10px;
      }
      h1 { font-size: 1.6rem !important; margin-bottom: 0.25rem !important; }
      h2 { font-size: 1.1rem !important; margin: 0 0 0.4rem 0 !important; }
      h3 { font-size: 0.95rem !important; margin: 0 0 0.4rem 0 !important; color: #C9D1D9; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="Loading neighborhoods…")
def load_neighborhoods():
    nbh = gpd.read_file(NEIGHBORHOODS_PATH)
    if nbh.crs is None or nbh.crs.to_epsg() != 4326:
        nbh = nbh.to_crs(epsg=4326)
    return nbh


@st.cache_data(show_spinner="Loading collision data…")
def load_collisions():
    gdf = gpd.read_parquet(DATA_PATH)
    if "SEVERITY" not in gdf.columns:
        gdf["SEVERITY"] = (
            gdf["INJURIES"].fillna(0)
            + gdf["SERIOUSINJURIES"].fillna(0) * 3
            + gdf["FATALITIES"].fillna(0) * 5
        )
    if "X" not in gdf.columns or "Y" not in gdf.columns:
        gdf["X"] = gdf.geometry.x
        gdf["Y"] = gdf.geometry.y
    gdf = gdf.dropna(subset=["X", "Y"])
    return gdf


@st.cache_data
def make_grid(xmin, xmax, ymin, ymax, n=150):
    x = np.linspace(xmin, xmax, n)
    y = np.linspace(ymin, ymax, n)
    xx, yy = np.meshgrid(x, y)
    return xx, yy, np.vstack([xx.ravel(), yy.ravel()])


@st.cache_data(show_spinner="Computing pre/post-2020 KDE…")
def kde_pre_post(coords_pre, coords_post, grid_points, shape):
    z_pre = gaussian_kde(coords_pre)(grid_points).reshape(shape)
    z_post = gaussian_kde(coords_post)(grid_points).reshape(shape)
    return z_post - z_pre


def style_axes(ax, title=None):
    ax.set_facecolor(PANEL_BG)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    ax.tick_params(colors=TEXT_COLOR, labelsize=8)
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)
    if title:
        ax.set_title(title, color=TEXT_COLOR, fontsize=10, fontweight="bold", loc="left")
    ax.grid(color=GRID_COLOR, alpha=0.4, linewidth=0.5)


def themed_fig(figsize):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor(PANEL_BG)
    return fig, ax


gdf = load_collisions()
neighborhoods = load_neighborhoods()
nb_minx, nb_miny, nb_maxx, nb_maxy = neighborhoods.total_bounds
xx, yy, grid_points = make_grid(gdf["X"].min(), gdf["X"].max(), gdf["Y"].min(), gdf["Y"].max())

with st.sidebar:
    st.markdown("### Filters")
    year_min, year_max = int(gdf["YEAR"].min()), int(gdf["YEAR"].max())
    year_range = st.slider("Year range", year_min, year_max, (year_min, year_max))
    sev_cap = int(min(gdf["SEVERITY"].quantile(0.99), 20))
    min_sev = st.slider("Minimum severity score", 0, sev_cap, 0)
    severe_only = st.checkbox("Severe only (fatal/serious)")
    st.divider()
    st.caption(
        "Severity = INJURIES + 3·SERIOUSINJURIES + 5·FATALITIES.    "
        "Spatial-shift uses the full dataset and ignores filters."
    )

mask = (gdf["YEAR"] >= year_range[0]) & (gdf["YEAR"] <= year_range[1]) & (gdf["SEVERITY"] >= min_sev)
if severe_only:
    mask &= (gdf["FATALITIES"] > 0) | (gdf["SERIOUSINJURIES"] > 0)
df_f = gdf[mask]

st.markdown("# Seattle Collision Dashboard")
st.caption(
    f"SDOT collision records · {year_range[0]}–{year_range[1]} · {len(df_f):,} of {len(gdf):,} rows shown"
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Collisions", f"{len(df_f):,}")
k2.metric("Mean severity", f"{df_f['SEVERITY'].mean():.2f}" if len(df_f) else "—")
k3.metric("Serious injuries", f"{int(df_f['SERIOUSINJURIES'].sum()):,}")
k4.metric("Fatalities", f"{int(df_f['FATALITIES'].sum()):,}")

if df_f.empty:
    st.warning("No collisions match the current filters.")
    st.stop()

st.markdown("")

row1_left, row1_right = st.columns([3, 2], gap="small")

with row1_left:
    with st.container(border=True):
        st.markdown("##### Collision heatmap")
        st.caption(f"{HEATMAP_GRID_N}×{HEATMAP_GRID_N} grid, weighted by VEHCOUNT (log scale).")

        weights = df_f["VEHCOUNT"].fillna(1).to_numpy()
        xedges = np.linspace(nb_minx, nb_maxx, HEATMAP_GRID_N + 1)
        yedges = np.linspace(nb_miny, nb_maxy, HEATMAP_GRID_N + 1)
        H, _, _ = np.histogram2d(
            df_f["X"].to_numpy(),
            df_f["Y"].to_numpy(),
            bins=[xedges, yedges],
            weights=weights,
        )
        H_masked = np.ma.masked_where(H.T <= 0, H.T)

        fig_hm, ax_hm = themed_fig((8, 6.2))
        if H_masked.count():
            mesh = ax_hm.pcolormesh(
                xedges, yedges, H_masked,
                cmap="YlOrRd",
                norm=LogNorm(vmin=max(H_masked.min(), 1), vmax=H_masked.max()),
                shading="flat",
            )
            cb = fig_hm.colorbar(mesh, ax=ax_hm, label="Vehicles (log)")
            cb.ax.tick_params(colors=TEXT_COLOR, labelsize=7)
            cb.ax.yaxis.label.set_color(TEXT_COLOR)
        neighborhoods.boundary.plot(ax=ax_hm, color="#9aa4b2", linewidth=0.4)
        ax_hm.set_xlim(nb_minx, nb_maxx)
        ax_hm.set_ylim(nb_miny, nb_maxy)
        ax_hm.set_aspect("equal")
        style_axes(ax_hm)
        ax_hm.set_xlabel("Longitude", fontsize=8)
        ax_hm.set_ylabel("Latitude", fontsize=8)
        fig_hm.tight_layout()
        st.pyplot(fig_hm, use_container_width=True)

with row1_right:
    with st.container(border=True):
        st.markdown("##### KDE density")
        st.caption("All collisions vs severe-only.")
        coords_all = np.vstack([df_f.geometry.x, df_f.geometry.y])

        fig_kde, axes_kde = plt.subplots(figsize=(5.2, 7.3))
        fig_kde.patch.set_facecolor(PANEL_BG)
        style_axes(axes_kde)

        if coords_all.shape[1] >= 2:
            z_all = gaussian_kde(coords_all)(grid_points).reshape(xx.shape)
            axes_kde.contourf(xx, yy, z_all, cmap="YlOrRd", levels=20)
            style_axes(axes_kde, "All collisions")
        else:
            axes_kde.text(0.5, 0.5, "Not enough data", ha="center", va="center", color=TEXT_COLOR, transform=axes_kde.transAxes)
            
        fig_kde.tight_layout()
        st.pyplot(fig_kde, use_container_width=True)

row2_left, row2_right = st.columns([3, 2], gap="small")

with row2_left:
    with st.container(border=True):
        st.markdown("##### Spatial shift: post-2020 − pre-2020")
        st.caption("Red = increase, blue = decrease. Uses full dataset, ignores filters.")
        pre_full = gdf[gdf["YEAR"] < 2020]
        post_full = gdf[gdf["YEAR"] >= 2020]
        coords_pre = np.vstack([pre_full.geometry.x, pre_full.geometry.y])
        coords_post = np.vstack([post_full.geometry.x, post_full.geometry.y])
        z_diff = kde_pre_post(coords_pre, coords_post, grid_points, xx.shape)

        fig_shift, ax_shift = themed_fig((8, 5.5))
        vlim = float(np.abs(z_diff).max())
        cs = ax_shift.contourf(xx, yy, z_diff, cmap="RdBu_r", levels=20, vmin=-vlim, vmax=vlim)
        cb = fig_shift.colorbar(cs, ax=ax_shift)
        cb.ax.tick_params(colors=TEXT_COLOR, labelsize=7)
        style_axes(ax_shift, "Density change")
        fig_shift.tight_layout()
        st.pyplot(fig_shift, use_container_width=True)

with row2_right:
    downtown_mask = (
        (df_f["Y"] >= DOWNTOWN_BBOX["y_min"]) & (df_f["Y"] <= DOWNTOWN_BBOX["y_max"])
        & (df_f["X"] >= DOWNTOWN_BBOX["x_min"]) & (df_f["X"] <= DOWNTOWN_BBOX["x_max"])
    )
    df_dt = df_f[downtown_mask]
    df_outer = df_f[~downtown_mask]
    dt_area = (DOWNTOWN_BBOX["y_max"] - DOWNTOWN_BBOX["y_min"]) * (
        DOWNTOWN_BBOX["x_max"] - DOWNTOWN_BBOX["x_min"]
    )
    full_area = (gdf["Y"].max() - gdf["Y"].min()) * (gdf["X"].max() - gdf["X"].min())
    outer_area = full_area - dt_area
    dt_count = df_dt.groupby("YEAR").size().reset_index(name="COUNT")
    outer_count = df_outer.groupby("YEAR").size().reset_index(name="COUNT")
    dt_count["DENSITY"] = dt_count["COUNT"] / dt_area
    outer_count["DENSITY"] = outer_count["COUNT"] / outer_area
    dt_sev = df_dt.groupby("YEAR")["SEVERITY"].mean().reset_index()
    outer_sev = df_outer.groupby("YEAR")["SEVERITY"].mean().reset_index()

    with st.container(border=True):
        st.markdown("##### Downtown vs outer — density")
        fig_d, ax_d = themed_fig((5.2, 2.8))
        if len(dt_count):
            ax_d.plot(dt_count["YEAR"], dt_count["DENSITY"], marker="o", color=ACCENT, label="Downtown")
        if len(outer_count):
            ax_d.plot(outer_count["YEAR"], outer_count["DENSITY"], marker="o", color=ACCENT_WARM, label="Outer")
        ax_d.set_ylabel("Collisions / unit area", fontsize=8)
        ax_d.legend(facecolor=PANEL_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)
        style_axes(ax_d)
        fig_d.tight_layout()
        st.pyplot(fig_d, use_container_width=True)

    with st.container(border=True):
        st.markdown("##### Downtown vs outer — mean severity")
        fig_s, ax_s = themed_fig((5.2, 2.8))
        if len(dt_sev):
            ax_s.plot(dt_sev["YEAR"], dt_sev["SEVERITY"], marker="o", color=ACCENT, label="Downtown")
        if len(outer_sev):
            ax_s.plot(outer_sev["YEAR"], outer_sev["SEVERITY"], marker="o", color=ACCENT_WARM, label="Outer")
        ax_s.set_ylabel("Mean severity", fontsize=8)
        ax_s.legend(facecolor=PANEL_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)
        style_axes(ax_s)
        fig_s.tight_layout()
        st.pyplot(fig_s, use_container_width=True)