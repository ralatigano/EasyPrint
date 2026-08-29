document.addEventListener("DOMContentLoaded", function () {
  const tablaPresupuesto = document.getElementById("NuevoPresupuesto");
  if (tablaPresupuesto) {
    $("#NuevoPresupuesto").DataTable({
      responsive: true,
      paging: false,
      searching: false,
      info: false,
      ordering: false,
      language: {
        emptyTable: "No hay productos cotizados",
      },
      columnDefs: [
        { responsivePriority: 1, targets: 6 }, // Total → siempre visible
        { responsivePriority: 2, targets: 0 }, // Servicio
        { responsivePriority: 3, targets: -1 }, // Editar/Borrar
        { responsivePriority: 4, targets: 3 }, // Precio
        { responsivePriority: 5, targets: 4 }, // Descuento [%]
        { responsivePriority: 6, targets: 5 }, // Descuento [$]
        { responsivePriority: 7, targets: 1 }, // Empaquetado
        { responsivePriority: 8, targets: 2 }, // Cantidad
      ]
    });
  }
});

// Regex para detectar productos con rango de cantidad en el nombre: "Nombre [1-5]", "Nombre [6-INF]"
const RANGO_RE = /^(.*?)\s*\[(\d+)[-](\d+|INF)\]\s*$/;

// Producto resuelto tras el packing (puede diferir del seleccionado en el dropdown)
let resolvedProductoId = null;
let resolvedProductoNombre = null;

// Contexto de tiempos de producción (Fase 2). Lo alimenta precargarTiempoEstimado
// y lo consumen el override manual (checkbox "Ajustar tiempos") y el save-back.
let tiemposCtx = {
  productoId: null,
  tipo: "D",
  q: 0,             // cantidad_producto convergida (0 si aún no se conoce)
  qConocida: false, // en A/B/C, si ya hay dibujo
  setup: 0,
  unitario: 0,
  factor: 1,
  tieneTiempos: false,
  override: false,  // checkbox "Ajustar tiempos" activo
};

document.addEventListener("DOMContentLoaded", () => {
    aplicarDefaultTipoCalculo();
    inicializarSelect2();
    cargarCategoriasDesdeBackend();
});

/**
 * Inicializa Select2 sobre los selects de categoría y producto para tener
 * búsqueda dentro del input. Es defensivo: si Select2/jQuery no cargaron, los
 * selects siguen funcionando como <select> normales.
 *
 * OJO con el encadenado: Select2 dispara el evento `change` vía jQuery, que NO
 * alcanza a los listeners `addEventListener` nativos. Por eso los handlers de
 * categoría/producto se registran con `$(...).on('change', ...)` (ver más abajo),
 * y al repoblar opciones se refresca la UI con `.trigger('change.select2')`
 * (namespaced, para NO re-disparar la lógica de esos handlers).
 */
function inicializarSelect2() {
    if (!window.jQuery || !$.fn.select2) return;
    $('#selectCategoria').select2({
        width: '100%',
        placeholder: 'Seleccione una categoría',
        language: { noResults: () => 'Sin resultados' },
    });
    $('#selectProducto').select2({
        width: '100%',
        placeholder: 'Seleccione un producto',
        language: { noResults: () => 'Sin resultados' },
    });
}

/**
 * Guarda en localStorage el valor como "tipoCalculoDefault" para que
 * el tipo de cálculo predeterminado se conserve entre sesiones.
 * @param {string} valorSeleccionado - Valor que se va a guardar como predeterminado.
 */
function guardarDefault(valorSeleccionado) {
  // Guardar en localStorage
  localStorage.setItem("tipoCalculoDefault", valorSeleccionado);

  // Desmarcar todos los checkboxes excepto el actual
  const checkboxes = document.querySelectorAll('[id^="defaultTipo"]');
  checkboxes.forEach(checkbox => {
    checkbox.checked = checkbox.id === `defaultTipo${valorSeleccionado}`;
  });
}

/**
 * Sets the default calculation type based on the value stored in localStorage.
 * 
 * This function retrieves the default calculation type from localStorage.
 * If no value is stored, it defaults to "A" and updates localStorage accordingly.
 * It then selects the radio button and checkbox corresponding to this default
 * value and updates the visibility of related elements on the page.
 */
function aplicarDefaultTipoCalculo() {
  let valorDefault = localStorage.getItem("tipoCalculoDefault");

  // Si no hay valor guardado, usar "A" como default
  if (!valorDefault) {
    valorDefault = "A";
    localStorage.setItem("tipoCalculoDefault", valorDefault);
  }

  const radio = document.querySelector(`input[name="tipoProducto"][value="${valorDefault}"]`);
  if (radio) {
    radio.checked = true;
  }

  // Marcar el checkbox correspondiente
  const checkbox = document.getElementById(`defaultTipo${valorDefault}`);
  if (checkbox) {
    checkbox.checked = true;
  }

  actualizarVisibilidadPorTipo();
}



