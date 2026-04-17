
let dataTable;
let dataTableIsInitilized=false;
// Lógica que inicializa la dataTable Productos.
const initDataTable = async () => {
    if (dataTableIsInitilized) {
        dataTable.destroy();
    }

    dataTable = $("#Productos").DataTable({
        dom: "<'row'<'col-sm-6'<'#categoriaContainer'>><'col-sm-6'>>" +
             "t" +
             "<'row'<'col-sm-6'i><'col-sm-6'p>>", // Define la ubicación de controles
        responsive: true,
        language: {
            lengthMenu: 'Mostrar _MENU_ productos por página',
            zeroRecords: 'No hay productos registrados',
            info: 'Mostrando de _START_ a _END_ de _TOTAL_ productos',
            infoEmpty: 'No hay productos',
            InfoFiltered: '(filtrado de _MAX_ productos totales)',
            LoadingRecords: 'Cargando...',
            paginate: {
                first: 'Primero',
                last: 'Último',
                next: 'Siguiente',
                previous: 'Anterior'
            }
        },
        initComplete: function () {
            // Filtro por categoría
            var categoriaFilter = $('<label for="categoriaFilter" class="me-2">Filtrar por categoría:</label><select id="categoriaFilter" class="form-select d-inline-block w-auto"><option value="">Todas</option></select>');
            $('.categoria-filter').append(categoriaFilter);

            // Buscador personalizado
            var customSearch = $('<label for="tableSearch" class="me-2">Buscar:</label><input type="text" id="tableSearch" class="form-control d-inline-block w-auto" placeholder="Escribí para buscar...">');
            $('.buscador').append(customSearch);


            // Cargar categorías dinámicamente desde el backend
            fetch('/productos/listarCategorias/')
                .then(response => response.json())
                .then(data => {
                    data.categorias.forEach(function (categoria) {
                        $('#categoriaFilter').append(`<option value="${categoria}">${categoria}</option>`);
                    });

                    // Agregar evento de filtrado
                    $('#categoriaFilter').on('change', function () {
                        dataTable.column(4).search($(this).val()).draw();
                    });
                })
                .catch(error => console.error('Error al cargar categorías:', error));
                // Buscador personalizado
            $('#tableSearch').on('keyup', function () {
                dataTable.search($(this).val()).draw();
            });
        }
    });

    dataTableIsInitilized = true;
};

window.addEventListener("load", async() => {
    await initDataTable();
    document.getElementById("nav_item_productos").style.fontWeight = "bold";
});
// Lógica que evita la eliminación de objetos listados en la cotización por un click involuntario.
// (function () {
//     const btnEliminacion = document.querySelectorAll(".btnEliminacion");
//     btnEliminacion.forEach(btn=>{
//         btn.addEventListener("click", (e)=>{
//             const confirmacion = confirm("¿Está segur@ de que desea continuar con el borrado? (Esto no se puede deshacer.)");
//             if(!confirmacion){
//                 e.preventDefault();
//             }    
//         });
//     });
// })();

//---------------------------------------- Sección nueva Insumos -> Productos

let insumosDisponibles = [];
let factorConversion = 1.15; // Si el producto no es tercerizado, se aplica este margen
let margenRentabilidad = 1.15; // Se puede vincular a un input para ser editable
let precioProveedor = 0; // Para casos de producto tercerizado

async function cargarInsumos() {
  try {
    const res = await fetch('/productos/obtenerInsumos');
    insumosDisponibles = await res.json();
  } catch (err) {
    console.error('Error al cargar insumos:', err);
  }
}

async function cargarCategorias() {
  try {
    const res = await fetch('/productos/obtenerCategorias');
    const categorias = await res.json();
    const select = document.getElementById('productoCategoria');
    select.innerHTML = '<option value="">-- Elegir categoría --</option>';
    categorias.forEach(cat => {
      select.innerHTML += `<option value="${cat.id}">${cat.nombre}</option>`;
    });
  } catch (err) {
    console.error('Error al cargar categorías:', err);
  }
}

// 🔁 Mostrar/ocultar sección de insumos y precio de proveedor
function toggleInsumos(esTercerizado) {
  const seccion = document.getElementById('seccion-insumos');
  const precioWrapper = document.getElementById('precioProveedorWrapper');

  seccion.style.display = esTercerizado ? 'none' : 'block';
  precioWrapper.style.display = esTercerizado ? 'block' : 'none';

  if (!esTercerizado && insumosDisponibles.length === 0) {
    cargarInsumos();
  }
  actualizarResumen();
}

