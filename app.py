import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from mplsoccer import Pitch
import networkx as nx


    df = pd.read_parquet("Eventing.parquet")


# =========================================================
# CONFIG
# =========================================================
st.set_page_config(layout="wide")

st.markdown("""
<style>
.stApp {
    background-color: #0e1117;
    color: white;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# DATA
# =========================================================

def clean(df):
    df["Event Type"] = df["Event Type"].astype(str)
    df["Player"] = df["Player"].astype(str)
    df["Recipient Player"] = df["Recipient Player"].astype(str)

    if "Minute" in df.columns:
        df["Minute"] = pd.to_numeric(df["Minute"], errors="coerce")

    return df

df = clean(df)

# =========================================================
# COLORES EQUIPOS
# =========================================================
team_colors = {
    "FC Barcelona": "#A50044",
    "Real Madrid": "#FFFFFF",
    "Atlético de Madrid": "#C8102E",
    "Athletic Club": "#EE2523",
    "Valencia CF": "#FFFFFF",
    "Villarreal CF": "#FFE600",
    "Sevilla FC": "#FFFFFF",
    "Real Betis": "#00954C",
    "Real Sociedad": "#0067B1",
    "CA Osasuna": "#B4002F",
    "RCD Mallorca": "#E20613",
    "Rayo Vallecano": "#E30613",
    "RC Celta": "#7AC5E3",
    "Getafe CF": "#003DA5",
    "Deportivo Alavés": "#00529F",
    "CD Leganés": "#0046AD",
    "UD Las Palmas": "#FFD100",
    "Girona FC": "#DA291C",
    "Real Valladolid": "#5C2D91"
}

def get_color(team):
    return team_colors.get(team, "#00FFCC")

# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.title("Filtros")

team = st.sidebar.selectbox("Equipo", sorted(df["Team"].dropna().unique()))
team_df = df[df["Team"] == team].copy()

# PARTIDOS JUGADOS (0-38)
if "Match" in team_df.columns:
    matches = sorted(team_df["Match"].dropna().unique())

    match_range = st.sidebar.slider(
        "Partidos jugados",
        1,
        min(38, len(matches)),
        (1, min(38, len(matches)))
    )

    selected_matches = matches[match_range[0]-1 : match_range[1]]
    team_df = team_df[team_df["Match"].isin(selected_matches)]

color = get_color(team)

# =========================================================
# FILTRO CONTEXTO PARTIDO
# =========================================================
st.sidebar.subheader("Contexto de partido")

game_state = st.sidebar.selectbox(
    "Situación",
    ["Todos", "Ganando", "Empatando", "Perdiendo"]
)

# Aplicar filtro
if game_state == "Ganando":
    team_df = team_df[team_df["Diferencia Goles"] > 0]
elif game_state == "Empatando":
    team_df = team_df[team_df["Diferencia Goles"] == 0]
elif game_state == "Perdiendo":
    team_df = team_df[team_df["Diferencia Goles"] < 0]
    
    
# =========================================================
# PASSES / RECOVERIES / SHOTS
# =========================================================

passes = team_df[
    team_df["Event Type"].str.lower().str.contains("pass", na=False)
]

recoveries = team_df[
    team_df["Event Type"].str.lower().str.contains("recover|duel|interception", na=False)
]



shot_types = ["shot", "goal", "saved shot", "missed shot"]

shots = team_df[
    team_df["Event Type"].str.lower().isin(shot_types)
]
# Evitar división por 0
if len(shots) > 0:
    passes_per_shot = len(passes) / len(shots)
else:
    passes_per_shot = 0

# =========================================================
# PPDA (Passes Per Defensive Action)
# =========================================================

# -----------------------------
# 1. ACCIONES DEFENSIVAS (solo presión real)
# -----------------------------
def_actions = team_df[
    team_df["Event Type"].str.lower().str.contains(
        "interception|foul_committed|duel",
        na=False
    )
]

# SOLO en campo rival (zona alta)
def_actions = def_actions[
    def_actions["Start X"] > 50
]

# -----------------------------
# 2. PASSES DEL RIVAL
# -----------------------------
opp_passes = team_df[
    team_df["Event Type"].str.lower().str.contains("pass", na=False)
]

# pases en salida / fase inicial del rival
opp_passes = opp_passes[
    opp_passes["Start X"] < 50
]

# -----------------------------
# 3. CÁLCULO PPDA
# -----------------------------
if len(def_actions) > 0:
    ppda = len(opp_passes) / len(def_actions)
else:
    ppda = None


# =========================================================
# TITLE
# =========================================================
color = get_color(team)

st.markdown("<h1 style='text-align:center'>Dashboard Interactivo La Liga 24/25</h1>", unsafe_allow_html=True)
st.markdown(f"<h2 style='text-align:center;color:{color}'>{team}</h2>", unsafe_allow_html=True)

st.markdown("---")

# =========================================================
# PASSES / RECOVERIES
# =========================================================
passes = team_df[team_df["Event Type"].str.lower().str.contains("pass", na=False)]
recoveries = team_df[team_df["Event Type"].str.lower().str.contains("recover|duel|interception", na=False)]
# =========================================================
# RECUPERACIONES TRAS PÉRDIDA (5-8 SEG)
# =========================================================

team_df = team_df.sort_values(["Minute", "Second"])

team_df["time_sec"] = team_df["Minute"] * 60 + team_df["Second"]

# -----------------------------
# 1. EVENTOS DE PÉRDIDA
# -----------------------------
losses = team_df[
    team_df["Event Type"].str.lower().str.contains(
        "loss|dispossessed|miscontrol|turnover",
        na=False
    )
][["time_sec", "Start X"]]

# -----------------------------
# 2. RECUPERACIONES
# -----------------------------
recoveries = team_df[
    team_df["Event Type"].str.lower().str.contains(
        "tackle|interception|pressure|recover",
        na=False
    )
][["time_sec", "Start X", "Start Y"]]

# -----------------------------
# 3. MATCH 5–8 SEG DESPUÉS DE PÉRDIDA
# -----------------------------
counter_press_recoveries = 0

for loss_time in losses["time_sec"]:
    window = recoveries[
        (recoveries["time_sec"] > loss_time + 5) &
        (recoveries["time_sec"] <= loss_time + 8)
    ]

    counter_press_recoveries += len(window)


# =========================================================
# KPIS
# =========================================================
col1, col2, col3 = st.columns(3)

col1.metric("Pases/Tiro", round(passes_per_shot, 2))
col2.metric("Recuperaciones tras pérdida (5–8s)", counter_press_recoveries)
col3.metric("PPDA", round(ppda, 2) if ppda else "NA")

# =========================================================
# PASS NETWORK
# =========================================================
st.subheader("Red de Pases")

grouped = passes.groupby(["Player", "Recipient Player"]).size().reset_index(name="count")
player_pos = passes.groupby("Player")[["Start X", "Start Y"]].mean()

G = nx.DiGraph()
for _, r in grouped.iterrows():
    G.add_edge(r["Player"], r["Recipient Player"], weight=r["count"])

centrality = nx.degree_centrality(G)
passes_count = passes.groupby("Player").size()

pitch = Pitch(pitch_color='#0e1117', line_color='white')
fig, ax = pitch.draw()

max_pass = grouped["count"].max() if not grouped.empty else 1
max_size = passes_count.max() if len(passes_count) > 0 else 1

for _, r in grouped.iterrows():
    if r["Player"] in player_pos.index and r["Recipient Player"] in player_pos.index:
        x1, y1 = player_pos.loc[r["Player"]]
        x2, y2 = player_pos.loc[r["Recipient Player"]]

        ax.plot(
            [x1, x2],
            [y1, y2],
            linewidth=(r["count"] / max_pass) * 6,
            color="#00ffcc",
            alpha=0.5
        )

for p in player_pos.index:
    x, y = player_pos.loc[p]
    size = (passes_count.get(p, 1) / max_size) * 900
    cent = centrality.get(p, 0)

    ax.scatter(x, y, s=size, color="white", edgecolors="black", zorder=3)
    ax.text(x, y+1.5, p, ha="center", fontsize=8, color="white",
            bbox=dict(facecolor="black", alpha=0.5))
    ax.text(x, y-2, f"{cent:.2f}", ha="center", fontsize=7, color="yellow")

st.pyplot(fig)


# =========================================================
# MAPA DE PRESIÓN
# =========================================================
st.subheader("Mapa de Presión")

pressing = team_df[
    team_df["Event Type"].str.lower().str.contains("press|pressure|duel|interception", na=False)
]

pitch = Pitch(pitch_color='#0e1117', line_color='white')
fig, ax = pitch.draw()

hb = ax.hexbin(
    pressing["Start X"],
    pressing["Start Y"],
    gridsize=15,
    cmap="Reds",
    alpha=0.85
)

fig.colorbar(hb, ax=ax)

st.pyplot(fig)

# =========================================================
# PASS FLOW
# =========================================================
st.subheader("Mapa de Flujo de Pases")

team_passes = passes.dropna(subset=["Start X", "Start Y", "End X", "End Y"])

pitch = Pitch(pitch_type='statsbomb', pitch_color='#0e1117', line_color='white')
fig, ax = pitch.draw(figsize=(10, 6))

bins = (6, 4)

bin_stat = pitch.bin_statistic(
    team_passes["Start X"],
    team_passes["Start Y"],
    statistic='count',
    bins=bins
)

pitch.heatmap(bin_stat, ax=ax, cmap='Blues', alpha=0.6)

pitch.flow(
    team_passes["Start X"],
    team_passes["Start Y"],
    team_passes["End X"],
    team_passes["End Y"],
    cmap='Greys',
    arrow_type='average',
    bins=bins,
    ax=ax
)

st.pyplot(fig)

# =========================================================
# RECOVERIES
# =========================================================
st.subheader("Mapa de Recuperaciones")

pitch = Pitch(pitch_color='#0e1117', line_color='white')
fig, ax = pitch.draw()

ax.hexbin(recoveries["Start X"], recoveries["Start Y"],
          gridsize=14, cmap="Reds", alpha=0.85)

st.pyplot(fig)

# =========================================================
# LOSS MAP 
# =========================================================
st.subheader("Mapa de pérdidas de balón")

losses = team_df[
    team_df["Event Type"].str.lower().str.contains("loss|turnover|miscontrol", na=False)
].dropna(subset=["Start X", "Start Y"])

pitch = Pitch(
    pitch_type='statsbomb',
    pitch_color='#0e1117',
    line_color='white'
)

# ---------------------------------------------------------
# GRID CON CAMPO BIEN DEFINIDO
# ---------------------------------------------------------
fig, axs = pitch.grid(
    figheight=10,
    axis=False,
    grid_height=0.75,
    title_height=0.08,
    endnote_height=0.03,
    title_space=0.02,
    endnote_space=0.02
)

# ---------------------------------------------------------
# ASEGURAR QUE EL PITCH SE DIBUJA EN EL AXIS CORRECTO
# ---------------------------------------------------------
pitch.draw(ax=axs["pitch"])

# ---------------------------------------------------------
# KDE (PÉRDIDAS)
# ---------------------------------------------------------
pitch.kdeplot(
    losses["Start X"],
    losses["Start Y"],
    ax=axs["pitch"],
    fill=True,
    levels=100,
    thresh=0,
    cut=4,
    cmap="mako",
    alpha=0.85
)

# ---------------------------------------------------------
# TITULO
# ---------------------------------------------------------
axs["title"].text(
    0.5, 0.5,
    f"Pérdidas de balón - {team}",
    ha="center",
    va="center",
    color="white",
    fontsize=16
)

st.pyplot(fig)
# =========================================================
# Mapa de Tiros
# =========================================================
st.subheader("Mapa de tiros")

shots = team_df[
    team_df["Event Type"].str.lower().str.contains("shot", na=False)
]

pitch = Pitch(pitch_type='statsbomb', pitch_color='#0e1117', line_color='white')
fig, ax = pitch.draw()

for _, r in shots.iterrows():
    x, y = r["Start X"], r["Start Y"]
    outcome = str(r.get("Outcome", "")).lower()

    if "goal" in outcome:
        ax.scatter(x, y, c="green", marker="o", s=120)
    elif "on target" in outcome or "saved" in outcome:
        ax.scatter(x, y, c="yellow", marker="s", s=90)
    else:
        ax.scatter(x, y, c="white", marker="x", s=80)

st.pyplot(fig)

# =========================================================
# LÍNEAS POR POSICIÓN 
# =========================================================

st.subheader("Altura defensiva del equipo por linea")

pitch = Pitch(pitch_color='#0e1117', line_color='white')
fig, ax = pitch.draw(figsize=(10, 6))

data = team_df.copy()

# ---------------------------------------------------------
# ACCIONES DEFENSIVAS
# ---------------------------------------------------------
def_actions = data[
    data["Event Type"].str.lower().str.contains(
        "tackle|interception|recover|duel|pressure|",
        na=False
    )
].dropna(subset=["Start X", "Start Y", "Player Position"])

if len(def_actions) == 0:
    st.warning("No hay acciones defensivas")
else:

    # -----------------------------------------------------
    # HEATMAP
    # -----------------------------------------------------
    bin_stat = pitch.bin_statistic(
        def_actions["Start X"],
        def_actions["Start Y"],
        statistic='count',
        bins=(25, 25)
    )

    pitch.heatmap(
        bin_stat,
        ax=ax,
        cmap='Reds',
        edgecolors='#0e1117',
        alpha=0.6
    )

    # -----------------------------------------------------
    # SEPARAR POR POSICIONES
    # -----------------------------------------------------
pos = def_actions["Player Position"].str.lower()

# -------------------------------
# DEFINIR GRUPOS DE POSICIONES
# -------------------------------
def_pos = ['cb', 'rcb', 'lcb', 'rb', 'lb', 'rwb', 'lwb']
mid_pos = ['cdm', 'ldm', 'rdm', 'cm', 'lcm', 'rcm', 'cam', 'lam', 'ram', 'lm', 'rm']
att_pos = ['cf', 'lcf', 'rcf', 'lw', 'rw']

# -------------------------------
# FILTRAR
# -------------------------------
defenders = def_actions[pos.isin(def_pos)]
midfielders = def_actions[pos.isin(mid_pos)]
attackers = def_actions[pos.isin(att_pos)]

# -----------------------------------------------------
# CALCULAR LÍNEAS
# -----------------------------------------------------
if len(defenders) > 0:
    def_line = defenders["Start X"].mean()
    ax.axvline(def_line, color='cyan', linewidth=3)
    ax.text(def_line, 5, "Defensive Line", color='cyan', ha='center')

if len(midfielders) > 0:
    mid_line = midfielders["Start X"].mean()
    ax.axvline(mid_line, color='yellow', linewidth=3)
    ax.text(mid_line, 5, "Midfield Line", color='yellow', ha='center')

if len(attackers) > 0:
    att_line = attackers["Start X"].mean()
    ax.axvline(att_line, color='red', linewidth=3)
    ax.text(att_line, 5, "Attacking Line", color='red', ha='center')

# -----------------------------------------------------
# MÉTRICA CLAVE
# -----------------------------------------------------
if len(defenders) > 0 and len(attackers) > 0:
    compactness = att_line - def_line
    st.metric("Compactación del equipo", round(compactness, 2))

st.pyplot(fig)

# =========================================================
# TOP COMBINATIONS
# =========================================================
st.subheader("Top combinaciones")

combo = grouped.sort_values("count", ascending=False).head(15)
st.dataframe(combo, use_container_width=True)