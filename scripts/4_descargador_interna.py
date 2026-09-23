#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
 DESCARGADOR — Documentación INTERNA (Cero Papel SLEP Valparaíso)
 Resoluciones, Oficios, Memos, Cartas, Actas, etc. generados en el gestor.
----------------------------------------------------------------------------
 Lee datos/documentos_internos.csv (generado por 3_extractor_interna_consola.js),
 descarga cada documento por mes y genera:
   - salida_interna/AAAA-MM_mes/ ...pdf   (archivos con trazabilidad)
   - salida_interna/indice_maestro_interna.csv
   - salida_interna/resumen_conteo_interna.csv

 REGLA: 1 fila del CSV = 1 documento. Mes por Fecha de Publicación.

----------------------------------------------------------------------------
 COOKIE DE SESIÓN (necesaria para descargar):
   F12 -> pestaña Network -> filtra por el sitio, recarga, clic en una
   petición del sitio (ej. entradaAction.php o buscar_listadoYui.php) ->
   Request Headers -> copia lo que sigue a "Cookie:".
   Formato:  "PHPSESSID=elvalor"
----------------------------------------------------------------------------
 USO:
   & "$env:LOCALAPPDATA\\Programs\\PythonEmbed312\\python.exe" scripts\\4_descargador_interna.py
============================================================================
"""

import csv
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Falta 'requests'. Instálala con:  python -m pip install requests")
    sys.exit(1)

# ============================ CONFIGURACIÓN =================================

# Pega aquí tu cookie de sesión.
COOKIE = "PEGA_AQUI_TU_COOKIE"

LIMITE = 0               # 0 = baja TODOS. Un número > 0 limita para pruebas.
REINTENTOS = 3
ESPERA_ENTRE = 0.4
ESPERA_REINTENTO = 2.0
TIMEOUT = 60

RAIZ = Path(__file__).resolve().parent.parent
CSV_ENTRADA = RAIZ / "datos" / "documentos_internos.csv"
DIR_SALIDA = RAIZ / "salida_interna"
INDICE = DIR_SALIDA / "indice_maestro_interna.csv"
RESUMEN = DIR_SALIDA / "resumen_conteo_interna.csv"

BASE = "https://ceropapel.slepvalparaiso.gob.cl"

MESES = {
    "01": "enero", "02": "febrero", "03": "marzo", "04": "abril",
    "05": "mayo", "06": "junio", "07": "julio", "08": "agosto",
    "09": "septiembre", "10": "octubre", "11": "noviembre", "12": "diciembre",
}

# ============================ UTILIDADES ===================================

def limpiar_nombre(texto, max_len=60):
    if not texto:
        return ""
    reemplazos = (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
        ("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U"),
        ("ñ", "n"), ("Ñ", "N"), ("ü", "u"), ("Ü", "U"),
    )
    for a, b in reemplazos:
        texto = texto.replace(a, b)
    texto = re.sub(r"\s+", "_", texto)
    texto = re.sub(r"[^A-Za-z0-9_.\-]+", "_", texto)
    texto = re.sub(r"_+", "_", texto).strip("_")
    return texto[:max_len].strip("_")


def leer_csv(ruta):
    if not ruta.exists():
        print(f"No encuentro el CSV de entrada: {ruta}")
        print("Genera primero el CSV con 3_extractor_interna_consola.js y muévelo a datos/.")
        sys.exit(1)
    filas = []
    with open(ruta, "r", encoding="utf-8-sig", newline="") as f:
        muestra = f.read(2048)
        f.seek(0)
        sep = ";" if muestra.count(";") >= muestra.count(",") else ","
        for fila in csv.DictReader(f, delimiter=sep):
            filas.append(fila)
    return filas


def carpeta_mes(anio, mes):
    if anio and mes:
        nombre = f"{anio}-{mes}_{MESES.get(mes, 'mes')}"
    else:
        nombre = "sin_fecha"
    destino = DIR_SALIDA / nombre
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def nombre_archivo(fila, extension):
    # Ndoc__Tipo__Nexp__Autor.ext
    partes = [
        limpiar_nombre(fila.get("n_documento", ""), 20),
        limpiar_nombre(fila.get("tipo_documento", ""), 25),
        limpiar_nombre(fila.get("n_expediente", ""), 20),
        limpiar_nombre(fila.get("autor", ""), 35),
    ]
    base = "__".join(p for p in partes if p) or f"doc_{fila.get('doc_id','')}"
    return f"{base}.{extension}"


RE_PDF_EN_HTML = re.compile(
    r"""(?:src|href|data|file|url)\s*[=:]\s*['"]([^'"]+\.pdf[^'"]*)['"]""",
    re.IGNORECASE,
)


