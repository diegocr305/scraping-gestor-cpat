#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
 LIMPIADOR de archivos .html basura (páginas de "sesión expirada")
----------------------------------------------------------------------------
 Cuando la cookie expira, los descargadores antiguos guardaban la página de
 "Su sesión ha expirado" como .html. Este script borra esos archivos inútiles
 de salida/ y salida_interna/ para dejar limpio antes de volver a descargar.

 USO:
   # Borra solo los .html que son páginas de sesión expirada (recomendado):
   & "$env:LOCALAPPDATA\\Programs\\PythonEmbed312\\python.exe" scripts\\5_limpiar_html_basura.py

   # Borra TODOS los .html (si estás seguro de que ninguno es un documento real):
   & "$env:LOCALAPPDATA\\Programs\\PythonEmbed312\\python.exe" scripts\\5_limpiar_html_basura.py --todos
============================================================================
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETAS = [RAIZ / "salida", RAIZ / "salida_interna"]

def es_html_basura(ruta_html):
    """
    True si el .html NO es un documento real, sino una página de mensaje/error
    del gestor (sesión expirada, documento no accesible, etc.).

    Se reconoce por el bloque 'msj-comprobante-modal' que el sistema usa para
    sus páginas de aviso, o por el texto de sesión expirada.
    """
    try:
        texto = ruta_html.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return False
    # Página de aviso/error del gestor (incluye sesión expirada y "documento
    # no accesible / anulado / restringido", que comparten esta plantilla).
    if "msj-comprobante-modal" in texto:
        return True
    if "su sesi" in texto and "expirad" in texto:
        return True
    return False


def main():
    borrar_todos = "--todos" in sys.argv

    total_html = 0
    borrados = 0
    conservados = 0

    for carpeta in CARPETAS:
        if not carpeta.exists():
            continue
        for html in carpeta.rglob("*.html"):
            total_html += 1
            if borrar_todos or es_html_basura(html):
                try:
                    html.unlink()
                    borrados += 1
                    print(f"  borrado: {html.relative_to(RAIZ)}")
                except Exception as e:
                    print(f"  [!] no pude borrar {html.name}: {e}")
            else:
                conservados += 1
                print(f"  CONSERVADO (no parece página de error): {html.relative_to(RAIZ)}")

    print("\n" + "=" * 60)
    print(f" .html encontrados: {total_html}")
    print(f" borrados:          {borrados}")
    print(f" conservados:       {conservados}")
    if conservados and not borrar_todos:
        print("\n Si los conservados tampoco sirven, ejecútalo con --todos.")
    print("=" * 60)


if __name__ == "__main__":
    main()
