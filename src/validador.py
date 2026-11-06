"""
Validador de datos para el pipeline de CI/CD de meteoritos.

Este script valida la integridad y calidad del archivo CSV de meteoritos
(por defecto en datos/meteoritos.csv), aplicando reglas estrictas sobre
estructura, tipos de datos, rangos y valores permitidos.
Si detecta algún registro no válido, detiene inmediatamente la ejecución
con código de salida 1 (exit code 1). Si todos los datos son válidos, finaliza
con código de salida 0.
"""

import csv
import io
import math
import re
import sys
from pathlib import Path

# Lista exacta de columnas requeridas en el archivo CSV
COLUMNAS_ESPERADAS = [
    "id",
    "name",
    "recclass",
    "mass (g)",
    "fall",
    "year",
    "reclat",
    "reclong",
]

# Valores permitidos exactamente para la columna 'fall'
VALORES_FALL_PERMITIDOS = {"Fell", "Found"}

# Rangos para validación de años y coordenadas
ANIO_MIN = 1
ANIO_MAX = 2026
LAT_MIN = -90.0
LAT_MAX = 90.0
LONG_MIN = -180.0
LONG_MAX = 180.0


def es_nulo_o_vacio(valor: str | None) -> bool:
    """
    Determina si un valor textual se considera nulo, vacío o no presente.
    Contempla cadenas vacías, espacios en blanco y representaciones comunes
    de valores nulos en CSV/DataFrames ('nan', 'null', 'none', 'na').
    """
    if valor is None:
        return True
    limpio = valor.strip()
    return limpio == "" or limpio.lower() in {"nan", "null", "none", "na"}


def reportar_error(num_fila: int, campo: str, motivo: str) -> None:
    """
    Imprime en consola un mensaje de error claro y descriptivo indicando
    el número de fila, el campo infractor y el motivo del rechazo,
    y termina inmediatamente la ejecución con código de salida 1.
    """
    print(f"Error en fila {num_fila} - Campo '{campo}': {motivo}")
    sys.exit(1)


def extraer_anio(valor: str) -> int | None:
    """
    Extrae el año numérico entero de una cadena de texto.
    Soporta múltiples formatos comunes en datos de meteoritos:
      - Entero directo: "1880", "861"
      - Formato flotante: "1880.0"
      - Formato de fecha NASA / EE.UU.: "01/01/1880 12:00:00 AM", "01/01/1880"
      - Formato de fecha ISO: "1880-01-01T00:00:00.000", "1880-01-01"
      - Año de 4 dígitos aislado: busca secuencias de 4 dígitos

    Retorna el año como entero o None si no se puede extraer.
    """
    s = valor.strip()

    # 1. Entero directo (con o sin signo)
    if re.fullmatch(r"[-+]?\d+", s):
        return int(s)

    # 2. Flotante con parte decimal en cero (ej. "1950.0")
    match_float = re.fullmatch(r"[-+]?(\d+)\.0+", s)
    if match_float:
        return int(match_float.group(1))

    # 3. Formato de fecha NASA (MM/DD/YYYY ... o DD/MM/YYYY ...)
    match_mdy = re.match(r"^\d{1,2}[-/]\d{1,2}[-/](\d{1,4})(?:\s+.*)?$", s)
    if match_mdy:
        return int(match_mdy.group(1))

    # 4. Formato de fecha ISO (YYYY-MM-DD...)
    match_ymd = re.match(r"^(\d{3,4})[-/]\d{1,2}[-/]\d{1,2}", s)
    if match_ymd:
        return int(match_ymd.group(1))

    # 5. Secuencia aislada de 4 dígitos (búsqueda general)
    match_4dig = re.search(r"\b(\d{4})\b", s)
    if match_4dig:
        return int(match_4dig.group(1))

    return None


def validar_estructura(encabezados: list[str]) -> None:
    """
    Regla 1: Estructura del archivo.
    Verifica que estén presentes exactamente las columnas esperadas,
    sin columnas faltantes ni columnas no permitidas.
    """
    if not encabezados:
        reportar_error(1, "Estructura", "El archivo CSV no contiene encabezados.")

    # Verificar si existen columnas duplicadas en el encabezado
    if len(encabezados) != len(set(encabezados)):
        reportar_error(1, "Estructura", "El encabezado contiene columnas duplicadas.")

    columnas_faltantes = [col for col in COLUMNAS_ESPERADAS if col not in encabezados]
    columnas_sobrantes = [col for col in encabezados if col not in COLUMNAS_ESPERADAS]

    if columnas_faltantes or columnas_sobrantes:
        detalles = []
        if columnas_faltantes:
            detalles.append(f"columnas faltantes: {columnas_faltantes}")
        if columnas_sobrantes:
            detalles.append(f"columnas no permitidas: {columnas_sobrantes}")
        reportar_error(
            1,
            "Estructura",
            f"El archivo debe contener exactamente las columnas {COLUMNAS_ESPERADAS}. ({', '.join(detalles)})",
        )