// ➕ Agrega fila de insumo con lógica JS
function agregarFilaInsumo() {
  const fila = document.createElement('div');
  fila.className = 'fila-insumo d-flex align-items-center gap-2';

  const opciones = insumosDisponibles.map(ins => `<option value="${ins.id}">${ins.nombre}</option>`).join('');

  fila.innerHTML = `
    <select class="form-select select-insumo" onchange="actualizarPU(this)">
      <option value="">-- Elegir insumo --</option>
      ${opciones}
    </select>
    <div class="d-flex align-items-center gap-1">
      <input type="number" class="form-control cantidad-insumo" value="1" min="0"
             onchange="actualizarSubtotal(this.closest('.fila-insumo'))">
      <span class="unidad-uso text-muted">---</span>
    </div>
    <span class="pu-insumo">$0.00</span>
    <span class="subtotal-insumo">$0.00</span>
    <button type="button" class="btn btn-sm btn-outline-danger" onclick="borrarFila(this)" title="Eliminar insumo">
      <i class="fa-solid fa-trash"></i>
    </button>
  `;

  document.getElementById('insumos-container').appendChild(fila);
}
function borrarFila(btn) {
  const fila = btn.closest('.fila-insumo');
  fila.remove();
  actualizarResumen();
}


// 🔎 Consulta precio unitario según insumo
async function actualizarPU(select) {
  const fila = select.closest('.fila-insumo');
  const id = select.value;
  if (!id) return;

  try {
    const res = await fetch(`/productos/datosInsumo/${id}`);
    const { precio, u_de_uso } = await res.json();

    fila.querySelector('.pu-insumo').textContent = `$ ${formatearNumeroLocal(precio)}`;
    fila.querySelector('.unidad-uso').textContent = u_de_uso;
    actualizarSubtotal(fila);
  } catch (err) {
    console.error('Error al obtener datos del insumo:', err);
  }
}

// 🔢 Calcula subtotal individual
function actualizarSubtotal(fila) {
  const cantidad = parseFloat(fila.querySelector('.cantidad-insumo').value) || 0;
  const pu = parsearNumeroLocal(fila.querySelector('.pu-insumo').textContent.replace('$', '')) || 0;
  const subtotal = cantidad * pu;
  fila.querySelector('.subtotal-insumo').textContent = `$ ${formatearNumeroLocal(subtotal)}`;
  actualizarResumen();
}

// 🧾 Recalcula costos totales según tercerizado y margen
function actualizarResumen() {
  const esTercerizado = document.getElementById('tercerizado-checkbox').checked;
  const inputPrecio = document.getElementById('productoPrecioProveedor');
  const inputMargen = document.getElementById('productoMargen');

  precioProveedor = parsearNumeroLocal(inputPrecio?.value) || 0;
  margenRentabilidad = parsearNumeroLocal(inputMargen?.value) || factorConversion;
  
  let costoBase = 0;

  if (esTercerizado) {
    costoBase = precioProveedor;
  } else {
    document.querySelectorAll('.subtotal-insumo').forEach(span => {
      costoBase += parsearNumeroLocal(span.textContent.replace('$', '')) || 0;
    });
  }

  document.getElementById('costo-total').textContent = `$ ${formatearNumeroLocal(costoBase)}`;
  document.getElementById('costo-final').textContent = `$ ${formatearNumeroLocal(costoBase * margenRentabilidad)}`;
}

// 🔁 Modal abierto: inicialización
document.getElementById('crearProductoModal').addEventListener('show.bs.modal', async function (event) {
  const button = event.relatedTarget;
  const productoId = button.getAttribute('data-bs-whatever');
  const idInput = document.querySelector('[name="id_producto"]');

  await cargarCategorias();
  await cargarInsumos();

  if (productoId === 'nuevo') {
    idInput.value = '0';
    resetearModalProducto();
  } else {
    idInput.value = productoId;
    await completarFormulario(productoId);
  }

  actualizarResumen();
});

async function completarFormulario(idProducto) {
  try {
    const res = await fetch(`/productos/obtenerProducto/${idProducto}`);
    const data = await res.json();

    document.getElementById('productoNombre').value = data.nombre;
    document.getElementById('productoCategoria').value = data.categoria_id;
    document.getElementById('productoAncho').value = data.ancho;
    document.getElementById('productoAlto').value = data.alto;
    document.getElementById('productoMargen').value = formatearNumeroLocal(data.margen);
    document.getElementById('tercerizado-checkbox').checked = data.tercerizado;
    document.getElementById('productoPrecioProveedor').value = formatearNumeroLocal(data.precio_proveedor);

    toggleInsumos(data.tercerizado); // actualiza visual

    const contenedor = document.getElementById('insumos-container');
    contenedor.innerHTML = '';
    if (!data.tercerizado && data.insumos?.length > 0) {
      data.insumos.forEach(insumo => agregarFilaInsumoConDatos(insumo.id, insumo.cantidad));
    }
  } catch (err) {
    console.error('Error al completar formulario:', err);
  }
}