/**
 * Updates the visibility of elements on the page based on the selected product type.
 *
 * This function checks if the "tipoD" radio button is selected to determine the product type.
 * If "tipoD" is selected, certain input fields and the graphical section are hidden. Otherwise,
 * these elements are displayed. Additionally, the function updates the state of the graphical
 * button based on the chosen product type.
 */

function actualizarVisibilidadPorTipo() {
  resetearSiHayGrafico();
  const tipoDSeleccionado = document.getElementById("tipoD").checked;
  const tipo = tipoDSeleccionado ? "D" : "ABC";

  const bloqueDimensiones = document.getElementById("bloqueDimensiones");
  const seccionGrafico = document.getElementById("seccionGrafico");

  // Mostrar/ocultar inputs
  bloqueDimensiones.querySelectorAll("#inputAnchoHoja, #inputAltoHoja, #inputAnchoElemento, #inputAltoElemento, #separacionElementos")
    .forEach(input => {
      const contenedor = input.closest(".col-md-4") || input.closest(".col-12.col-md-4");
      if (contenedor) {
        contenedor.style.display = tipoDSeleccionado ? "none" : "block";
      }
    });

  // Mostrar/ocultar gráfico (pero no el botón)
  seccionGrafico.style.display = tipoDSeleccionado ? "none" : "block";

  // Actualizar botón según tipo
  actualizarBotonGrafico(tipo);
}


/**
 * Actualiza el botón de generación de gráfico según el tipo de producto
 * seleccionado.
 *
 * Si el tipo de producto es "D", el botón muestra el texto "Calcular"
 * y al hacer clic se muestra un modal con el precio. Si el tipo de
 * producto es "A", "B" o "C", el botón muestra el texto "Dibujito" y
 * al hacer clic se genera un gráfico.
 *
 * @param {string} tipo - Tipo de producto ("A", "B", "C" o "D")
 */
function actualizarBotonGrafico(tipo) {
  const btn = document.getElementById("btnGenerarGrafico");

  if (tipo === "D") {
    btn.innerHTML = `<i class="fa-solid fa-calculator me-1"></i> Cotizar`;
    btn.onclick = () => {
      // Acción para tipo D: mostrar modal con precio, por ejemplo
      calcularCotizacion(); // función que vos definas
    };
  } else {
    btn.innerHTML = `<i class="fa-solid fa-chart-column me-1"></i> Dibujito`;
    btn.onclick = () => {
      // Acción para tipos A, B, C: generar gráfico
      generarGrafico(); // función que vos definas
    };
  }
}

// Escuchar cambios en los radios
document.querySelectorAll('input[name="tipoProducto"]').forEach(radio => {
  radio.addEventListener("change", actualizarVisibilidadPorTipo);
  // Al cambiar de tipo, la magnitud de la cantidad cambia (elementos vs
  // pliegos/m²/metros): refrescar la precarga y su leyenda (cambio de contexto).
  radio.addEventListener("change", () => precargarTiempoEstimado(true));
});


/**
 * Carga las categorías desde el backend y las agrega como opciones en el select con id "selectCategoria"
 * Se utiliza fetch para obtener la lista de categorías en formato JSON y se itera sobre ella
 * para crear las opciones en el select.
 * Si hay un error en la petición se muestra un mensaje en la consola.
 */

function cargarCategoriasDesdeBackend() {
  fetch("/productos/obtenerCategorias")
    .then(response => {
      if (!response.ok) throw new Error("Error al obtener categorías");
      return response.json();
    })
    .then(categorias => {
      const select = document.getElementById("selectCategoria");
      select.innerHTML = ""; // Limpiar opciones previas

      // Placeholder
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Seleccione una categoría";
      placeholder.disabled = true;
      placeholder.selected = true;
      select.appendChild(placeholder);

      // Filtrar y cargar categorías
      categorias
        .filter(cat => cat.nombre.toLowerCase() !== "miscelaneos")
        .forEach(cat => {
          const option = document.createElement("option");
          option.value = cat.id;
          option.textContent = cat.nombre;
          select.appendChild(option);
        });

      // Refrescar Select2 tras repoblar (sin re-disparar el handler de cambio).
      if (window.jQuery && $.fn.select2) $('#selectCategoria').trigger('change.select2');
    })
    .catch(error => {
      console.error("Error en la carga de categorías:", error);
    });

}

