/* ============================================================================
 *  EXTRACTOR DE TRAZABILIDAD — Documentación INTERNA
 *  (Resoluciones, Oficios, Memos, Cartas, Actas, etc. generados en el gestor)
 *  Cero Papel — SLEP Valparaíso
 * ----------------------------------------------------------------------------
 *  CÓMO USARLO:
 *   1. Genera/abre el listado de documentos internos (el de las 193 páginas)
 *      con el rango de fechas deseado y espera a que se muestre la tabla.
 *   2. Presiona F12 -> pestaña "Console".
 *   3. Copia TODO este archivo, pégalo en la consola y presiona Enter.
 *   4. Espera. Recorre todas las páginas solo e informa el avance.
 *   5. Al terminar descarga "documentos_internos.csv".
 *      Muévelo a la carpeta datos/ del proyecto.
 *
 *  QUÉ EXTRAE (por fila = 1 documento):
 *   n_expediente, expediente_titulo, fecha_creacion, n_documento,
 *   tipo_documento, nombre_documento, autor, destinatario,
 *   fecha_publicacion, materia, doc_id, url_descarga, anio, mes, mes_nombre
 * ==========================================================================*/

(async function () {
  "use strict";

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const txt = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");

  const MESES = {
    "01": "enero", "02": "febrero", "03": "marzo", "04": "abril",
    "05": "mayo", "06": "junio", "07": "julio", "08": "agosto",
    "09": "septiembre", "10": "octubre", "11": "noviembre", "12": "diciembre",
  };

  function desglosarFecha(fechaStr) {
    const m = (fechaStr || "").match(/(\d{2})-(\d{2})-(\d{4})/);
    if (!m) return { anio: "", mes: "", mes_nombre: "" };
    const [, dd, mm, yyyy] = m;
    return { anio: yyyy, mes: mm, mes_nombre: MESES[mm] || "" };
  }

  // El link de descarga aquí es digital.php?doc_id=XXXX
  function extraerDocId(tr) {
    const enlaces = tr.querySelectorAll("a[href*='digital.php']");
    for (const a of enlaces) {
      const m = a.getAttribute("href").match(/doc_id=(\d+)/i);
      if (m) return m[1];
    }
    const m2 = tr.innerHTML.match(/digital\.php\?doc_id=(\d+)/i);
    return m2 ? m2[1] : "";
  }

  // De la celda "Documento" separamos: tipo (antes del span/nombre) y nombre.
  // Ej HTML: <a ...>Resolución Exenta<span id="nombre_documento_..">:NOMBRE</span></a>
  function extraerTipoYNombre(celdaDoc) {
    const link = celdaDoc.querySelector("a[href*='digital.php']") || celdaDoc.querySelector("a");
    if (!link) return { tipo: txt(celdaDoc), nombre: "" };

    // El nombre suele venir en un span con id que empieza por "nombre_documento_"
    const spanNombre = link.querySelector("span[id^='nombre_documento_']");
    let nombre = spanNombre ? txt(spanNombre) : "";
    // El nombre a veces empieza con ":" -> lo limpiamos
    nombre = nombre.replace(/^\s*:\s*/, "");

    // El tipo es el texto del link SIN el texto del span del nombre
    let tipo = txt(link);
    if (nombre && tipo.includes(nombre)) {
      tipo = tipo.replace(nombre, "");
    }
    // Quitar el ":" y espacios sobrantes que quedaban antes del nombre
    tipo = tipo.replace(/:\s*$/, "").replace(/\s+/g, " ").trim();

    return { tipo, nombre };
  }

  // --- Localizar la tabla: filas con enlace a digital.php --------------------
  function encontrarTabla() {
    const tablas = Array.from(document.querySelectorAll("table"));
    let mejor = null, mejorConteo = 0;
    for (const t of tablas) {
      let conLink = 0;
      t.querySelectorAll("tbody tr").forEach((tr) => {
        if (tr.querySelector("a[href*='digital.php']")) conLink++;
      });
      if (conLink > mejorConteo) { mejorConteo = conLink; mejor = t; }
    }
    return mejor;
  }

  const tabla = encontrarTabla();
  if (!tabla) {
    alert("No encontré la tabla de documentos internos. Genera el listado y espera a ver las filas antes de ejecutar el script.");
    return;
  }
  console.log("%c[Extractor Interna] Tabla localizada.", "color:#0a0");

  // --- Máximo de registros por página --------------------------------------
  try {
    const selLen = document.querySelector("select[name$='_length'], .dataTables_length select");
    if (selLen) {
      const opciones = Array.from(selLen.options).map((o) => parseInt(o.value, 10));
      const max = Math.max(...opciones.filter((n) => !isNaN(n) && n > 0));
      if (max && String(max) !== selLen.value) {
        selLen.value = String(max);
        selLen.dispatchEvent(new Event("change", { bubbles: true }));
        console.log(`[Extractor Interna] Registros por página ajustado a ${max}.`);
        await sleep(1500);
      }
    }
  } catch (e) {
    console.warn("[Extractor Interna] No pude ajustar registros por página (no crítico).", e);
  }

  // --- Extraer filas de la página actual ------------------------------------
  function extraerFilasActuales() {
    const filas = [];
    tabla.querySelectorAll("tbody tr").forEach((tr) => {
      const celdas = tr.querySelectorAll("td");
      if (celdas.length < 9) return; // fila no válida

      const docId = extraerDocId(tr);
      if (!docId) return; // fila sin documento descargable (fila de control, etc.)

      const { tipo, nombre } = extraerTipoYNombre(celdas[4]);
      const fechaPub = txt(celdas[7]);   // col 8 (índice 7): fecha publicación
      const { anio, mes, mes_nombre } = desglosarFecha(fechaPub);

      filas.push({
        n_expediente: txt(celdas[0]),
        expediente_titulo: txt(celdas[1]),
        fecha_creacion: txt(celdas[2]),
        n_documento: txt(celdas[3]),
        tipo_documento: tipo,
        nombre_documento: nombre,
        autor: txt(celdas[5]),
        destinatario: txt(celdas[6]),
        fecha_publicacion: fechaPub,
        materia: txt(celdas[8]),
        doc_id: docId,
        url_descarga: `https://ceropapel.slepvalparaiso.gob.cl/documentos/digital.php?doc_id=${docId}`,
        anio, mes, mes_nombre,
      });
    });
    return filas;
  }

  // --- Paginación (igual que el primer extractor) ---------------------------
  function botonSiguiente() {
    let btn =
      document.querySelector(".paginate_button.next:not(.disabled)") ||
      document.querySelector("li.next:not(.disabled) a") ||
      document.querySelector("a.next:not(.disabled)");
    if (btn) return btn;
    const candidatos = Array.from(document.querySelectorAll("a, button"));
    return candidatos.find((el) => {
      const t = el.textContent.trim().toLowerCase();
      const clases = el.className.toLowerCase();
      const desactivado = clases.includes("disabled") || el.getAttribute("aria-disabled") === "true";
      return (t === "siguiente" || t === "next") && !desactivado;
    }) || null;
  }

  function siguienteEstaDeshabilitado() {
    const cont =
      document.querySelector(".paginate_button.next") ||
      document.querySelector("li.next") ||
      Array.from(document.querySelectorAll("a, button")).find((el) => {
        const t = el.textContent.trim().toLowerCase();
        return t === "siguiente" || t === "next";
      });
    if (!cont) return true;
    const clases = (cont.className || "").toLowerCase();
    return clases.includes("disabled") || cont.getAttribute("aria-disabled") === "true";
  }

  function firmaPagina() {
    const primera = tabla.querySelector("tbody tr td");
    const info = document.querySelector(".dataTables_info");
    return (info ? txt(info) : "") + "|" + (primera ? txt(primera) : "");
  }

  // --- Recorrido ------------------------------------------------------------
  const acumulado = [];
  const vistos = new Set();
  let pagina = 1;
  const MAX_PAGINAS = 3000;

  console.log("%c[Extractor Interna] Iniciando recorrido...", "color:#06c;font-weight:bold");

  while (pagina <= MAX_PAGINAS) {
    const filas = extraerFilasActuales();
    let nuevas = 0;
    for (const f of filas) {
      const clave = f.doc_id || `${f.n_documento}|${f.fecha_publicacion}`;
      if (!vistos.has(clave)) { vistos.add(clave); acumulado.push(f); nuevas++; }
    }
    console.log(`[Extractor Interna] Página ${pagina}: ${filas.length} filas (${nuevas} nuevas). Total: ${acumulado.length}`);

    if (siguienteEstaDeshabilitado()) {
      console.log("%c[Extractor Interna] Última página alcanzada.", "color:#0a0;font-weight:bold");
      break;
    }
    const btn = botonSiguiente();
    if (!btn) { console.warn("[Extractor Interna] No encontré Siguiente activo. Deteniendo."); break; }

    const antes = firmaPagina();
    btn.click();
    let cambiou = false;
    for (let i = 0; i < 60; i++) {
      await sleep(250);
      if (firmaPagina() !== antes) { cambiou = true; break; }
    }
    if (!cambiou) { console.warn("[Extractor Interna] La página no cambió. Deteniendo."); break; }
    await sleep(200);
    pagina++;
  }

  // --- CSV ------------------------------------------------------------------
  const columnas = [
    "n_expediente", "expediente_titulo", "fecha_creacion", "n_documento",
    "tipo_documento", "nombre_documento", "autor", "destinatario",
    "fecha_publicacion", "materia", "doc_id", "url_descarga",
    "anio", "mes", "mes_nombre",
  ];
  const celdaCSV = (v) => '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"';
  const encabezado = columnas.join(";");
  const lineas = acumulado.map((row) => columnas.map((c) => celdaCSV(row[c])).join(";"));
  const csv = "\uFEFF" + encabezado + "\r\n" + lineas.join("\r\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "documentos_internos.csv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  // --- Resumen en consola ---------------------------------------------------
  const porMes = {};
  const porTipo = {};
  acumulado.forEach((r) => {
    const k = r.anio && r.mes ? `${r.anio}-${r.mes} (${r.mes_nombre})` : "sin_fecha";
    porMes[k] = (porMes[k] || 0) + 1;
    const t = r.tipo_documento || "sin_tipo";
    porTipo[t] = (porTipo[t] || 0) + 1;
  });

  console.log("%c===== EXTRACCIÓN INTERNA COMPLETADA =====", "color:#0a0;font-weight:bold;font-size:14px");
  console.log(`Total de documentos: ${acumulado.length}`);
  console.log("Por mes:"); console.table(porMes);
  console.log("Por tipo de documento:"); console.table(porTipo);
  console.log("Archivo descargado: documentos_internos.csv -> muévelo a datos/");

  window.__documentosInternos = acumulado;
})();
