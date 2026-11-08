/* Pedidos tercerizados: tablas, modal de alta/edición y armado del pago.
 *
 * Los montos se muestran e ingresan en formato argentino (1.234,56): se usan
 * formatearNumeroLocal / parsearNumeroLocal de core.js, igual que el resto del
 * proyecto. El backend los vuelve a parsear con parse_ar.
 */

let tablaTercerizados;
let tablaPagos;
let tablasIniciadas = false;

const idioma = {
  lengthMenu: "Mostrar _MENU_ registros por página",
  zeroRecords: "No hay registros que coincidan",
  info: "Mostrando de _START_ a _END_ de _TOTAL_ registros",
  infoEmpty: "Sin registros",
  infoFiltered: "(filtrado de _MAX_ registros totales)",
  search: "Buscar:",
  loadingRecords: "Cargando...",
  paginate: { first: "Primero", last: "Último", next: "Siguiente", previous: "Anterior" },
};

const iniciarTablas = () => {
  if (tablasIniciadas) {
    tablaTercerizados.destroy();
    tablaPagos.destroy();
  }
  tablaTercerizados = $("#TablaTercerizados").DataTable({
    responsive: true,
    pageLength: 25,
    order: [[1, "desc"]],
    // La columna de checkboxes y la de acciones no se ordenan ni se buscan.
    columnDefs: [
      { targets: [0, 12], orderable: false, searchable: false },
      { responsivePriority: 1, targets: 3 },
      { responsivePriority: 2, targets: 7 },
    ],
    language: idioma,
  });
  tablaPagos = $("#TablaPagosTercerizados").DataTable({
    responsive: true,
    pageLength: 10,
    order: [[0, "desc"]],
    columnDefs: [{ targets: [8], orderable: false, searchable: false }],
    language: idioma,
  });
  tablasIniciadas = true;
};

window.addEventListener("load", () => {
  iniciarTablas();
  const item = document.getElementById("nav_item_tercerizados");
  if (item) item.style.fontWeight = "bold";
});

/* ------------------------------------------------ Seleccionar todos */

document.addEventListener("DOMContentLoaded", () => {
  const global = document.getElementById("seleccionarTodos");
  if (!global) return;
  global.addEventListener("change", () => {
    // Solo las filas visibles de la página actual de la DataTable.
    document
      .querySelectorAll("#TablaTercerizados tbody .fila-checkbox")
      .forEach((cb) => {
        cb.checked = global.checked;
      });
  });
});

/* ------------------------------------------------ Ver solo sin revisar */

document.addEventListener("DOMContentLoaded", () => {
  const boton = document.getElementById("btnFiltrarSinRevisar");
  if (!boton) return;
  boton.addEventListener("click", () => {
    // El origen "agente" sin revisar se reconoce por el badge de la tabla:
    // se filtra con el buscador de la DataTable.
    tablaTercerizados.search("sin revisar").draw();
  });
});

/* ------------------------------------------------ Modal de alta / edición */