// Se usa $(...).on('change') (no addEventListener) para que el handler también
// se dispare cuando la selección la hace Select2 (que emite el change vía jQuery).
$("#selectCategoria").on("change", function () {
  resetearSiHayGrafico();
  const categoriaId = this.value;

  // Limpiar select de productos
  const selectProducto = document.getElementById("selectProducto");
  selectProducto.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Seleccione un producto";
  placeholder.disabled = true;
  placeholder.selected = true;
  selectProducto.appendChild(placeholder);
  if (window.jQuery && $.fn.select2) $('#selectProducto').trigger('change.select2');

  // Limpiar inputs de dimensiones
  document.getElementById("inputAnchoHoja").value = "";
  document.getElementById("inputAltoHoja").value = "";

  // Cargar productos de la categoría
  cargarProductosPorCategoria(categoriaId);
});

/**
 * Carga los productos de una categoría en el select de productos.
 * @param {number} categoriaId - Id de la categoría a cargar.
 */
function cargarProductosPorCategoria(categoriaId) {
  fetch(`/productos/productosPorCategoria/${categoriaId}`)
    .then(res => res.json())
    .then(productos => {
      const select = document.getElementById("selectProducto");

      // El backend ya devuelve un representante por familia, sin duplicados.
      select.innerHTML = '<option value="">Seleccione un producto</option>';
      productos.forEach(prod => {
        const option = document.createElement("option");
        option.value = prod.id;
        option.textContent = prod.nombre;
        select.appendChild(option);
      });

      // Refrescar Select2 tras repoblar (sin re-disparar el handler de cambio).
      if (window.jQuery && $.fn.select2) $('#selectProducto').trigger('change.select2');
    })
    .catch(err => console.error("Error al cargar productos:", err));
}

$("#selectProducto").on("change", function () {
  resetearSiHayGrafico();
  const productoId = this.value;

  // Si el tipo D está seleccionado, no hacemos nada con dimensiones
  const tipoDSeleccionado = document.getElementById("tipoD")?.checked;
  if (!tipoDSeleccionado) {
    obtenerDimensionesProducto(productoId);
  }

  // Precargar el tiempo estimado del producto recién elegido (Fase 2). En tipos
  // A/B/C todavía no hay gráfico, así que la precarga fina vuelve a correr al
  // generarlo; acá cubre el tipo D y deja un valor de arranque.
  precargarTiempoEstimado(true);
});


/**
 * Fetches and updates the dimensions of a product based on its ID.
 *
 * This function makes an HTTP request to retrieve the width and height of a product
 * identified by the provided `productoId`. The retrieved dimensions are used to
 * update the corresponding input fields in the DOM. If the height is a special value
 * (100000), the height input is set to display as text with the value "Según cálculo".
 *
 * @param {number} productoId - The ID of the product for which dimensions are retrieved.
 */

// Unidad de la magnitud convergida (cantidad_producto) según el tipo de cálculo.
const _UNIDAD_POR_TIPO = { A: "pliegos", B: "m²", C: "m", D: "unidades" };

/** Formatea horas en formato AR con hasta `dec` decimales (sin ceros de más). */
function _fmtHoras(valor, dec = 3) {
  const n = Number(valor);
  if (isNaN(n)) return "";
  return n.toLocaleString("es-AR", { maximumFractionDigits: dec });
}

/** Equivalente en minutos de un valor en horas, para no tener que calcularlo. */
function _minTxt(horas) {
  const m = Number(horas) * 60;
  if (m > 0 && m < 1) return "<1 min";
  return `${Math.round(m)} min`;
}

/** Escribe la leyenda de desglose debajo del input de tiempo. */
function _renderDesgloseTiempo(texto) {
  const el = document.getElementById("tiempoDesglose");
  if (el) el.textContent = texto;
}

/**
 * Precarga el tiempo estimado de producción y muestra su desglose (Fase 2).
 *
 * Pide al backend el tiempo estimado (fórmula (setup + unitario × q) × factor)
 * y lo escribe en #inputTiempo como SUGERENCIA (el campo sigue editable).
 *
 * La cantidad relevante es la magnitud convergida (cantidad_producto):
 *  - tipo D: cantidad de elementos, conocida al instante.
 *  - tipos A/B/C: sale del packing, así que solo existe DESPUÉS del dibujo.
 *    Antes de generarlo NO se precarga (mezclaría unidades): se avisa en la
 *    leyenda y queda el default.
 *
 * Se usa el producto ya resuelto por tier (resolvedProductoId) si existe, para
 * que el tiempo precargado sea el del producto que efectivamente se cotiza.
 *
 * `resetContexto` = true en cambios de contexto (producto/tipo/dibujo): si el
 * producto no tiene tiempos, se resetea el input al default de 1 h para que no
 * quede un valor stale del producto anterior. En cambios de solo cantidad va
 * false, para no pisar una edición manual en un producto sin tiempos.
 */