def resolver_url_pdf(sesion, url):
    r = sesion.get(url, timeout=TIMEOUT, allow_redirects=True)
    r.raise_for_status()
    ctype = r.headers.get("Content-Type", "").lower()

    if "application/pdf" in ctype or r.content[:5] == b"%PDF-":
        return r.content, "pdf"

    if "text/html" in ctype:
        html = r.text
        for c in RE_PDF_EN_HTML.findall(html):
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
        return r.content, "html"

    ext = "bin"
    if "image/" in ctype:
        ext = ctype.split("/")[-1].split(";")[0]
    elif "msword" in ctype:
        ext = "doc"
    elif "officedocument" in ctype:
        ext = "docx"
    return r.content, ext


def descargar_uno(sesion, fila):
    docid = fila.get("doc_id", "").strip()
    url = fila.get("url_descarga", "").strip() or (
        f"{BASE}/documentos/digital.php?doc_id={docid}" if docid else ""
    )
    resultado = {**fila, "archivo": "", "carpeta": "", "estado": "", "detalle": ""}

    if not url:
        resultado["estado"] = "SIN_URL"
        resultado["detalle"] = "La fila no tiene doc_id ni url_descarga."
        return resultado

    destino = carpeta_mes(fila.get("anio", ""), fila.get("mes", ""))
    ultimo_error = ""
    for intento in range(1, REINTENTOS + 1):
        try:
            contenido, ext = resolver_url_pdf(sesion, url)
            ruta = destino / nombre_archivo(fila, ext)
            if ruta.exists():
                ruta = destino / f"{ruta.stem}__id{docid}.{ext}"
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
    print(" DESCARGADOR — Documentación INTERNA Cero Papel SLEP Valparaíso")
    print("=" * 70)

    if COOKIE.strip() in ("", "PEGA_AQUI_TU_COOKIE"):
        print("\n[!] Falta configurar la COOKIE de sesión. Edita este archivo.\n")
        sys.exit(1)

    filas = leer_csv(CSV_ENTRADA)
    total = len(filas)
    if total == 0:
        print("El CSV no tiene filas. Nada que descargar.")
        sys.exit(1)

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
              f"[{res.get('tipo_documento','')}] ({res.get('mes_nombre','')}) "
              f"-> {res.get('archivo') or res['detalle']}")
        time.sleep(ESPERA_ENTRE)

    # ---- Índice maestro ----
    columnas = [
        "n_expediente", "expediente_titulo", "fecha_creacion", "n_documento",
        "tipo_documento", "nombre_documento", "autor", "destinatario",
        "fecha_publicacion", "materia", "doc_id", "url_descarga",
        "anio", "mes", "mes_nombre", "carpeta", "archivo", "estado", "detalle",
    ]
    with open(INDICE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in resultados:
            w.writerow(r)

    # ---- Resumen por mes ----
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
        w.writerow(["anio", "mes", "mes_nombre", "documentos", "descargados_ok", "fallidos"])
        tot_t = tot_ok = tot_err = 0
        for clave in sorted(porc_mes.keys()):
            anio, mes, nombre = clave
            d = porc_mes[clave]
            w.writerow([anio, mes, nombre, d["total"], d["ok"], d["error"]])
            tot_t += d["total"]; tot_ok += d["ok"]; tot_err += d["error"]
        w.writerow(["", "", "TOTAL", tot_t, tot_ok, tot_err])

    dur = time.time() - inicio
    print("\n" + "=" * 70)
    print(" RESUMEN (Documentación Interna)")
    print("=" * 70)
    print(f" Tiempo total: {dur/60:.1f} min")
    print(f" Estados: {conteo_estado}")
    print(f" Índice maestro:  {INDICE}")
    print(f" Resumen conteo:  {RESUMEN}")
    print(f" Carpetas por mes en: {DIR_SALIDA}")
    if conteo_estado.get("ERROR"):
        print(f"\n [!] Hubo {conteo_estado['ERROR']} fallidos. Revisa 'detalle' en el "
              f"índice maestro y vuelve a ejecutar para reintentarlos.")


if __name__ == "__main__":
    main()