document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("pedidoTercerizadoModal");
  if (!modal) return;
  const titulo = document.getElementById("pedidoTercerizadoModalLabel");
  const form = document.getElementById("formPedidoTercerizado");
  const info = document.getElementById("infoPagosPedido");

  modal.addEventListener("show.bs.modal", (evento) => {
    const boton = evento.relatedTarget;
    const id = boton ? boton.getAttribute("data-bs-whatever") : "0";
    info.style.display = "none";
    info.innerHTML = "";

    if (!id || id === "0") {
      titulo.textContent = "Registrar pedido tercerizado";
      form.reset();
      document.getElementById("pedidoId").value = "0";
      return;
    }

    titulo.textContent = "Cargando…";
    fetch(`/tercerizados/info/${id}`)
      .then((res) => {
        if (!res.ok) throw new Error("No se pudo obtener el pedido");
        return res.json();
      })
      .then((datos) => {
        titulo.textContent = `Editar pedido #${datos.id}`;
        document.getElementById("pedidoId").value = datos.id;
        document.getElementById("fechaPedido").value = datos.fecha;
        document.getElementById("proveedorPedido").value = datos.proveedor;
        document.getElementById("descripcionPedido").value = datos.descripcion;
        document.getElementById("pedidosInternosPedido").value =
          (datos.pedidos_internos ?? []).join(", ");
        document.getElementById("montoPedido").value = formatearNumeroLocal(datos.monto);
        document.getElementById("formaPagoPedido").value = datos.forma_pago;
        document.getElementById("estadoPedido").value = datos.estado;
        document.getElementById("notaPedido").value = datos.nota ?? "";

        if (datos.monto_pagado > 0) {
          info.style.display = "block";
          info.innerHTML =
            `<i class="fa-solid fa-circle-info"></i> Este pedido ya tiene ` +
            `$ ${formatearNumeroLocal(datos.monto_pagado)} imputados ` +
            `(saldo $ ${formatearNumeroLocal(datos.saldo)}). El monto no puede ` +
            `quedar por debajo de lo pagado, y para cancelarlo o cambiarle el ` +
            `proveedor hay que anular el pago primero.`;
        } else if (datos.origen === "agente" && !datos.revisado) {
          info.style.display = "block";
          info.innerHTML =
            `<i class="fa-solid fa-robot"></i> Lo cargó el agente desde el correo ` +
            `y todavía no estaba revisado. Al guardar queda marcado como revisado.`;
        }
      })
      .catch((error) => {
        console.error("Error al cargar el pedido tercerizado:", error);
        titulo.textContent = "Error al cargar el pedido";
      });
  });
});

/* ------------------------------------------------ Modal de pago */

