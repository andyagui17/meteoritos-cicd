"""
Generador de sitio web estático para el análisis de meteoritos en el pipeline de CI/CD.

Este script:
1. Lee el dataset de meteoritos desde datos/meteoritos.csv usando pandas.
2. Calcula métricas clave (totales, recuentos 'Fell'/'Found', masa media ignorando nulos,
   y cantidad de registros sin masa).
3. Genera un gráfico con las 10 clasificaciones ('recclass') más frecuentes usando matplotlib
   y lo guarda en public/grafico_clases.png.
4. Genera una página HTML responsiva en public/index.html inyectando dinámicamente todos
   los datos e indicadores calculados mediante f-strings.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Configuración de backend headless para matplotlib antes de importar pyplot (imprescindible en CI/CD)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def resolver_ruta_csv(ruta_argumento: str | None = None) -> Path:
    """
    Resuelve la ruta del archivo CSV a procesar.
    Permite argumento explícito, busca 'datos/meteoritos.csv' en el directorio
    de trabajo actual o relativo a la raíz del repositorio.
    """
    if ruta_argumento:
        return Path(ruta_argumento)

    ruta_relativa = Path("datos/meteoritos.csv")
    if ruta_relativa.exists():
        return ruta_relativa

    ruta_script = Path(__file__).resolve().parent.parent / "datos" / "meteoritos.csv"
    if ruta_script.exists():
        return ruta_script

    return ruta_relativa


def generar_grafico_clasificaciones(df: pd.DataFrame, ruta_salida: Path) -> None:
    """
    Genera un gráfico de barras con las 10 clasificaciones ('recclass') más frecuentes
    y lo almacena en la ruta especificada.
    """
    top_clases = df["recclass"].value_counts().head(10)

    # Configuración del gráfico
    plt.figure(figsize=(10, 5.5))
    barras = plt.bar(
        top_clases.index.astype(str),
        top_clases.values,
        color="#2b6cb0",
        edgecolor="#1a365d",
        alpha=0.9,
    )

    plt.title("Top 10 Clasificaciones de Meteoritos más Frecuentes", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Clasificación (recclass)", fontsize=11, labelpad=10)
    plt.ylabel("Cantidad de Meteoritos", fontsize=11, labelpad=10)
    plt.xticks(rotation=40, ha="right", fontsize=9)
    plt.grid(axis="y", linestyle="--", alpha=0.6)

    # Añadir etiquetas con el valor exacto sobre cada barra
    for barra in barras:
        altura = barra.get_height()
        plt.annotate(
            f"{int(altura):,}",
            xy=(barra.get_x() + barra.get_width() / 2, altura),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
            color="#2d3748",
        )

    plt.tight_layout()
    plt.savefig(ruta_salida, dpi=150)
    plt.close()


def generar_html(df: pd.DataFrame, ruta_html: Path) -> None:
    """
    Calcula los indicadores mediante pandas e inyecta dinámicamente los valores
    en una plantilla HTML responsiva guardada en public/index.html.
    """
    # -------------------------------------------------------------------------
    # 1. Cálculos de indicadores clave con Pandas
    # -------------------------------------------------------------------------
    total_registros = len(df)

    conteo_fall = df["fall"].value_counts()
    total_fell = int(conteo_fall.get("Fell", 0))
    total_found = int(conteo_fall.get("Found", 0))

    # Masa media en gramos: calculada únicamente con valores disponibles (ignora nulos)
    masas_validas = df["mass (g)"].dropna()
    masa_media = float(masas_validas.mean()) if not masas_validas.empty else 0.0

    # Cantidad de registros sin información de masa
    sin_info_masa = int(df["mass (g)"].isna().sum())

    # -------------------------------------------------------------------------
    # 2. Ranking: Top 10 meteoritos de mayor masa
    # -------------------------------------------------------------------------
    top_10_masa = df.dropna(subset=["mass (g)"]).sort_values(by="mass (g)", ascending=False).head(10)

    filas_ranking_html = []
    for pos, (_, fila) in enumerate(top_10_masa.iterrows(), start=1):
        nombre = fila.get("name", "N/A")
        clase = fila.get("recclass", "N/A")
        masa = f"{float(fila['mass (g)']):,.2f} g"
        estado = fila.get("fall", "N/A")
        anio = str(int(fila["year"])) if pd.notna(fila.get("year")) else "Desconocido"

        filas_ranking_html.append(
            f"<tr>"
            f"<td class='text-center'><strong>#{pos}</strong></td>"
            f"<td><strong>{nombre}</strong></td>"
            f"<td><code>{clase}</code></td>"
            f"<td class='text-right'>{masa}</td>"
            f"<td class='text-center'><span class='badge badge-{str(estado).lower()}'>{estado}</span></td>"
            f"<td class='text-center'>{anio}</td>"
            f"</tr>"
        )
    ranking_tbody = "\n".join(filas_ranking_html)

    # -------------------------------------------------------------------------
    # 3. Comprobación de CI/CD: Últimos 10 registros del CSV (tail(10))
    # -------------------------------------------------------------------------
    ultimos_10 = df.tail(10)

    filas_ultimos_html = []
    for _, fila in ultimos_10.iterrows():
        f_id = fila.get("id", "")
        f_name = fila.get("name", "")
        f_recclass = fila.get("recclass", "")
        f_mass = f"{float(fila['mass (g)']):,.2f}" if pd.notna(fila.get("mass (g)")) else "—"
        f_fall = fila.get("fall", "")
        f_year = str(int(fila["year"])) if pd.notna(fila.get("year")) else "—"
        f_lat = f"{float(fila['reclat']):.4f}" if pd.notna(fila.get("reclat")) else "—"
        f_long = f"{float(fila['reclong']):.4f}" if pd.notna(fila.get("reclong")) else "—"

        filas_ultimos_html.append(
            f"<tr>"
            f"<td class='text-center'>{f_id}</td>"
            f"<td><strong>{f_name}</strong></td>"
            f"<td><code>{f_recclass}</code></td>"
            f"<td class='text-right'>{f_mass}</td>"
            f"<td class='text-center'><span class='badge badge-{str(f_fall).lower()}'>{f_fall}</span></td>"
            f"<td class='text-center'>{f_year}</td>"
            f"<td class='text-right'>{f_lat}</td>"
            f"<td class='text-right'>{f_long}</td>"
            f"</tr>"
        )
    ultimos_tbody = "\n".join(filas_ultimos_html)

    # -------------------------------------------------------------------------
    # 4. Metadatos de ejecución
    # -------------------------------------------------------------------------
    fecha_generacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_sha = os.environ.get("GITHUB_SHA", "Ejecución Local")
    estudiante_nombre = os.environ.get("ESTUDIANTE_NOMBRE", "Andres Aguirre Cortez")

    # -------------------------------------------------------------------------
    # 5. Construcción completa del documento HTML
    # -------------------------------------------------------------------------
    html_contenido = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análisis de Meteoritos - Pipeline CI/CD</title>
    <style>
        :root {{
            --bg-color: #f7fafc;
            --card-bg: #ffffff;
            --text-main: #2d3748;
            --text-muted: #718096;
            --primary: #2b6cb0;
            --primary-light: #ebf8ff;
            --accent: #319795;
            --warning-bg: #fffaf0;
            --warning-border: #dd6b20;
            --warning-text: #9c4221;
            --border-color: #e2e8f0;
            --badge-fell: #e53e3e;
            --badge-found: #3182ce;
            --font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: var(--font-family);
            line-height: 1.6;
            padding: 1.5rem;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            background: var(--card-bg);
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            border-top: 5px solid var(--primary);
        }}

        header h1 {{
            font-size: 2rem;
            color: #1a202c;
            margin-bottom: 0.5rem;
        }}

        .header-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 1.5rem;
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-bottom: 1.25rem;
        }}

        .header-meta span strong {{
            color: var(--text-main);
        }}

        .alert-banner {{
            background-color: var(--warning-bg);
            border-left: 4px solid var(--warning-border);
            color: var(--warning-text);
            padding: 0.85rem 1.25rem;
            border-radius: 6px;
            font-size: 0.95rem;
            font-weight: 500;
        }}

        .grid-kpis {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }}

        .kpi-card {{
            background: var(--card-bg);
            border-radius: 10px;
            padding: 1.5rem;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
            border: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}

        .kpi-title {{
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
            font-weight: 600;
        }}

        .kpi-value {{
            font-size: 1.85rem;
            font-weight: 700;
            color: var(--primary);
        }}

        .kpi-subtext {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }}

        .section-card {{
            background: var(--card-bg);
            border-radius: 10px;
            padding: 1.75rem;
            margin-bottom: 2rem;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
            border: 1px solid var(--border-color);
        }}

        .section-title {{
            font-size: 1.35rem;
            font-weight: 700;
            color: #1a202c;
            margin-bottom: 1.25rem;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 0.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        .chart-container {{
            text-align: center;
            padding: 1rem 0;
        }}

        .chart-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            border: 1px solid var(--border-color);
        }}

        .table-responsive {{
            overflow-x: auto;
            width: 100%;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.92rem;
        }}

        th {{
            background-color: #edf2f7;
            color: #4a5568;
            font-weight: 600;
            text-align: left;
            padding: 0.75rem 1rem;
            border-bottom: 2px solid var(--border-color);
            white-space: nowrap;
        }}

        td {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border-color);
            white-space: nowrap;
        }}

        tr:nth-child(even) {{
            background-color: #f7fafc;
        }}

        tr:hover {{
            background-color: #ebf8ff;
        }}

        .text-center {{
            text-align: center;
        }}

        .text-right {{
            text-align: right;
        }}

        code {{
            background-color: #edf2f7;
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-size: 0.85em;
            color: #805ad5;
        }}

        .badge {{
            display: inline-block;
            padding: 0.25rem 0.6rem;
            font-size: 0.75rem;
            font-weight: 700;
            border-radius: 12px;
            color: #ffffff;
            text-transform: uppercase;
        }}

        .badge-fell {{
            background-color: var(--badge-fell);
        }}

        .badge-found {{
            background-color: var(--badge-found);
        }}

        footer {{
            margin-top: 3rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border-color);
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            color: var(--text-muted);
            font-size: 0.85rem;
        }}

        footer .commit-tag {{
            background: #edf2f7;
            color: #2d3748;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-family: monospace;
        }}

        @media (max-width: 768px) {{
            body {{
                padding: 0.75rem;
            }}

            header {{
                padding: 1.25rem;
            }}

            header h1 {{
                font-size: 1.5rem;
            }}

            .section-card {{
                padding: 1.25rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Encabezado Principal -->
        <header>
            <h1>Portal de Análisis de Meteoritos</h1>
            <div class="header-meta">
                <span><strong>Estudiante:</strong> {estudiante_nombre}</span>
                <span><strong>Fuente de datos:</strong> NASA / The Meteoritical Society</span>
            </div>
            <div class="alert-banner">
                <strong>Aviso:</strong> Este portal contiene modificaciones simuladas con fines educativos como parte de un pipeline automatizado de CI/CD.
            </div>
        </header>

        <!-- Indicadores Clave (KPIs) -->
        <section class="grid-kpis">
            <div class="kpi-card">
                <div class="kpi-title">Total de Registros</div>
                <div class="kpi-value">{total_registros:,}</div>
                <div class="kpi-subtext">Meteoritos catalogados en el archivo</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Estado: Fell / Found</div>
                <div class="kpi-value">{total_fell:,} <span style="font-size: 1rem; color: var(--text-muted);">/</span> {total_found:,}</div>
                <div class="kpi-subtext">Fell (vistos caer) vs Found (hallados)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Masa Media</div>
                <div class="kpi-value">{masa_media:,.2f} <span style="font-size: 1rem;">g</span></div>
                <div class="kpi-subtext">Calculada ignorando valores nulos</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Sin Información de Masa</div>
                <div class="kpi-value">{sin_info_masa:,}</div>
                <div class="kpi-subtext">Registros con masa nula o no reportada</div>
            </div>
        </section>

        <!-- Gráfico de Clasificaciones -->
        <section class="section-card">
            <div class="section-title">
                Distribución de las 10 Clasificaciones más Frecuentes
            </div>
            <div class="chart-container">
                <img src="grafico_clases.png" alt="Gráfico de las 10 clasificaciones más frecuentes">
            </div>
        </section>

        <!-- Ranking: Top 10 Meteoritos de Mayor Masa -->
        <section class="section-card">
            <div class="section-title">
                Top 10 Meteoritos de Mayor Masa
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th class="text-center">Posición</th>
                            <th>Nombre</th>
                            <th>Clasificación</th>
                            <th class="text-right">Masa</th>
                            <th class="text-center">Estado</th>
                            <th class="text-center">Año</th>
                        </tr>
                    </thead>
                    <tbody>
{ranking_tbody}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Comprobación de CI/CD: Últimos 10 Registros -->
        <section class="section-card">
            <div class="section-title">
                Comprobación de CI/CD: Últimos 10 Registros del Dataset (tail(10))
            </div>
            <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1rem;">
                Visualización de los registros más recientes añadidos al CSV para verificación de despliegue continuo.
            </p>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th class="text-center">ID</th>
                            <th>Nombre</th>
                            <th>Clasificación</th>
                            <th class="text-right">Masa (g)</th>
                            <th class="text-center">Fall</th>
                            <th class="text-center">Año</th>
                            <th class="text-right">Reclat</th>
                            <th class="text-right">Reclong</th>
                        </tr>
                    </thead>
                    <tbody>
{ultimos_tbody}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Metadatos de Generación -->
        <footer>
            <div>
                <strong>Fecha y hora de generación:</strong> {fecha_generacion}
            </div>
            <div>
                <strong>Identificador de Commit:</strong> <span class="commit-tag">{commit_sha}</span>
            </div>
        </footer>
    </div>
</body>
</html>
"""

    with open(ruta_html, mode="w", encoding="utf-8") as f:
        f.write(html_contenido)


def main() -> None:
    """
    Función orquestadora principal:
    1. Asegura la existencia del directorio public/
    2. Carga y procesa el CSV
    3. Genera el gráfico y la página HTML
    """
    ruta_arg = sys.argv[1] if len(sys.argv) > 1 else None
    ruta_csv = resolver_ruta_csv(ruta_arg)

    if not ruta_csv.is_file():
        print(f"Error: No se encontró el archivo CSV en '{ruta_csv}'.", file=sys.stderr)
        sys.exit(1)

    # Crear directorio public si no existe
    dir_public = Path("public")
    dir_public.mkdir(parents=True, exist_ok=True)

    print(f"Leyendo dataset desde '{ruta_csv}'...")
    # Cargar CSV respetando tipos de columnas
    df = pd.read_csv(ruta_csv)

    ruta_grafico = dir_public / "grafico_clases.png"
    print(f"Generando gráfico de clasificaciones en '{ruta_grafico}'...")
    generar_grafico_clasificaciones(df, ruta_grafico)

    ruta_html = dir_public / "index.html"
    print(f"Generando página estática en '{ruta_html}'...")
    generar_html(df, ruta_html)

    print("Generación completada exitosamente.")


if __name__ == "__main__":
    main()
