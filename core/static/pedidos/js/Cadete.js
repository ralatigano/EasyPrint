let dataTablePendientes;
let dataTablePagados;
let dataTableIsInitilized=false;
// Lógica que inicializa la dataTable Pedidos.
const initDataTablesViajes=async() => {
  if(dataTableIsInitilized){
      dataTablePendientes.destroy();
      dataTablePagados.destroy();
  }

  // 🔄 Resetear todos los checkboxes antes de inicializar
  document.querySelectorAll('.estado-checkbox').forEach(cb => {
    cb.checked = false;
  });
  const checkboxGlobal = document.getElementById('selectAllViajesPendientes');
  if (checkboxGlobal) {
    checkboxGlobal.checked = false;
  }
  const checkboxGlobalPagados = document.getElementById('selectAllViajesPagados');
  if (checkboxGlobalPagados) {
    checkboxGlobalPagados.checked = false;
  }
  const configComun = {
      responsive: true,
      columnDefs: [
        { responsivePriority: 1, targets: 0 }, // Fecha
        { responsivePriority: 4, targets: 1 }, // Origen/Destino
        { responsivePriority: 2, targets: 2 }, // Precio
        { responsivePriority: 3, targets: 3 }, // Estado
        { responsivePriority: 5, targets: 4 }, // Fecha de pago
      ],
      language: {
        lengthMenu: 'Mostrar _MENU_ viajes por página',
        zeroRecords: 'No hay viajes registrados',
        info: 'Mostrando de _START_ a _END_ de _TOTAL_ viajes',
        infoEmpty: 'No hay viajes',
        infoFiltered: '(filtrado de _MAX_ viajes totales)',
        search: 'Buscar:',
        loadingRecords: 'Cargando...',
        paginate: {
          first: 'Primero',
          last: 'Último',
          next: 'Siguiente',
          previous: 'Anterior'
        }
      }
  };
  dataTablePendientes=$("#ViajesPendientes").DataTable({...configComun});
  dataTablePagados=$("#ViajesPagados").DataTable({...configComun});
  vincularCheckboxesConSelectAll('ViajesCadete', 'selectAllViajesPendientes');
  vincularCheckboxesConSelectAll('ViajesCadetePagados', 'selectAllViajesPagados');
  dataTableIsInitilized=true;
};


window.addEventListener("load", async() => {
    await initDataTablesViajes();
    document.getElementById("nav_item_cadete").style.fontWeight = "bold";
});

/* Funcionalidad para evitar la eliminación de objetos listados en la vista por un click involuntario. */
(function () {
    const btnEliminacion = document.querySelectorAll(".btnEliminacion");
    btnEliminacion.forEach(btn=>{
        btn.addEventListener("click", (e)=>{
            const confirmacion = confirm("¿Está segur@ de que desea eliminar este elemento?");
            if(!confirmacion){
                e.preventDefault();
            }    
        });
    });
})();

document.addEventListener("DOMContentLoaded", function () {
  const modalElement = document.getElementById("crearViajeModal");
  const modalTitle = document.getElementById("crearViajeModalLabel");
  const form = document.getElementById("formViajeCadete");

  modalElement.addEventListener("show.bs.modal", function (event) {
    const button = event.relatedTarget;
    const viajeId = button.getAttribute("data-bs-whatever");

    if (!viajeId || viajeId === "0") {
      // Modo creación
      modalTitle.textContent = "Registrar nuevo viaje";
      form.reset();
      document.getElementById("viajeId").value = "0";
      document.getElementById("pagado").checked = false;
      document.getElementById("fecha_pago").value = "";
    } else {
      // Modo edición
      fetch(`/pedidos/infoViajeCadete/${viajeId}`)
        .then(res => {
          if (!res.ok) throw new Error("No se pudo obtener el viaje");
          return res.json();
        })
        .then(data => {
          modalTitle.textContent = `Editar viaje del ${data.fecha}`;
          document.getElementById("viajeId").value = data.id;
          document.getElementById("fecha").value = data.fecha;
          document.getElementById("origen").value = data.origen;
          document.getElementById("destino").value = data.destino;
          document.getElementById("precio").value = data.precio;
          document.getElementById("pagado").checked = data.pagado;
          document.getElementById("fecha_pago").value = data.fecha_pago ?? "";
        })
        .catch(error => {
          console.error("Error al cargar viaje:", error);
          modalTitle.textContent = "Error al cargar viaje";
        });
    }
  });
});

document.addEventListener("DOMContentLoaded", function () {
  const marcarPagadosBtn = document.getElementById("btnMarcarPagados");
  const marcarNoPagadosBtn = document.getElementById("btnMarcarNoPagados");

  const getCheckboxIds = (tablaId) => {
    const checkboxes = document.querySelectorAll(`#${tablaId} .estado-checkbox:checked`);
    return Array.from(checkboxes).map(cb => cb.dataset.id);
  };

  const enviarActualizacionEstado = (ids, nuevoEstado) => {
  if (ids.length === 0) {
    alert("No seleccionaste ningún viaje.");
    return;
  }

  fetch("/pedidos/actualizarEstadoViajes", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCSRFToken()
    },
    body: JSON.stringify({
      ids: ids,
      pagado: nuevoEstado
    })
  })
  .then(res => {
    if (!res.ok) throw new Error("Error al actualizar viajes");
    return res.json();
  })
  .then(data => {
    if (data.redirect_url) {
      window.location.href = data.redirect_url;
    } else {
      alert("Actualización realizada, pero sin redirección.");
    }
  })
  .catch(err => {
    console.error("Error:", err);
    alert("Hubo un problema al actualizar los viajes.");
  });
};


  const getCSRFToken = () => {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
  };

  marcarPagadosBtn.addEventListener("click", () => {
    const ids = getCheckboxIds("ViajesCadete");
    enviarActualizacionEstado(ids, true);
  });

  marcarNoPagadosBtn.addEventListener("click", () => {
    const ids = getCheckboxIds("ViajesCadetePagados");
    enviarActualizacionEstado(ids, false);
  });
});


function vincularCheckboxesConSelectAll(idTabla, idCheckboxGlobal) {
  const tabla = document.getElementById(idTabla);
  const checkboxGlobal = document.getElementById(idCheckboxGlobal);

  if (!tabla || !checkboxGlobal) return;

  const checkboxes = tabla.querySelectorAll('.estado-checkbox');

  // Reset inicial
  checkboxGlobal.checked = false;
  checkboxes.forEach(cb => cb.checked = false);

  // Vinculación: marcar todos
  checkboxGlobal.addEventListener('change', function () {
    checkboxes.forEach(cb => {
      cb.checked = checkboxGlobal.checked;
    });
  });

  // Vinculación: sincronizar estado del global
  checkboxes.forEach(cb => {
    cb.addEventListener('change', function () {
      const allChecked = Array.from(checkboxes).every(c => c.checked);
      checkboxGlobal.checked = allChecked;
    });
  });
}