def validar_fila(
    fila: dict[str, str | None],
    num_fila: int,
    ids_vistos: set[int],
) -> None:
    """
    Aplica las reglas de negocio sobre un registro individual (fila) del CSV.
    """
    # Verificación de integridad de columnas en la fila
    if None in fila:
        reportar_error(
            num_fila,
            "Estructura de fila",
            "La fila contiene más campos de los definidos en el encabezado.",
        )

    # -------------------------------------------------------------------------
    # Regla: id
    # Debe ser un entero positivo, obligatorio y sin duplicados en todo el archivo.
    # -------------------------------------------------------------------------
    raw_id = fila.get("id")
    if raw_id is None or raw_id.strip() == "":
        reportar_error(num_fila, "id", "El campo es obligatorio y no puede estar vacío.")

    id_str = raw_id.strip()
    # Rechazar números flotantes o cadenas no enteras
    if "." in id_str:
        reportar_error(num_fila, "id", f"Debe ser un número entero (recibido: '{id_str}').")

    try:
        val_id = int(id_str)
    except ValueError:
        reportar_error(num_fila, "id", f"Debe ser un entero válido (recibido: '{id_str}').")

    if val_id <= 0:
        reportar_error(
            num_fila,
            "id",
            f"Debe ser un entero positivo mayor a cero (recibido: {val_id}).",
        )

    if val_id in ids_vistos:
        reportar_error(
            num_fila,
            "id",
            f"Identificador duplicado detectado (id: {val_id}).",
        )
    ids_vistos.add(val_id)

    # -------------------------------------------------------------------------
    # Regla: name
    # Texto obligatorio. No debe quedar vacío tras aplicar strip().
    # -------------------------------------------------------------------------
    raw_name = fila.get("name")
    if raw_name is None or raw_name.strip() == "":
        reportar_error(
            num_fila,
            "name",
            "El campo es obligatorio y no puede estar vacío tras quitar espacios.",
        )

    # -------------------------------------------------------------------------
    # Regla: recclass
    # Texto obligatorio. No debe quedar vacío tras aplicar strip().
    # -------------------------------------------------------------------------
    raw_recclass = fila.get("recclass")
    if raw_recclass is None or raw_recclass.strip() == "":
        reportar_error(
            num_fila,
            "recclass",
            "El campo es obligatorio y no puede estar vacío tras quitar espacios.",
        )

    # -------------------------------------------------------------------------
    # Regla: mass (g)
    # Si está presente, debe ser un número finito mayor o igual a cero.
    # (Puede ser nulo/NaN, no lo convierte a cero).
    # -------------------------------------------------------------------------
    raw_mass = fila.get("mass (g)")
    if not es_nulo_o_vacio(raw_mass):
        mass_str = raw_mass.strip()  # type: ignore[union-attr]
        try:
            mass_val = float(mass_str)
        except ValueError:
            reportar_error(
                num_fila,
                "mass (g)",
                f"Debe ser un número válido (recibido: '{mass_str}').",
            )

        if not math.isfinite(mass_val):
            reportar_error(
                num_fila,
                "mass (g)",
                f"El valor debe ser un número finito (recibido: '{mass_str}').",
            )

        if mass_val < 0:
            reportar_error(
                num_fila,
                "mass (g)",
                f"El valor debe ser mayor o igual a cero (recibido: {mass_val}).",
            )

    # -------------------------------------------------------------------------
    # Regla: fall
    # Únicamente se permiten los valores exactos "Fell" o "Found".
    # -------------------------------------------------------------------------
    raw_fall = fila.get("fall")
    if raw_fall not in VALORES_FALL_PERMITIDOS:
        reportar_error(
            num_fila,
            "fall",
            f"Valor no permitido: '{raw_fall}'. Únicamente se permiten los valores exactos 'Fell' o 'Found'.",
        )

    # -------------------------------------------------------------------------
    # Regla: year
    # Si está presente, extrae el año numérico. Debe ser un entero válido entre 1 y 2026.
    # -------------------------------------------------------------------------
    raw_year = fila.get("year")
    if not es_nulo_o_vacio(raw_year):
        anio = extraer_anio(raw_year)  # type: ignore[arg-type]
        if anio is None:
            reportar_error(
                num_fila,
                "year",
                f"No se pudo extraer un año numérico válido (recibido: '{raw_year}').",
            )
        if not (ANIO_MIN <= anio <= ANIO_MAX):
            reportar_error(
                num_fila,
                "year",
                f"El año debe estar entre {ANIO_MIN} y {ANIO_MAX} (extraído: {anio}).",
            )

    # -------------------------------------------------------------------------
    # Regla: reclat
    # Si está presente, debe ser un número finito entre -90 y 90.
    # -------------------------------------------------------------------------
    raw_lat = fila.get("reclat")
    if not es_nulo_o_vacio(raw_lat):
        lat_str = raw_lat.strip()  # type: ignore[union-attr]
        try:
            lat_val = float(lat_str)
        except ValueError:
            reportar_error(
                num_fila,
                "reclat",
                f"Debe ser un número válido (recibido: '{lat_str}').",
            )

        if not math.isfinite(lat_val):
            reportar_error(
                num_fila,
                "reclat",
                f"El valor debe ser un número finito (recibido: '{lat_str}').",
            )

        if not (LAT_MIN <= lat_val <= LAT_MAX):
            reportar_error(
                num_fila,
                "reclat",
                f"La latitud debe estar entre {LAT_MIN} y {LAT_MAX} (recibido: {lat_val}).",
            )

    # -------------------------------------------------------------------------
    # Regla: reclong
    # Si está presente, debe ser un número finito entre -180 y 180.
    # -------------------------------------------------------------------------
    raw_long = fila.get("reclong")
    if not es_nulo_o_vacio(raw_long):
        long_str = raw_long.strip()  # type: ignore[union-attr]
        try:
            long_val = float(long_str)
        except ValueError:
            reportar_error(
                num_fila,
                "reclong",
                f"Debe ser un número válido (recibido: '{long_str}').",
            )

        if not math.isfinite(long_val):
            reportar_error(
                num_fila,
                "reclong",
                f"El valor debe ser un número finito (recibido: '{long_str}').",
            )

        if not (LONG_MIN <= long_val <= LONG_MAX):
            reportar_error(
                num_fila,
                "reclong",
                f"La longitud debe estar entre {LONG_MIN} y {LONG_MAX} (recibido: {long_val}).",
            )