function precargarTiempoEstimado(resetContexto = false) {
  const productoId = resolvedProductoId || document.getElementById("selectProducto")?.value;
  const tipo = document.querySelector('input[name="tipoProducto"]:checked')?.value || "D";
  tiemposCtx.productoId = productoId || null;
  tiemposCtx.tipo = tipo;

  if (!productoId) {
    tiemposCtx.qConocida = false;
    tiemposCtx.tieneTiempos = false;
    if (!tiemposCtx.override) _renderDesgloseTiempo("");
    return;
  }

  const cantidadElementos = parseFloat(document.getElementById("cantidadElementos")?.value) || 0;
  let cantidadProducto = cantidadElementos;
  if (tipo !== "D") {
    const resultadoGraficoInput = document.querySelector("#resultadoGraficoValor");
    const valorGrafico = resultadoGraficoInput
      ? parseFloat(resultadoGraficoInput.value || resultadoGraficoInput.dataset.valor)
      : 0;
    if (!(valorGrafico > 0)) {
      // Todavía no hay dibujo: la cantidad convergida (pliegos/m²/metros) aún no
      // existe. No se precarga para no mezclar unidades con la cant. de elementos.
      tiemposCtx.qConocida = false;
      tiemposCtx.q = 0;
      if (tiemposCtx.override) {
        _recomputarTiempoOverride();
      } else {
        if (resetContexto) document.getElementById("inputTiempo").value = 1;
        _renderDesgloseTiempo("El tiempo se calculará al generar el dibujo.");
      }
      return;
    }
    cantidadProducto = valorGrafico;
  }

  tiemposCtx.q = cantidadProducto;
  tiemposCtx.qConocida = cantidadProducto > 0;
  if (cantidadProducto <= 0) {
    if (!tiemposCtx.override) _renderDesgloseTiempo("");
    return;
  }

  fetch(`/productos/obtenerTiempos/${productoId}?cantidad=${encodeURIComponent(cantidadProducto)}`)
    .then(res => res.json())
    .then(data => {
      tiemposCtx.setup = Number(data.tiempo_setup) || 0;
      tiemposCtx.unitario = Number(data.tiempo_unitario) || 0;
      tiemposCtx.factor = Number(data.factor_correccion) || 1;
      tiemposCtx.tieneTiempos = !!data.tiene_tiempos;

      if (tiemposCtx.override) {
        // El usuario tomó control manual: no pisar sus valores, solo recalcular
        // el total con la q (que puede haber cambiado al regenerar el dibujo).
        _recomputarTiempoOverride();
        return;
      }

      if (data.tiene_tiempos && data.tiempo_estimado != null) {
        document.getElementById("inputTiempo").value = data.tiempo_estimado;
        _renderDesgloseTiempo(_leyendaDesglose(
          data.tiempo_setup, cantidadProducto, data.tiempo_unitario,
          data.factor_correccion, data.tiempo_estimado, tipo));
      } else {
        // Sin tiempos configurados: en cambio de contexto se resetea a 1 h (para
        // no dejar un valor stale); en cambio de cantidad se respeta lo tipeado.
        if (resetContexto) document.getElementById("inputTiempo").value = 1;
        _renderDesgloseTiempo("Utilizando el valor por defecto (1 h).");
      }
    })
    .catch(err => console.error("Error al precargar el tiempo estimado:", err));
}

/** Arma el texto de desglose con el equivalente en minutos de cada tiempo. */
function _leyendaDesglose(setup, q, unitario, factor, total, tipo, sufijo = "") {
  const unidad = _UNIDAD_POR_TIPO[tipo] || "unidades";
  const factorTxt = (Number(factor) !== 1) ? ` × ${_fmtHoras(factor, 2)}` : "";
  return `Setup ${_fmtHoras(setup)} h (${_minTxt(setup)}) + ${_fmtHoras(q)} ${unidad}` +
         ` × ${_fmtHoras(unitario)} h (${_minTxt(unitario)} c/u)${factorTxt}` +
         ` = ${_fmtHoras(total, 2)} h (${_minTxt(total)})${sufijo}`;
}

/**
 * Recalcula #inputTiempo a partir de los tiempos que el usuario ingresó a mano
 * (checkbox "Ajustar tiempos"), con la fórmula (setup + unitario × q) × factor.
 * En A/B/C sin dibujo (q desconocida) usa solo el setup y avisa que se completa
 * al generar el dibujo.
 */
function _recomputarTiempoOverride() {
  const setup = parseFloat(document.getElementById("inputSetupAjuste")?.value) || 0;
  const unitario = parseFloat(document.getElementById("inputUnitarioAjuste")?.value) || 0;
  const factor = tiemposCtx.factor || 1;
  const q = tiemposCtx.qConocida ? tiemposCtx.q : 0;
  const total = (setup + unitario * q) * factor;
  document.getElementById("inputTiempo").value = Math.round(total * 100) / 100;

  if (!tiemposCtx.qConocida && tiemposCtx.tipo !== "D") {
    _renderDesgloseTiempo(
      `Ajuste manual — Setup ${_fmtHoras(setup)} h (${_minTxt(setup)}) + ` +
      `(cantidad al generar el dibujo) × ${_fmtHoras(unitario)} h (${_minTxt(unitario)} c/u)`);
  } else {
    _renderDesgloseTiempo(_leyendaDesglose(
      setup, q, unitario, factor, total, tiemposCtx.tipo, " (ajuste manual)"));
  }
}

