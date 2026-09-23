/* ============================================================================
 *  EXTRACTOR DE TRAZABILIDAD — Reporte "Documentos de entrada"
 *  Cero Papel — SLEP Valparaíso
 * ----------------------------------------------------------------------------
 *  CÓMO USARLO:
 *   1. Genera el reporte en el navegador (fechas 1-may-2026 a 31-ago-2026)
 *      y espera a que se muestre la tabla con las páginas.
 *   2. Presiona F12 -> pestaña "Console".
 *   3. Copia TODO este archivo, pégalo en la consola y presiona Enter.
 *   4. Espera. El script recorre todas las páginas solo e informa el avance.
 *   5. Al terminar descarga "documentos_entrada.csv".
 *      Mueve ese archivo a la carpeta datos/ del proyecto.
 *
 *  QUÉ EXTRAE (por fila = 1 transacción):
 *   n_documento, n_expediente, tipo_documento, emisor, destinatarios,
 *   fecha_publicacion, fecha_recepcion, expediente_codigo, firmante,
 *   institucion, id_documento, url_descarga, anio, mes, mes_nombre
 * ==========================================================================*/

(async function () {
  "use strict";

  // --- Utilidades -----------------------------------------------------------
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const txt = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");

  const MESES = {
    "01": "enero", "02": "febrero", "03": "marzo", "04": "abril",
    "05": "mayo", "06": "junio", "07": "julio", "08": "agosto",
    "09": "septiembre", "10": "octubre", "11": "noviembre", "12": "diciembre",
  };

  // Convierte "dd-mm-yyyy" -> {anio, mes, mes_nombre}
  function desglosarFecha(fechaStr) {
    const m = (fechaStr || "").match(/(\d{2})-(\d{2})-(\d{4})/);
    if (!m) return { anio: "", mes: "", mes_nombre: "" };
    const [, dd, mm, yyyy] = m;
    return { anio: yyyy, mes: mm, mes_nombre: MESES[mm] || "" };
  }

  // Extrae el idDocumento de un href tipo documento.php?idDocumento=XXXX
  function extraerIdDocumento(tr) {
    const enlaces = tr.querySelectorAll("a[href*='documento.php']");
    for (const a of enlaces) {
      const m = a.getAttribute("href").match(/idDocumento=(\d+)/i);
      if (m) return m[1];
    }
    // Respaldo: buscar en cualquier atributo con idDocumento
    const m2 = tr.innerHTML.match(/idDocumento=(\d+)/i);
    return m2 ? m2[1] : "";
  }

  // --- Localizar la tabla del reporte --------------------------------------
  // Buscamos una tabla que tenga varias filas con enlace a documento.php
  function encontrarTabla() {
    const tablas = Array.from(document.querySelectorAll("table"));
    let mejor = null, mejorConteo = 0;
    for (const t of tablas) {
      const filas = t.querySelectorAll("tbody tr");
      let conLink = 0;
      filas.forEach((tr) => {
        if (tr.querySelector("a[href*='documento.php']")) conLink++;
      });
      if (conLink > mejorConteo) { mejorConteo = conLink; mejor = t; }
    }
    return mejor;
  }

  const tabla = encontrarTabla();
  if (!tabla) {
    alert("No encontré la tabla del reporte. Asegúrate de haber generado el reporte y ver las filas antes de ejecutar el script.");
    return;
  }
  console.log("%c[Extractor] Tabla localizada.", "color:#0a0");

  // --- Intentar mostrar el máximo de registros por página ------------------
  // DataTables suele tener un <select name='...length'>. Elegimos el mayor.
  try {
    const selLen = document.querySelector("select[name$='_length'], .dataTables_length select");
    if (selLen) {
      const opciones = Array.from(selLen.options).map((o) => parseInt(o.value, 10));
      const max = Math.max(...opciones.filter((n) => !isNaN(n) && n > 0));
      if (max && String(max) !== selLen.value) {
        selLen.value = String(max);
        selLen.dispatchEvent(new Event("change", { bubbles: true }));
        console.log(`[Extractor] Registros por página ajustado a ${max}.`);
        await sleep(1500);
      }
    }
  } catch (e) {
    console.warn("[Extractor] No pude ajustar registros por página (no crítico).", e);
  }

  // --- Extraer las filas de la página actual --------------------------------
  function extraerFilasActuales() {
    const filas = [];
    tabla.querySelectorAll("tbody tr").forEach((tr) => {
      const celdas = tr.querySelectorAll("td");
      if (celdas.length < 10) return; // fila no válida (ej. "No hay datos")

      const idDoc = extraerIdDocumento(tr);
      const fechaPub = txt(celdas[8]);   // col 9: fecha publicación
      const fechaRec = txt(celdas[9]);   // col 10: fecha recepción
      const { anio, mes, mes_nombre } = desglosarFecha(fechaPub);

      filas.push({
        n_documento: txt(celdas[0]),
        n_expediente: txt(celdas[1]),
        tipo_documento: txt(celdas[2]),
        emisor: txt(celdas[6]),
        destinatarios: txt(celdas[7]),
        fecha_publicacion: fechaPub,
        fecha_recepcion: fechaRec,
        expediente_codigo: txt(celdas[10]),
        firmante: txt(celdas[11]),
        institucion: txt(celdas[12]),
        id_documento: idDoc,
        url_descarga: idDoc
          ? `https://ceropapel.slepvalparaiso.gob.cl/documentos/documento.php?idDocumento=${idDoc}`
          : "",
        anio, mes, mes_nombre,
      });
    });
    return filas;
  }

  // --- Encontrar el botón "Siguiente" y saber si está deshabilitado ---------
  function botonSiguiente() {
    // DataTables: <a class="paginate_button next" ...> o li.next
    let btn =
      document.querySelector(".paginate_button.next:not(.disabled)") ||
      document.querySelector("li.next:not(.disabled) a") ||
      document.querySelector("a.next:not(.disabled)");
    if (btn) return btn;

    // Respaldo por texto "Siguiente"
    const candidatos = Array.from(document.querySelectorAll("a, button"));
    return candidatos.find((el) => {
      const t = el.textContent.trim().toLowerCase();
      const clases = el.className.toLowerCase();
      const desactivado = clases.includes("disabled") ||
        el.getAttribute("aria-disabled") === "true";
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
    if (!cont) return true; // sin paginación => una sola página
    const clases = (cont.className || "").toLowerCase();
    return clases.includes("disabled") || cont.getAttribute("aria-disabled") === "true";
  }

  // Firma de la página actual para detectar cuándo terminó de cambiar
  function firmaPagina() {
    const primera = tabla.querySelector("tbody tr td");
    const info = document.querySelector(".dataTables_info");
    return (info ? txt(info) : "") + "|" + (primera ? txt(primera) : "");
  }

  // --- Recorrido de todas las páginas --------------------------------------
  const acumulado = [];
  const vistos = new Set(); // evita duplicados por id_documento
  let pagina = 1;
  const MAX_PAGINAS = 2000; // salvaguarda anti-bucle

  console.log("%c[Extractor] Iniciando recorrido de páginas...", "color:#06c;font-weight:bold");

  while (pagina <= MAX_PAGINAS) {
    const filas = extraerFilasActuales();
    let nuevas = 0;
    for (const f of filas) {
      const clave = f.id_documento || `${f.n_documento}|${f.fecha_publicacion}`;
      if (!vistos.has(clave)) {
        vistos.add(clave);
        acumulado.push(f);
        nuevas++;
      }
    }
    console.log(`[Extractor] Página ${pagina}: ${filas.length} filas (${nuevas} nuevas). Total acumulado: ${acumulado.length}`);

    if (siguienteEstaDeshabilitado()) {
      console.log("%c[Extractor] Llegué a la última página.", "color:#0a0;font-weight:bold");
      break;
    }

    const btn = botonSiguiente();
    if (!btn) {
      console.warn("[Extractor] No encontré el botón Siguiente activo. Deteniendo.");
      break;
    }

    const antes = firmaPagina();
    btn.click();

    // Esperar a que la tabla cambie (hasta ~15s)
    let cambiou = false;
    for (let i = 0; i < 60; i++) {
      await sleep(250);
      if (firmaPagina() !== antes) { cambiou = true; break; }
    }
    if (!cambiou) {
      console.warn("[Extractor] La página no cambió tras hacer clic en Siguiente. Deteniendo por seguridad.");
      break;
    }
    await sleep(200); // pequeño respiro para el render
    pagina++;
  }

  // --- Generar CSV ----------------------------------------------------------
  const columnas = [
    "n_documento", "n_expediente", "tipo_documento", "emisor", "destinatarios",
    "fecha_publicacion", "fecha_recepcion", "expediente_codigo", "firmante",
    "institucion", "id_documento", "url_descarga", "anio", "mes", "mes_nombre",
  ];

  function celdaCSV(v) {
    const s = (v == null ? "" : String(v));
    // Escapar comillas y envolver siempre entre comillas (seguro para Excel)
    return '"' + s.replace(/"/g, '""') + '"';
  }

  const encabezado = columnas.join(";"); // ; para que Excel en español lo abra en columnas
  const lineas = acumulado.map((row) =>
    columnas.map((c) => celdaCSV(row[c])).join(";")
  );
  const csv = "\uFEFF" + encabezado + "\r\n" + lineas.join("\r\n"); // BOM para tildes en Excel

  // --- Descargar el archivo -------------------------------------------------
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "documentos_entrada.csv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  // --- Resumen rápido por mes en la consola ---------------------------------
  const porMes = {};
  acumulado.forEach((r) => {
    const k = r.anio && r.mes ? `${r.anio}-${r.mes} (${r.mes_nombre})` : "sin_fecha";
    porMes[k] = (porMes[k] || 0) + 1;
  });

  console.log("%c===== EXTRACCIÓN COMPLETADA =====", "color:#0a0;font-weight:bold;font-size:14px");
  console.log(`Total de documentos (transacciones): ${acumulado.length}`);
  console.table(porMes);
  console.log("Archivo descargado: documentos_entrada.csv");
  console.log("Muévelo a la carpeta datos/ del proyecto y continúa con el descargador.");

  // También lo dejamos accesible por si quieres inspeccionarlo
  window.__documentosEntrada = acumulado;
})();