function agregarFilaInsumoConDatos(insumoId, cantidad) {
  agregarFilaInsumo();
  const fila = document.querySelectorAll('.fila-insumo')[document.querySelectorAll('.fila-insumo').length - 1];
  fila.querySelector('.select-insumo').value = insumoId;
  fila.querySelector('.cantidad-insumo').value = cantidad;
  actualizarPU(fila.querySelector('.select-insumo'));
}


// 🔁 Modal cerrado: limpiar
async function limpiarModalProducto() {
  document.getElementById('productoNombre').value = '';
  document.getElementById('productoCategoria').innerHTML = '';
  document.getElementById('productoAncho').value = '';
  document.getElementById('productoAlto').value = '';
  document.getElementById('insumos-container').innerHTML = '';
  document.getElementById('costo-total').textContent = '$0.00';
  document.getElementById('costo-final').textContent = '$0.00';
  document.getElementById('precioProveedorWrapper').style.display = 'block';
  document.getElementById('tercerizado-checkbox').checked = true;
  document.getElementById('productoPrecioProveedor').value = ' ';
  document.getElementById('productoMargen').value = '1';
  document.getElementById('seccion-insumos').style.display = 'none';
}

async function resetearModalProducto() {
  await limpiarModalProducto();
  await cargarCategorias();
}


document.getElementById('crearProductoModal').addEventListener('hidden.bs.modal', function () {
  resetearModalProducto();
});

// 📡 Eventos para campos clave
document.getElementById('productoTercerizado')?.addEventListener('change', function () {
  toggleInsumos(this.checked);
});

document.getElementById('productoPrecioProveedor')?.addEventListener('input', actualizarResumen);
document.getElementById('productoMargen')?.addEventListener('input', actualizarResumen);

// Intercepta el envío del formulario para serializar los insumos si corresponde de modo que el backend pueda interpretarlos adecuadamente.
async function guardarProducto() {
  const formData = new FormData();
  const tercerizado = document.getElementById('tercerizado-checkbox').checked;
  const idProducto = document.querySelector('[name="id_producto"]').value;

  formData.append("id_producto", idProducto);
  formData.append("productoNombre", document.getElementById("productoNombre").value || '');
  formData.append("productoCategoria", document.getElementById("productoCategoria").value || '');
  formData.append("productoAncho", document.getElementById("productoAncho").value || '');
  formData.append("productoAlto", document.getElementById("productoAlto").value || '');
  formData.append("productoMargen", document.getElementById("productoMargen").value || '');
  const precioTexto = document.getElementById("costo-total").textContent;
  const precioLimpio = parsearNumeroLocal(precioTexto.replace(/\$/g, "").trim());
  formData.append("productoPrecio", precioLimpio);
  formData.append("tercerizado", document.getElementById("tercerizado-checkbox").checked ? "on" : "");

  if (!tercerizado) {
    const filas = document.querySelectorAll('.fila-insumo');
    filas.forEach((fila, idx) => {
      const insumoId = fila.querySelector('.select-insumo').value;
      const cantidad = fila.querySelector('.cantidad-insumo').value;
      if (insumoId && parseFloat(cantidad) > 0) {
        formData.append(`insumo_${idx}_id`, insumoId);
        formData.append(`insumo_${idx}_cantidad`, cantidad);
      }
    });
  }

try {
  const res = await fetch('/productos/guardarProducto', {
    method: 'POST',
    headers: {
      "X-CSRFToken": obtenerCSRFToken(),
    },
    body: formData,
  });

  const data = await res.json();

  if (data.ok && data.redirect_url) {
    sessionStorage.setItem("flashMensaje", data.mensaje);
    sessionStorage.setItem("flashTipo", "success");
    limpiarModalProducto();  // según tu lógica
    window.location.href = data.redirect_url;
  } else {
    sessionStorage.setItem("flashMensaje", data.mensaje || "Error inesperado.");
    sessionStorage.setItem("flashTipo", "error");
    window.location.href = "/productos";  // redirigimos igual para mostrar el error
  }

} catch (err) {
  console.error('Error al guardar producto:', err);
  sessionStorage.setItem("flashMensaje", "Error al guardar producto. Intentá nuevamente.");
  sessionStorage.setItem("flashTipo", "error");
  window.location.href = "/productos";
}
}

function obtenerCSRFToken() {
  const cookieValue = document.cookie
    .split("; ")
    .find(row => row.startsWith("csrftoken="));
  return cookieValue ? cookieValue.split("=")[1] : "";
}

// Escucha la carga de un archivo en el botón de carga masiva de Productos y dispara el submit para automatizar la carga.
document.getElementById('excelFileInput').addEventListener('change', function() {
  if (this.files.length > 0) {
    document.getElementById('formCargaAuto').submit();
  }
});