/** Activa/desactiva el override manual de tiempos (checkbox "Ajustar tiempos"). */
function toggleAjusteTiempos(activo) {
  tiemposCtx.override = activo;
  const wrapper = document.getElementById("tiemposAjuste");
  const inputTiempo = document.getElementById("inputTiempo");
  if (wrapper) wrapper.style.display = activo ? "flex" : "none";

  if (activo) {
    // Precargar los inputs de ajuste con los tiempos actuales del producto y
    // pasar el total a solo-lectura (se calcula desde setup/unitario).
    const inSetup = document.getElementById("inputSetupAjuste");
    const inUnit = document.getElementById("inputUnitarioAjuste");
    if (inSetup) inSetup.value = tiemposCtx.setup || 0;
    if (inUnit) inUnit.value = tiemposCtx.unitario || 0;
    if (inputTiempo) inputTiempo.readOnly = true;
    _recomputarTiempoOverride();
  } else {
    // Volver a la sugerencia automática.
    if (inputTiempo) inputTiempo.readOnly = false;
    precargarTiempoEstimado(true);
  }
}

function obtenerDimensionesProducto(productoId) {
  fetch(`/productos/obtenerDimensiones/${productoId}`)
    .then(res => res.json())
    .then(data => {
      const inputAncho = document.getElementById("inputAnchoHoja");
      const inputAlto = document.getElementById("inputAltoHoja");

      inputAncho.value = data.ancho;

      if (data.alto === 100000) {
        inputAlto.setAttribute("type", "text");
        inputAlto.value = "Según cálculo";
      } else {
        inputAlto.setAttribute("type", "number");
        inputAlto.value = data.alto;
      }


    })
    .catch(err => console.error("Error al obtener dimensiones:", err));
}

/**
 * Generates a graphical representation based on user input and displays it on the page.
 *
 * This function collects various input values from the DOM to create a FormData object
 * that is sent to the backend to generate a graphical representation. It uses the selected
 * product type, sheet dimensions, element dimensions, element quantity, and packing algorithm.
 * The generated graph is displayed in the DOM element with the ID "graficoCotizacion", and
 * accompanying buttons are updated accordingly. If an error occurs during the process,
 * it logs an error message to the console.
 */

function generarGrafico() {
  const csrfToken = getCookie("csrftoken");
  const algoritmosPacking = ["Skyline", "MaxRects"];
  const algoritmoIndex = parseInt(document.getElementById("btn-regenerar")?.dataset.algoritmo || "0");
  const algoritmoNombre = algoritmosPacking[algoritmoIndex];
  const tipoCalculo = document.querySelector('input[name="tipoProducto"]:checked').value;

  const formData = new FormData();
  formData.append("tipo", tipoCalculo);
  formData.append("anchoHoja", document.getElementById("inputAnchoHoja").value);
  formData.append("altoHoja", document.getElementById("inputAltoHoja").value);
  formData.append("anchoElemento", document.getElementById("inputAnchoElemento").value);
  formData.append("altoElemento", document.getElementById("inputAltoElemento").value);
  formData.append("cantidadElementos", document.getElementById("cantidadElementos").value);
  const valorSeparacion = document.getElementById("separacionElementos").value || "0";
  formData.append("separacionElementos", valorSeparacion);
  formData.append("algoritmo", algoritmoNombre);

  fetch("/presupuestos/generarGrafico/", {
    method: "POST",
    headers: { "X-CSRFToken": csrfToken },
    body: formData
  })
    .then(res => res.json())
    .then(async data => {
      const graficoContainer = document.getElementById("graficoCotizacion");
      graficoContainer.innerHTML = `
        <img src="${data.grafico_url}" class="img-fluid mb-3">
        <p class="mt-2 fw-semibold text-secondary" id="mensajeGrafico">${data.mensaje}</p>
        <input type="hidden" id="resultadoGraficoValor" value="${data.valor_grafico}" />
      `;
      document.getElementById("seccionGrafico").style.display = "block";

      mostrarBotonesGrafico(algoritmoIndex);
      actualizarBotonGrafico(data.tipo);

      // Para tipo A: resolver el tier correcto según la cantidad de hojas necesarias
      if (tipoCalculo === "A") {
        const productoId = document.getElementById("selectProducto").value;
        const cantidadHojas = Math.ceil(parseFloat(data.valor_grafico) || 0);
        const tierData = await resolverTierProducto(productoId, cantidadHojas);
        if (tierData && tierData.tier_encontrado) {
          const mensajeEl = document.getElementById("mensajeGrafico");
          if (mensajeEl) {
            mensajeEl.innerHTML +=
              `<br><span class="text-primary fw-semibold">→ Se cotizará con: <strong>${tierData.nombre}</strong> (rango ${tierData.rango_display})</span>`;
          }
        }
      }

      // Ya hay resultado de gráfico (y tier resuelto para tipo A): precargar el
      // tiempo estimado con la cantidad convergida real (hojas/m²/metros).
      precargarTiempoEstimado(true);
    })
    .catch(err => {
      console.error("❌ Error al generar gráfico:", err);
    });
}


