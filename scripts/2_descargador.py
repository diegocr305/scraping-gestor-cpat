#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
 DESCARGADOR DE DOCUMENTOS — Reporte "Documentos de entrada"
 Cero Papel — SLEP Valparaíso
----------------------------------------------------------------------------
 Lee el CSV generado por el extractor (datos/documentos_entrada.csv),
 descarga cada documento a una carpeta por mes, y genera:
   - salida/AAAA-MM_mes/ ...pdf         (los archivos, nombrados con trazabilidad)
   - salida/indice_maestro.csv           (una fila por documento, con estado)
   - salida/resumen_conteo.csv           (conteo de transacciones por mes)

 REGLA: 1 fila del CSV = 1 transacción (aunque tenga varios anexos).

----------------------------------------------------------------------------
 CÓMO OBTENER LA COOKIE DE SESIÓN (necesaria para descargar):
   1. En el navegador, ya logueado y con el reporte abierto, presiona F12.
   2. Ve a la pestaña "Application" (o "Almacenamiento") -> Cookies ->
      https://ceropapel.slepvalparaiso.gob.cl
   3. Copia el valor de la cookie de sesión (suele llamarse PHPSESSID).
   4. Pégala abajo en la variable COOKIE, formato:  "PHPSESSID=elvalor"
      (Si ves varias cookies relevantes, sepáralas con "; ")

   ALTERNATIVA rápida: en la consola (F12 -> Console) escribe:
       document.cookie
   copia lo que devuelve y pégalo tal cual en COOKIE.
----------------------------------------------------------------------------
 USO:
   python scripts\\2_descargador.py
============================================================================
"""

import csv
import os
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Falta la librería 'requests'. Instálala con:")
    print(r"   python -m pip install requests")
    sys.exit(1)

# ============================ CONFIGURACIÓN =================================

# Pega aquí tu cookie de sesión (ver instrucciones arriba).
COOKIE = "PEGA_AQUI_TU_COOKIE"


# Rutas (relativas a la raíz del proyecto)
RAIZ = Path(__file__).resolve().parent.parent
CSV_ENTRADA = RAIZ / "datos" / "documentos_entrada.csv"
DIR_SALIDA = RAIZ / "salida"
INDICE = DIR_SALIDA / "indice_maestro.csv"
RESUMEN = DIR_SALIDA / "resumen_conteo.csv"

# Comportamiento de descarga
LIMITE = 0               # 0 = baja TODOS. Un número > 0 limita para pruebas.
REINTENTOS = 3            # intentos por documento
ESPERA_ENTRE = 0.4        # segundos de pausa entre descargas (amable con el server)
ESPERA_REINTENTO = 2.0    # segundos antes de reintentar tras un fallo
TIMEOUT = 60              # timeout por request (segundos)

BASE = "https://ceropapel.slepvalparaiso.gob.cl"

MESES = {
    "01": "enero", "02": "febrero", "03": "marzo", "04": "abril",
    "05": "mayo", "06": "junio", "07": "julio", "08": "agosto",
    "09": "septiembre", "10": "octubre", "11": "noviembre", "12": "diciembre",
}

# ============================ UTILIDADES ===================================

def limpiar_nombre(texto, max_len=60):
    """Convierte un texto en un fragmento seguro para nombre de archivo."""
    if not texto:
        return ""
    # Quitar acentos comunes para máxima compatibilidad
    reemplazos = (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
        ("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U"),
        ("ñ", "n"), ("Ñ", "N"), ("ü", "u"), ("Ü", "U"),
    )
    for a, b in reemplazos:
        texto = texto.replace(a, b)
    # Normalizar espacios a "_"
    texto = re.sub(r"\s+", "_", texto)
    # Quedarse solo con caracteres seguros: letras/números ASCII, "_", "-", "."
    # Cualquier otro símbolo (°, º, ª, /, :, etc.) se convierte a "_"
    texto = re.sub(r"[^A-Za-z0-9_.\-]+", "_", texto)
    # Colapsar múltiples "_" y recortar
    texto = re.sub(r"_+", "_", texto).strip("_")
    return texto[:max_len].strip("_")


def leer_csv(ruta):
    """Lee el CSV del extractor (separado por ';', con BOM)."""
    if not ruta.exists():
        print(f"No encuentro el CSV de entrada: {ruta}")
        print("Genera primero el CSV con el extractor y muévelo a la carpeta datos/.")
        sys.exit(1)
    filas = []
    with open(ruta, "r", encoding="utf-8-sig", newline="") as f:
        # Detectar separador (el extractor usa ';', pero por si acaso)
        muestra = f.read(2048)
        f.seek(0)
        sep = ";" if muestra.count(";") >= muestra.count(",") else ","
        lector = csv.DictReader(f, delimiter=sep)
        for fila in lector:
            filas.append(fila)
    return filas


def carpeta_mes(anio, mes):
    """Devuelve (y crea) la carpeta salida/AAAA-MM_mesnombre/."""
    if anio and mes:
        nombre = f"{anio}-{mes}_{MESES.get(mes, 'mes')}"
    else:
        nombre = "sin_fecha"
    destino = DIR_SALIDA / nombre
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def nombre_archivo(fila, extension):
    """Construye el nombre trazable: Ndoc__Nexp__Tipo__Emisor.ext"""
    partes = [
        limpiar_nombre(fila.get("n_documento", ""), 20),
        limpiar_nombre(fila.get("n_expediente", ""), 20),
        limpiar_nombre(fila.get("tipo_documento", ""), 25),
        limpiar_nombre(fila.get("emisor", ""), 40),
    ]
    base = "__".join(p for p in partes if p) or f"doc_{fila.get('id_documento','')}"
    return f"{base}.{extension}"


# Detección de PDF real dentro de una respuesta HTML (por si documento.php
# devuelve una página de previsualización en lugar del PDF directo).
RE_PDF_EN_HTML = re.compile(
    r"""(?:src|href|data|file|url)\s*[=:]\s*['"]([^'"]+\.pdf[^'"]*)['"]""",
    re.IGNORECASE,
)


