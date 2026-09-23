# Scraping Gestor Documental — Cero Papel SLEP Valparaíso

Herramientas para extraer y descargar de forma masiva los documentos del gestor
documental **Cero Papel** (SLEP Valparaíso), agruparlos **por mes** y generar un
**conteo con trazabilidad** que sirve como medio de verificación.

Cubre dos reportes:

| Reporte | Qué contiene | Scripts |
|---------|--------------|---------|
| **Documentos de entrada** | Documentación externa que llega a Oficina de Partes | `1_extractor_consola.js` + `2_descargador.py` |
| **Documentación interna** | Documentos generados en el gestor (Resoluciones, Oficios, Memos, Cartas, Actas…) | `3_extractor_interna_consola.js` + `4_descargador_interna.py` |

## Cómo funciona (enfoque)

La autenticación del gestor usa **Clave Única**, que no permite login automatizado.
Por eso el trabajo se divide en dos fases y **nunca se automatiza el login**:

1. **Extracción (navegador):** tú inicias sesión y generas el reporte. Un script de
   consola (JavaScript, se pega en F12) recorre todas las páginas de la tabla y
   exporta un **CSV** con la trazabilidad de cada documento (N°, fechas, tipo,
   emisor/autor, y la URL de descarga con su ID).
2. **Descarga (Python):** un script lee ese CSV y descarga cada documento a una
   carpeta por mes, reutilizando la **cookie de sesión** del navegador. Genera un
   índice maestro y un resumen de conteo.

## Regla de conteo

- **1 fila del reporte = 1 transacción**, aunque el documento tenga varios anexos o
  destinatarios.
- El **mes** se determina por la **Fecha de Publicación**.

## Seguridad (importante)

- **Ningún script guarda ni usa tu Clave Única.** La autenticación la haces tú en el
  navegador.
- La **cookie de sesión** que se pega en los descargadores es temporal. No la subas
  a ningún repositorio y **cierra sesión en Cero Papel al terminar** para invalidarla.
- El `.gitignore` excluye los CSV con datos reales y las carpetas de descarga, para
  que **no se suban documentos institucionales** al repositorio.

## Requisitos

- **Python 3.12** con la librería `requests` (`python -m pip install requests`).
  > En este equipo, el instalador oficial de Python está bloqueado por política de
  > la organización; se usa una build embebida portable en
  > `%LOCALAPPDATA%\Programs\PythonEmbed312` que funciona igual.
- **Navegador** con sesión iniciada en Cero Papel.
- (Opcional) **Node.js** para utilidades futuras.

---

## Reporte 1 — Documentos de entrada

### Paso 1 — Generar el reporte
1. Inicia sesión en Cero Papel con tu Clave Única.
2. Cambia al perfil **Funcionario / Oficina de Partes**.
3. Entra al reporte de entrada:
   `…/oficialDePartes/reportes/entrada.php`
4. Elige el rango de fechas (ej. `1-may-2026` a `31-ago-2026`) → **Generar Reporte**.

### Paso 2 — Extraer la trazabilidad (CSV)
1. Con el reporte a la vista: **F12 → Console**.
2. Copia TODO `scripts/1_extractor_consola.js`, pégalo en la consola y Enter.
3. Recorre todas las páginas y descarga `documentos_entrada.csv`.
4. Mueve ese archivo a la carpeta `datos/`.

### Paso 3 — Descargar los PDFs por mes
1. Consigue la **cookie de sesión** (ver "Cómo obtener la cookie" más abajo) y pégala
   en la variable `COOKIE` de `scripts/2_descargador.py`.
2. Ejecuta:
   ```powershell
   & "$env:LOCALAPPDATA\Programs\PythonEmbed312\python.exe" scripts\2_descargador.py
   ```
   > Tip: `LIMITE = 3` en el script baja solo 3 documentos (para probar). Ponlo en
   > `0` para bajar todos.
3. Resultado en `salida/`: carpetas por mes + `indice_maestro.csv` + `resumen_conteo.csv`.

Nombre de archivo: `Ndoc__Nexpediente__Tipo__Emisor.pdf`

---

## Reporte 2 — Documentación interna

Mismo enfoque, adaptado a este reporte:

- El enlace de descarga es `documentos/digital.php?doc_id=XXXX`.
- El **tipo de documento** (Resolución Exenta, Oficio, Memo…) se extrae de la columna
  "Documento" y se incluye en el nombre del archivo y en el índice.
- La salida va a `salida_interna/` para no mezclar con el reporte de entrada.

### Pasos
1. Abre el listado de documentos internos con el rango de fechas deseado.
2. **F12 → Console**, pega TODO `scripts/3_extractor_interna_consola.js` y Enter.
   Descarga `documentos_internos.csv`; muévelo a `datos/`.
   > En la consola verás un desglose por mes y **por tipo de documento**.
3. Pega la cookie en `scripts/4_descargador_interna.py` y ejecuta:
   ```powershell
   & "$env:LOCALAPPDATA\Programs\PythonEmbed312\python.exe" scripts\4_descargador_interna.py
   ```
4. Resultado en `salida_interna/`: carpetas por mes +
   `indice_maestro_interna.csv` + `resumen_conteo_interna.csv`.

Nombre de archivo: `Ndoc__Tipo__Nexpediente__Autor.pdf`

---

## Cómo obtener la cookie de sesión

1. En el navegador ya logueado: **F12 → pestaña Network**.
2. En el filtro escribe una página del sitio (ej. `entradaAction.php` o
   `buscar_listadoYui.php`) y **recarga** (F5).
3. Haz clic en una petición **del sitio** (no de extensiones `chrome-extension://`).
4. En **Request Headers** copia lo que sigue a `Cookie:` (algo como
   `PHPSESSID=xxxxxxxx`).
5. Pégalo en la variable `COOKIE` del descargador correspondiente.

> La cookie es HttpOnly, por eso `document.cookie` en la consola devuelve vacío;
> hay que sacarla desde Network como se indica arriba.

## Estructura del proyecto

```
scraping-gestor-cpat/
├─ README.md
├─ .gitignore
├─ scripts/
│  ├─ 1_extractor_consola.js         # Entrada: extractor (consola F12)
│  ├─ 2_descargador.py               # Entrada: descargador (Python)
│  ├─ 3_extractor_interna_consola.js # Interna: extractor (consola F12)
│  └─ 4_descargador_interna.py       # Interna: descargador (Python)
├─ datos/                             # CSVs exportados (ignorados por git)
├─ salida/                            # Descargas reporte de entrada (ignorado)
└─ salida_interna/                    # Descargas reporte interno (ignorado)
```

## Solución de problemas

- **`python` no se reconoce:** usa la ruta completa
  `& "$env:LOCALAPPDATA\Programs\PythonEmbed312\python.exe" ...` o desactiva el alias
  del Microsoft Store en *Configuración → Aplicaciones → Alias de ejecución*.
- **Descargas con estado `ERROR`:** suele ser cookie expirada. Saca una cookie fresca
  y vuelve a ejecutar; los ya descargados no se vuelven a bajar.
- **Archivos que salen como `.html`:** significa que la previsualización no expuso el
  PDF directo; revisa la fila en el índice maestro (columna `detalle`).