document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("pagoTercerizadoModal");
  if (!modal) return;

  const selectProveedor = document.getElementById("proveedorPago");
  const lista = document.getElementById("listaImputaciones");
  const resumen = document.getElementById("imputacionesResumen");
  const montoPago = document.getElementById("montoPago");
  const botonAuto = document.getElementById("btnRepartirAuto");
  let pendientes = [];

  const dibujarResumen = () => {
    const total = pendientes.reduce((acumulado, pedido) => {
      const campo = document.getElementById(`imputacion_${pedido.id}`);
      return acumulado + (campo ? parsearNumeroLocal(campo.value) : 0);
    }, 0);
    const pagado = parsearNumeroLocal(montoPago.value);
    const sobrante = pagado - total;

    let texto = `Imputado: <strong>$ ${formatearNumeroLocal(total)}</strong>`;
    if (pagado > 0) {
      texto += ` de $ ${formatearNumeroLocal(pagado)}`;
      if (sobrante > 0.004) {
        texto += ` · <span class="text-success">$ ${formatearNumeroLocal(sobrante)} quedan a cuenta</span>`;
      } else if (sobrante < -0.004) {
        texto += ` · <span class="text-danger">te pasaste por $ ${formatearNumeroLocal(-sobrante)}</span>`;
      }
    }
    resumen.innerHTML = texto;
  };

  const dibujarPendientes = (datos) => {
    pendientes = datos.pedidos;
    if (!pendientes.length) {
      lista.innerHTML =
        '<p class="text-muted small mb-0">Este proveedor no tiene pedidos con saldo. ' +
        "El pago se va a registrar como plata a cuenta.</p>";
      resumen.innerHTML = "";
      return;
    }
    lista.innerHTML = pendientes
      .map(
        (p) => `
      <div class="imputacion-fila">
        <div class="descripcion">
          <strong>#${p.id}</strong> ${p.descripcion}<br>
          <small>${p.fecha} · monto $ ${formatearNumeroLocal(p.monto)} ·
                 saldo $ ${formatearNumeroLocal(p.saldo)}</small>
        </div>
        <input type="text" class="form-control form-control-sm monto campo-imputacion"
               id="imputacion_${p.id}" name="imputacion_${p.id}"
               inputmode="decimal" placeholder="0,00" data-saldo="${p.saldo}">
      </div>`
      )
      .join("");

    lista.querySelectorAll(".campo-imputacion").forEach((campo) => {
      campo.addEventListener("input", dibujarResumen);
    });
    dibujarResumen();
  };

  const cargarPendientes = () => {
    const id = selectProveedor.value;
    if (!id) {
      lista.innerHTML =
        '<p class="text-muted small mb-0">Elegí un proveedor para ver sus pedidos con saldo.</p>';
      resumen.innerHTML = "";
      pendientes = [];
      return;
    }
    lista.innerHTML = '<p class="text-muted small mb-0">Cargando pedidos…</p>';
    fetch(`/tercerizados/pendientes/${id}`)
      .then((res) => {
        if (!res.ok) throw new Error("No se pudieron obtener los pedidos");
        return res.json();
      })
      .then(dibujarPendientes)
      .catch((error) => {
        console.error("Error al cargar pendientes:", error);
        lista.innerHTML =
          '<p class="text-danger small mb-0">No se pudieron cargar los pedidos del proveedor.</p>';
      });
  };

  selectProveedor.addEventListener("change", cargarPendientes);
  montoPago.addEventListener("input", dibujarResumen);

  // Reparte el monto pagado del pedido más viejo al más nuevo (los pendientes
  // ya vienen ordenados así desde el backend).
  botonAuto.addEventListener("click", () => {
    let restante = parsearNumeroLocal(montoPago.value);
    if (restante <= 0) {
      alert("Primero ingresá el monto pagado.");
      return;
    }
    pendientes.forEach((pedido) => {
      const campo = document.getElementById(`imputacion_${pedido.id}`);
      if (!campo) return;
      const aplicar = Math.min(restante, pedido.saldo);
      campo.value = aplicar > 0 ? formatearNumeroLocal(aplicar) : "";
      restante -= aplicar > 0 ? aplicar : 0;
    });
    dibujarResumen();
  });

  modal.addEventListener("show.bs.modal", () => {
    // Si la vista está filtrada por un proveedor, se arranca con ese.
    const filtro = document.getElementById("proveedorFiltro");
    if (filtro && filtro.value && !selectProveedor.value) {
      selectProveedor.value = filtro.value;
    }
    cargarPendientes();
  });
});

/* ------------------------------------------------ Confirmaciones de borrado */

document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("borrarTercerizadoModal");
  if (!modal) return;
  const form = document.getElementById("formBorrarTercerizado");
  const mensaje = document.getElementById("borrarTercerizadoMensaje");
  const bootstrapModal = new bootstrap.Modal(modal);

  document.querySelectorAll(".btn-borrar-tercerizado").forEach((boton) => {
    boton.addEventListener("click", () => {
      form.action = `/tercerizados/borrar/${boton.dataset.id}`;
      mensaje.innerHTML =
        `Vas a eliminar el pedido tercerizado <strong>#${boton.dataset.id}</strong>: ` +
        `"${boton.dataset.descripcion}" de ${boton.dataset.proveedor} por ` +
        `${boton.dataset.monto}.<br><br>Si tiene pagos imputados no se va a borrar: ` +
        `en ese caso anulá el pago o marcalo como cancelado.`;
      bootstrapModal.show();
    });
  });
});

/* Anular un pago mueve plata: se confirma antes. */
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".form-anular-pago").forEach((form) => {
    form.addEventListener("submit", (evento) => {
      const boton = form.querySelector("button[type=submit]");
      const texto =
        `¿Anular el pago de ${boton.dataset.monto} a ${boton.dataset.proveedor}?\n\n` +
        "Los pedidos que tenía imputados vuelven a quedar con saldo.";
      if (!confirm(texto)) evento.preventDefault();
    });
  });
});