/**
 * Displays buttons related to the graph functionality.
 *
 * This function generates HTML for buttons that allow users to download,
 * delete, or regenerate a graph. The regenerating button cycles through
 * predefined packing algorithms based on the given index.
 *
 * @param {number} [indexActual=0] - The current index of the packing algorithm,
 * which determines the next algorithm to use when regenerating the graph.
 */

function mostrarBotonesGrafico(indexActual = 0) {
  const algoritmosPacking = ["Skyline", "MaxRects"];
  const siguienteIndex = (indexActual + 1) % algoritmosPacking.length;

  const botonesHTML = `
    <button id="btnDescargarGrafico" class="btn btn-grafico btn-dark" onclick="descargarGrafico()">
      <i class="fa-solid fa-download"></i>
    </button>
    <button id="btnBorrarGrafico" class="btn btn-grafico btn-dark" onclick="borrarGrafico()">
      <i class="fa-solid fa-trash-can" type="button"></i>
    </button>
    <button id="btn-regenerar" class="btn btn-grafico btn-dark" data-algoritmo="${siguienteIndex}" onclick="generarGrafico()">
      <i class="fa-solid fa-arrows-rotate"></i>
    </button>
  `;

  document.getElementById("botonesGrafico").innerHTML = botonesHTML;
}

/**
 * Borra la imagen generada en el servidor y restablece el botón principal.
 *
 * Hace una petición POST a la vista `borrarImagenGenerada` para eliminar
 * la imagen generada en el servidor. Luego, limpia el contenido del
 * gráfico y oculta la sección del gráfico. Finalmente, restaura el
 * botón principal a "Dibujito".
 */
function borrarGrafico() {
  // Limpiar estado de tier resuelto
  resolvedProductoId = null;
  resolvedProductoNombre = null;

  fetch('/presupuestos/borrarImagenGenerada', {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCookie('csrftoken'),
      'Content-Type': 'application/json'
    }
  })
    .then(response => response.json())
    .then(data => {
      const graficoContenedor = document.getElementById("graficoCotizacion");
      graficoContenedor.innerHTML = "";
      actualizarBotonGrafico("ABC");
    })
    .catch(error => {
      console.error('❌ Error al eliminar la imagen:', error);
    });
}

function resetearSiHayGrafico() {
  const graficoContenedor = document.getElementById("graficoCotizacion");
  if (graficoContenedor && graficoContenedor.innerHTML.trim() !== "") {
    borrarGrafico();
  }
}

async function resolverTierProducto(productoId, cantidad) {
  try {
    const formData = new FormData();
    formData.append('producto_id', productoId);
    formData.append('cantidad', cantidad);

    const res = await fetch('/productos/resolverTier', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      body: formData
    });
    const data = await res.json();

    resolvedProductoId = data.producto_id;
    resolvedProductoNombre = data.nombre;
    return data;
  } catch (err) {
    console.error('❌ Error al resolver tier:', err);
    resolvedProductoId = productoId;
    return null;
  }
}


/**
 * Descarga el gráfico generado en formato PNG.
 *
 * Busca la imagen del gráfico dentro del contenedor #graficoCotizacion.
 * Si se encuentra la imagen, crea un enlace de descarga con el nombre 
 * de archivo basado en la fecha actual (formato: cotizacion_YYYY-MM-DD.png).
 * Si no se encuentra la imagen, muestra una advertencia en la consola.
 */