def resolver_url_pdf(sesion, url):
    """
    Pide la URL. Si devuelve PDF, retorna (contenido_bytes, 'pdf').
    Si devuelve HTML de previsualización, intenta encontrar el PDF real
    embebido y lo descarga. Retorna (bytes, ext) o lanza excepción.
    """
    r = sesion.get(url, timeout=TIMEOUT, allow_redirects=True)
    r.raise_for_status()
    ctype = r.headers.get("Content-Type", "").lower()

    # Caso 1: es un PDF directo
    if "application/pdf" in ctype or r.content[:5] == b"%PDF-":
        return r.content, "pdf"

    # Caso 2: es HTML -> buscar PDF embebido
    if "text/html" in ctype:
        html = r.text
        candidatos = RE_PDF_EN_HTML.findall(html)
        for c in candidatos:
            pdf_url = c
            if pdf_url.startswith("//"):
                pdf_url = "https:" + pdf_url
            elif pdf_url.startswith("/"):
                pdf_url = BASE + pdf_url
            elif not pdf_url.startswith("http"):
                pdf_url = BASE + "/documentos/" + pdf_url
            try:
                r2 = sesion.get(pdf_url, timeout=TIMEOUT, allow_redirects=True)
                r2.raise_for_status()
                if r2.content[:5] == b"%PDF-" or "application/pdf" in r2.headers.get("Content-Type", "").lower():
                    return r2.content, "pdf"
            except Exception:
                continue
        # No se encontró PDF embebido: guardamos el HTML como evidencia
        return r.content, "html"

    # Caso 3: otro tipo (imagen, doc, etc.) -> guardar con extensión genérica
    ext = "bin"
    if "image/" in ctype:
        ext = ctype.split("/")[-1].split(";")[0]
    elif "msword" in ctype:
        ext = "doc"
    elif "officedocument" in ctype:
        ext = "docx"
    return r.content, ext


def descargar_uno(sesion, fila):
    """Descarga un documento. Retorna dict con resultado para el índice."""
    idd = fila.get("id_documento", "").strip()
    url = fila.get("url_descarga", "").strip() or (
        f"{BASE}/documentos/documento.php?idDocumento={idd}" if idd else ""
    )
    resultado = {
        **fila,
        "archivo": "",
        "carpeta": "",
        "estado": "",
        "detalle": "",
    }

    if not url:
        resultado["estado"] = "SIN_URL"
        resultado["detalle"] = "La fila no tiene id_documento ni url_descarga."
        return resultado

    destino = carpeta_mes(fila.get("anio", ""), fila.get("mes", ""))

    ultimo_error = ""
    for intento in range(1, REINTENTOS + 1):
        try:
            contenido, ext = resolver_url_pdf(sesion, url)
            nombre = nombre_archivo(fila, ext)
            ruta = destino / nombre

            # Evitar sobrescribir si ya existe uno con el mismo nombre (distinto id)
            if ruta.exists():
                ruta = destino / f"{ruta.stem}__id{idd}.{ext}"

            with open(ruta, "wb") as fp:
                fp.write(contenido)

            resultado["archivo"] = ruta.name
            resultado["carpeta"] = destino.name
            resultado["estado"] = "OK" if ext == "pdf" else f"OK_{ext.upper()}"
            resultado["detalle"] = f"{len(contenido)} bytes"
            return resultado
        except Exception as e:
            ultimo_error = str(e)
            if intento < REINTENTOS:
                time.sleep(ESPERA_REINTENTO)

    resultado["estado"] = "ERROR"
    resultado["detalle"] = ultimo_error
    return resultado


