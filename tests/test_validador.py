"""
Pruebas unitarias para el módulo de validación de datos (src/validador.py).

Verifica de forma aislada las reglas de negocio y de integridad de datos
utilizando conjuntos de datos pequeños en memoria (io.StringIO) y fixtures
temporales, garantizando la cobertura de los casos requeridos para el pipeline de CI/CD.
"""

import io
import sys
from pathlib import Path

import pytest

# Asegurar que la raíz del proyecto se encuentre en sys.path para pytest y CLI
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.validador import validar_archivo

# Encabezado estándar requerido por las reglas de estructura
HEADER = "id,name,recclass,mass (g),fall,year,reclat,reclong\n"


def test_procesamiento_registro_valido():
    """
    Prueba 1: Procesamiento de un registro válido.
    Verifica que un registro con todos los campos correctos (id único,
    masa > 0, fall 'Fell', año válido y coordenadas dentro de rango)
    se procese exitosamente sin generar excepciones ni errores.
    """
    csv_data = HEADER + "1,Aachen,L5,21.0,Fell,1880,50.775,6.08333\n"
    stream = io.StringIO(csv_data)

    registros = validar_archivo(stream)

    assert len(registros) == 1
    assert registros[0]["id"] == "1"
    assert registros[0]["name"] == "Aachen"
    assert registros[0]["recclass"] == "L5"
    assert registros[0]["mass (g)"] == "21.0"
    assert registros[0]["fall"] == "Fell"
    assert registros[0]["year"] == "1880"
    assert registros[0]["reclat"] == "50.775"
    assert registros[0]["reclong"] == "6.08333"


def test_calculo_indicador_resultado_conocido():
    """
    Prueba 2: Cálculo de un indicador con resultado conocido.
    Procesa 3 registros válidos simulados, extrae sus masas, calcula
    el promedio aritmético y verifica mediante assert que coincide exactamente
    con el valor esperado: (100.0 + 250.0 + 400.0) / 3 = 250.0.
    """
    csv_data = HEADER + (
        "10,Meteorito Alpha,H5,100.0,Fell,1920,12.34,56.78\n"
        "20,Meteorito Beta,L6,250.0,Found,1950,-23.45,-67.89\n"
        "30,Meteorito Gamma,CM2,400.0,Found,2001,45.0,90.0\n"
    )
    stream = io.StringIO(csv_data)

    registros = validar_archivo(stream)

    # Extraer las masas numéricas de los registros procesados
    masas = [float(reg["mass (g)"]) for reg in registros]
    promedio_calculado = sum(masas) / len(masas)
    promedio_esperado = 250.0

    assert len(masas) == 3
    assert promedio_calculado == pytest.approx(promedio_esperado)


def test_tratamiento_dato_faltante():
    """
    Prueba 3: Tratamiento correcto de un dato faltante.
    Verifica que un registro con 'mass (g)' y 'year' vacíos (nulos) pase la
    validación exitosamente, asegurando que no se rechaza y que no se reemplaza
    por cero (debe permanecer como valor ausente/vacío).
    """
    csv_data = HEADER + "100,Meteorito Sin Masa o Anio,Iron-IIIAB,,Found,,15.5,-30.2\n"
    stream = io.StringIO(csv_data)

    registros = validar_archivo(stream)

    assert len(registros) == 1
    registro = registros[0]

    # Verificar que el dato nulo no fue reemplazado por cero
    assert registro["mass (g)"] == ""
    assert registro["mass (g)"] != "0"
    assert registro["mass (g)"] != 0

    assert registro["year"] == ""
    assert registro["year"] != "0"
    assert registro["year"] != 0


def test_rechazo_masa_negativa():
    """
    Prueba 4: Rechazo de una masa negativa.
    Verifica que un registro con masa negativa (-15) sea interceptado
    inmediatamente por las reglas de validación, provocando un SystemExit con código 1.
    """
    csv_data = HEADER + "200,Meteorito Masa Negativa,L5,-15,Fell,1990,20.0,10.0\n"
    stream = io.StringIO(csv_data)

    with pytest.raises(SystemExit) as exc_info:
        validar_archivo(stream)

    assert exc_info.value.code == 1


def test_rechazo_coordenadas_fuera_de_rango():
    """
    Prueba 5: Rechazo de coordenadas fuera de rango.
    Verifica que los registros con latitud fuera de [-90, 90] (ej. 95)
    o longitud fuera de [-180, 180] (ej. -200) sean rechazados con SystemExit(1).
    """
    # Caso 5a: Latitud fuera de rango (95 > 90)
    csv_lat_invalida = HEADER + "301,Lat Invalida,H4,50.0,Fell,1985,95.0,10.0\n"
    with pytest.raises(SystemExit) as exc_info_lat:
        validar_archivo(io.StringIO(csv_lat_invalida))
    assert exc_info_lat.value.code == 1

    # Caso 5b: Longitud fuera de rango (-200 < -180)
    csv_long_invalida = HEADER + "302,Long Invalida,H4,50.0,Fell,1985,10.0,-200.0\n"
    with pytest.raises(SystemExit) as exc_info_long:
        validar_archivo(io.StringIO(csv_long_invalida))
    assert exc_info_long.value.code == 1


def test_rechazo_identificador_duplicado():
    """
    Prueba 6: Rechazo de un identificador duplicado.
    Verifica que un conjunto de datos donde dos registros comparten el mismo id
    sea interceptado por la validación de unicidad, provocando un SystemExit(1).
    """
    csv_data = HEADER + (
        "500,Primer Registro,L6,120.0,Fell,1940,30.0,40.0\n"
        "500,Segundo Registro Mismo ID,H5,80.0,Found,1960,-10.0,-20.0\n"
    )
    stream = io.StringIO(csv_data)

    with pytest.raises(SystemExit) as exc_info:
        validar_archivo(stream)

    assert exc_info.value.code == 1