function descargarGrafico() {
  const imgElement = document.querySelector("#graficoCotizacion img");
  const nombreArchivo = `cotizacion_${new Date().toISOString().slice(0,10)}.png`;

  if (!imgElement || !imgElement.src) {
    console.warn("⚠️ No se encontró el gráfico para descargar.");
    return;
  }

  const link = document.createElement('a');
  link.href = imgElement.src;
  link.download = nombreArchivo;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function calcularCotizacion() {
  const formData = new FormData();
  // Usar el tier resuelto por el packing si existe; si no, el seleccionado directamente
  const productoIdFinal = resolvedProductoId || document.getElementById("selectProducto").value;
  formData.append("producto_id", productoIdFinal);
  formData.append("cantidadElementos", document.getElementById("cantidadElementos").value);
  formData.append("inputTiempo", document.getElementById("inputTiempo").value);
  formData.append("empaquetado", document.getElementById("checkEmpaquetado").checked);
  formData.append("producto_final", document.getElementById("inputProductoFinal").value);
  formData.append("info_adic", document.getElementById("inputInfoAdic").value);
  formData.append("descuento", document.getElementById("inputDescuento").value || 0);
  const tipoCotizacion = document.querySelector('input[name="tipoProducto"]:checked')?.value || "D";
  formData.append("tipoCotizacion", tipoCotizacion);

  const resultadoGraficoInput = document.querySelector("#resultadoGraficoValor");
  if (resultadoGraficoInput) {
    const valor = resultadoGraficoInput.value || resultadoGraficoInput.dataset.valor;
    formData.append("resultado_grafico", valor);
  }

  fetch("/presupuestos/calcularCotizacionFinal", {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken")
    },
    body: formData
  })
    .then(res => res.json())
    .then(data => {
      mostrarModalResultado(data);
    })
    .catch(err => {
      console.error("❌ Error en cálculo final:", err);
    });
}

function mostrarModalResultado(data) {
  document.getElementById("prod_prev").textContent = data.insumo;
  document.getElementById("producto_final_prev").textContent = data.producto_final;
  document.getElementById("info_adic_prev").textContent = data.info_adic;
  document.getElementById("cant_prev").textContent = data.cantidad;
  document.getElementById("cant_area_prev").textContent = formatearNumeroLocal(data.resultado_grafico);
  document.getElementById("precio_prev").textContent = formatearNumeroLocal(data.precio_total);
  document.getElementById("descuento_prev").textContent = data.descuento || "—";
  document.getElementById("empaquetado_prev").textContent = data.empaquetado;
  document.getElementById("t_produccion_prev").textContent = formatearNumeroLocal(data.tiempo_produccion);

  // Comparación de métodos (Fase 3): informativo, no cambia lo que se cobra.
  document.getElementById("precio_actual_bruto_prev").textContent = formatearNumeroLocal(data.precio_actual_bruto);
  document.getElementById("precio_sugerido_prev").textContent = formatearNumeroLocal(data.precio_sugerido);
  document.getElementById("piso_absoluto_prev").textContent = formatearNumeroLocal(data.piso_absoluto);
  document.getElementById("piso_absorcion_prev").textContent = formatearNumeroLocal(data.piso_absorcion);
  document.getElementById("tasa_hora_prev").textContent = formatearNumeroLocal(data.tasa_hora);

  // Diferencia % entre el método sugerido y el actual (bruto vs bruto).
  const actualBruto = Number(data.precio_actual_bruto) || 0;
  const sugerido = Number(data.precio_sugerido) || 0;
  const difEl = document.getElementById("diferencia_prev");
  if (actualBruto > 0) {
    const difPct = (sugerido / actualBruto - 1) * 100;
    const signo = difPct >= 0 ? "+" : "";
    difEl.textContent = `${signo}${formatearNumeroLocal(difPct)} %`;
    difEl.className = difPct >= 0 ? "text-success" : "text-danger";
  } else {
    difEl.textContent = "—";
    difEl.className = "";
  }
  document.getElementById("detalle_prev").textContent = data.detalle;

  const modal = new bootstrap.Modal(document.getElementById("resultadoPrevioModal"));

  // Datos de dimensiones desde el DOM
  const anchoElem = document.getElementById("inputAnchoElemento").value;
  const altoElem = document.getElementById("inputAltoElemento").value;
  const anchoHoja = document.getElementById("inputAnchoHoja").value;
  const altoHoja = document.getElementById("inputAltoHoja").value;

  // Cantidad de pliegos/hojas calculada por el backend
  const pliegos = formatearNumeroLocal(data.resultado_grafico);

  // Armar texto final
  let detalleFinal = "";

  detalleFinal += `${data.producto_final}\n\n`;

  detalleFinal += `Dimensiones: ${anchoElem} × ${altoElem} cm\n`;
  //detalleFinal += `Dimensiones de la hoja/pliego: ${anchoHoja} × ${altoHoja} cm\n`;
  detalleFinal += `Cantidad de hojas/m2: ${pliegos}`;

  // Insertar en el modal
  document.getElementById("detalle_prev").textContent = detalleFinal;
  
  // --- Actualizar la sesión en el backend ---
  fetch("/presupuestos/actualizarDetalle", {
      method: "POST",
      headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken")
      },
      body: JSON.stringify({ detalle: detalleFinal })
  })
  .then(res => res.json())
  .then(data => {
      console.log("Detalle actualizado en sesión:", data);
  })
  .catch(err => {
      console.error("Error al actualizar detalle:", err);
  });

  modal.show();
}