# ============================ PRINCIPAL ====================================

def main():
    print("=" * 70)
    print(" DESCARGADOR — Documentos de entrada Cero Papel SLEP Valparaíso")
    print("=" * 70)

    if COOKIE.strip() in ("", "PEGA_AQUI_TU_COOKIE"):
        print("\n[!] Falta configurar la COOKIE de sesión.")
        print("    Edita este archivo y pega tu cookie en la variable COOKIE.")
        print("    Instrucciones detalladas al inicio del archivo.\n")
        sys.exit(1)

    filas = leer_csv(CSV_ENTRADA)
    total = len(filas)
    if total == 0:
        print("El CSV no tiene filas. Nada que descargar.")
        sys.exit(1)

    # Modo prueba: limitar la cantidad de descargas
    if LIMITE and LIMITE > 0:
        filas = filas[:LIMITE]
        print(f"\n[MODO PRUEBA] Solo se descargarán los primeros {len(filas)} de {total} documentos.")
        print("             Para bajar TODOS, pon LIMITE = 0 en la configuración.")
        total = len(filas)
    else:
        print(f"\nDocumentos a procesar: {total}")
    DIR_SALIDA.mkdir(parents=True, exist_ok=True)

    sesion = requests.Session()
    sesion.headers.update({
        "Cookie": COOKIE.strip(),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DescargadorCeroPapel/1.0",
        "Accept": "application/pdf,text/html,*/*",
    })

    resultados = []
    conteo_estado = {}
    inicio = time.time()

    for i, fila in enumerate(filas, 1):
        res = descargar_uno(sesion, fila)
        resultados.append(res)
        conteo_estado[res["estado"]] = conteo_estado.get(res["estado"], 0) + 1

        marca = "OK " if res["estado"].startswith("OK") else "ERR"
        print(f"[{i}/{total}] {marca} {res.get('n_documento','')} "
              f"({res.get('mes_nombre','')}) -> {res.get('archivo') or res['detalle']}")

        time.sleep(ESPERA_ENTRE)

    # ---- Índice maestro ----
    columnas = [
        "n_documento", "n_expediente", "tipo_documento", "emisor", "destinatarios",
        "fecha_publicacion", "fecha_recepcion", "expediente_codigo", "firmante",
        "institucion", "id_documento", "url_descarga", "anio", "mes", "mes_nombre",
        "carpeta", "archivo", "estado", "detalle",
    ]
    with open(INDICE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in resultados:
            w.writerow(r)

    # ---- Resumen de conteo por mes ----
    porc_mes = {}
    for r in resultados:
        clave = (r.get("anio", ""), r.get("mes", ""), r.get("mes_nombre", ""))
        d = porc_mes.setdefault(clave, {"total": 0, "ok": 0, "error": 0})
        d["total"] += 1
        if r["estado"].startswith("OK"):
            d["ok"] += 1
        else:
            d["error"] += 1

    with open(RESUMEN, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["anio", "mes", "mes_nombre", "documentos_transacciones",
                    "descargados_ok", "fallidos"])
        tot_t = tot_ok = tot_err = 0
        for clave in sorted(porc_mes.keys()):
            anio, mes, nombre = clave
            d = porc_mes[clave]
            w.writerow([anio, mes, nombre, d["total"], d["ok"], d["error"]])
            tot_t += d["total"]; tot_ok += d["ok"]; tot_err += d["error"]
        w.writerow(["", "", "TOTAL", tot_t, tot_ok, tot_err])

    # ---- Resumen en consola ----
    dur = time.time() - inicio
    print("\n" + "=" * 70)
    print(" RESUMEN")
    print("=" * 70)
    print(f" Tiempo total: {dur/60:.1f} min")
    print(f" Estados: {conteo_estado}")
    print(f" Índice maestro:  {INDICE}")
    print(f" Resumen conteo:  {RESUMEN}")
    print(f" Carpetas por mes en: {DIR_SALIDA}")
    if conteo_estado.get("ERROR"):
        print(f"\n [!] Hubo {conteo_estado['ERROR']} fallidos. Revisa la columna "
              f"'estado'/'detalle' del índice maestro. Puedes volver a ejecutar: "
              f"los ya descargados no se vuelven a bajar si mantienes los archivos.")


if __name__ == "__main__":
    main()