def resolver_ruta_archivo(ruta_personalizada: str | None = None) -> Path:
    """
    Determina la ruta del archivo CSV a validar.
    Si se proporciona un argumento, se utiliza dicha ruta.
    De lo contrario, busca 'datos/meteoritos.csv' en el directorio de trabajo actual
    o relativo a la raíz del proyecto.
    """
    if ruta_personalizada:
        return Path(ruta_personalizada)

    ruta_default = Path("datos/meteoritos.csv")
    if ruta_default.exists():
        return ruta_default

    # Intento relativo al directorio padre del script (raíz del proyecto)
    ruta_script = Path(__file__).resolve().parent.parent / "datos" / "meteoritos.csv"
    if ruta_script.exists():
        return ruta_script

    return ruta_default


def procesar_csv_stream(stream: io.TextIOBase) -> list[dict[str, str | None]]:
    """
    Lee y valida un flujo de texto CSV fila por fila.
    Retorna la lista de diccionarios de filas validadas si no hay errores.
    Si detecta una infracción, reporta el error y detiene el flujo con sys.exit(1).
    """
    lector_dict = csv.DictReader(stream)

    if lector_dict.fieldnames is None:
        reportar_error(1, "Estructura", "El archivo CSV está completamente vacío o no contiene encabezados.")

    validar_estructura(list(lector_dict.fieldnames))

    ids_vistos: set[int] = set()
    registros: list[dict[str, str | None]] = []

    for num_fila, fila in enumerate(lector_dict, start=2):
        validar_fila(fila, num_fila, ids_vistos)
        registros.append(fila)

    return registros


def validar_archivo(origen: Path | str | io.StringIO | io.TextIOBase) -> list[dict[str, str | None]]:
    """
    Valida un archivo CSV o un flujo en memoria (StringIO / TextIOBase).
    Retorna la lista de registros validados si todo es correcto.
    Si encuentra algún error, reporta el fallo y ejecuta sys.exit(1).
    """
    if isinstance(origen, (str, Path)):
        ruta = Path(origen)
        if not ruta.is_file():
            print(f"Error: No se encontró el archivo CSV en '{ruta}'.")
            sys.exit(1)

        # utf-8-sig maneja tanto UTF-8 estándar como UTF-8 con BOM
        with open(ruta, mode="r", encoding="utf-8-sig", newline="") as f:
            return procesar_csv_stream(f)
    elif hasattr(origen, "read"):
        return procesar_csv_stream(origen)
    else:
        raise TypeError(f"Tipo de origen no soportado: {type(origen)}")


# Alias para mayor claridad al validar fuentes de datos en memoria o disco
validar_datos = validar_archivo


def main() -> None:
    """
    Función principal de entrada del script para ejecución en CLI o pipeline de CI/CD.
    Permite recibir opcionalmente la ruta al CSV por argumento de consola.
    """
    ruta_arg = sys.argv[1] if len(sys.argv) > 1 else None
    ruta_csv = resolver_ruta_archivo(ruta_arg)
    registros = validar_archivo(ruta_csv)
    print(
        f"Validación exitosa: Todos los {len(registros)} registros en '{ruta_csv}' cumplen estrictamente las reglas."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