function descartarProducto() {
  fetch("/presupuestos/descartarProducto", {
      method: "GET",
      headers: {
          "X-Requested-With": "XMLHttpRequest"
      }
  })
  .then(response => response.json())
  .then(data => {
      if (data.status === "ok") {
        const modalElement = document.getElementById("resultadoPrevioModal");
        const modalInstance = bootstrap.Modal.getInstance(modalElement);
        if (modalInstance) {
          modalInstance.hide();
        }
      }
  });
}

// function guardarPresupuesto() {
//     const clienteInput = document.getElementById("cliente");
//     const cliente = clienteInput ? clienteInput.value.trim() : "";

//     // Armamos la URL con el cliente como parámetro GET
//     const url = `/presupuestos/guardarPresupuesto?cliente=${encodeURIComponent(cliente)}`;

//     // Redirigimos
//     window.location.href = url;
// }


/* Funcionalidad para evitar la eliminación de objetos listados en la cotización por un click involuntario. */
// (function () {
//     const btnEliminacion = document.querySelectorAll(".btnEliminacion");
//     btnEliminacion.forEach(btn=>{
//         btn.addEventListener("click", (e)=>{
//             const confirmacion = confirm("¿Está segur@ de que desea eliminar este elemento?");
//             if(!confirmacion){
//                 e.preventDefault();
//             }    
//         });
//     });
// })();

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      // Verifica si la cookie comienza con el nombre deseado
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Resetear el gráfico si el usuario cambia parámetros que afectan el resultado
["cantidadElementos", "inputAnchoElemento", "inputAltoElemento", "separacionElementos"].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener("input", resetearSiHayGrafico);
});

// En tipo D el tiempo depende directo de la cantidad de elementos (no hay
// gráfico que lo dispare), así que se reprecarga al cambiarla. En A/B/C la
// precarga la maneja generarGrafico con la cantidad convergida real.
document.getElementById("cantidadElementos")?.addEventListener("input", function () {
  const tipoD = document.getElementById("tipoD")?.checked;
  // resetContexto=false: no pisar una edición manual en productos sin tiempos.
  if (tipoD) precargarTiempoEstimado(false);
});

// --- Override manual de tiempos (Fase 2, checkbox "Ajustar tiempos") ---
document.getElementById("chkAjustarTiempos")?.addEventListener("change", function () {
  toggleAjusteTiempos(this.checked);
});
["inputSetupAjuste", "inputUnitarioAjuste"].forEach(id => {
  document.getElementById(id)?.addEventListener("input", function () {
    if (tiemposCtx.override) _recomputarTiempoOverride();
  });
});

/**
 * Intercepta "Agregar" para ofrecer guardar en el producto los tiempos ajustados
 * a mano (Fase 2, save-back). Cualquier vendedor puede guardarlos; la traza queda
 * en el t_produccion del ProductoCotizado y en la leyenda mostrada. Si no hubo
 * override, o el usuario dice que no, se agrega normalmente.
 */
document.getElementById("btnAgregarProducto")?.addEventListener("click", function (e) {
  const destino = this.getAttribute("href") || "/presupuestos/agregarProducto";
  if (!tiemposCtx.override || !tiemposCtx.productoId) return; // flujo normal

  e.preventDefault();
  const setup = parseFloat(document.getElementById("inputSetupAjuste")?.value) || 0;
  const unitario = parseFloat(document.getElementById("inputUnitarioAjuste")?.value) || 0;

  const guardar = confirm(
    `¿Guardar estos tiempos en el producto para futuras cotizaciones?\n\n` +
    `Setup: ${_fmtHoras(setup)} h\nPor unidad: ${_fmtHoras(unitario)} h\n\n` +
    `(Aceptar = guardar y agregar · Cancelar = agregar sin guardar)`);

  if (!guardar) { window.location.href = destino; return; }

  const formData = new FormData();
  formData.append("producto_id", tiemposCtx.productoId);
  formData.append("tiempo_setup", setup);
  formData.append("tiempo_unitario", unitario);

  fetch("/productos/guardarTiempos", {
    method: "POST",
    headers: { "X-CSRFToken": getCookie("csrftoken") },
    body: formData
  })
    .then(res => res.json())
    .then(data => {
      if (!data.ok) console.error("No se pudieron guardar los tiempos:", data.mensaje);
    })
    .catch(err => console.error("Error al guardar los tiempos:", err))
    .finally(() => { window.location.href = destino; });
});

function syncClienteYEnviar(url) {
    const cliente = document.getElementById("cliente_input").value;

    fetch("/presupuestos/setClienteSession", {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": getCookie("csrftoken")
        },
        body: "cliente=" + encodeURIComponent(cliente)
    }).then(() => {
        window.location.href = url;
    });
}
