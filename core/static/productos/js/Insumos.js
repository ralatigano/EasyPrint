let dataTable;
let dataTableIsInitilized=false;
// Lógica que inicializa la dataTable Insumos
const initDataTable = async () => {
    if (dataTableIsInitilized) {
        dataTable.destroy();
    }

    dataTable = $("#Insumos").DataTable({
      language: {
          lengthMenu: 'Mostrar _MENU_ insumos por página',
          zeroRecords: 'No hay insumos registrados',
          info: 'Mostrando de _START_ a _END_ de _TOTAL_ insumos',
          infoEmpty: 'No hay insumos',
          infoFiltered: '(filtrado de _MAX_ insumos totales)',
          search: 'Buscar:',
          loadingRecords: 'Cargando...',
          paginate: {
              first: 'Primero',
              last: 'Último',
              next: 'Siguiente',
              previous: 'Anterior'
          }
      },
      responsive: true,
      columnDefs: [
        { responsivePriority: 1, targets: 0 }, // Nombre
        { responsivePriority: 2, targets: 4 }, // Stock real
        { responsivePriority: 3, targets: 5 }, // Editar/Borrar
        { responsivePriority: 4, targets: 1 }, // PU
        { responsivePriority: 5, targets: 2 }, // Unidad medida
        { responsivePriority: 6, targets: 3 }, // Stock
      ],
      drawCallback: function(settings) {
        $('#Insumos tbody tr').each(function(index) {
          const stockText = $(this).find('td:eq(4)').text().trim();
          const stock = parseFloat(stockText.replace(',', '.'));


          if (!isNaN(stock)) {
            if (stock === 0) {

              $(this).find('td').each(function() {
                $(this).css({
                  'background-color': 'rgba(255, 0, 0, 0.15)',  // rojo suave
                });
              });

            } else if (stock <= 10) {

              $(this).find('td').each(function() {
                $(this).css({
                  'background-color': 'rgba(255, 255, 0, 0.25)',  // amarillo tenue
                });
              });
            }
          }
        });
      }
    });

    dataTableIsInitilized = true;
};

window.addEventListener("load", async() => {
    await initDataTable();
    document.getElementById("nav_item_insumos").style.fontWeight = "bold";
});

document.addEventListener("DOMContentLoaded", function () {
  const modalElement = document.getElementById("crearEditarInsumoModal");
  const modalTitle = document.getElementById("crearEditarInsumoModalLabel");
  const insumoModal = new bootstrap.Modal(modalElement);
  const infoModificacion = document.getElementById("info-modificacion");
  const idInput = document.getElementById("id_insumo");

  // Reset siempre al abrir el modal, antes de que lleguen los datos
  modalElement.addEventListener("show.bs.modal", function () {
    modalElement.querySelector("form").reset();
    document.getElementById("activo").checked = true;
    infoModificacion.textContent = "Última modificación: - por -";
  });

  document.querySelectorAll("[data-bs-toggle='modal'][data-bs-target='#crearEditarInsumoModal']").forEach(button => {
    button.addEventListener("click", function () {
      const id = button.getAttribute("data-id");

      if (id === "0") {
        // Modo creación — el reset ya lo maneja show.bs.modal
        modalTitle.textContent = "Nuevo insumo";
        idInput.value = "0";
      } else {
        // Modo edición
        fetch(`/productos/infoInsumo/${id}`)
          .then(res => {
            if (!res.ok) throw new Error("No se pudo obtener el insumo");
            return res.json();
          })
          .then(data => {
            idInput.value = data.id;
            document.getElementById("nombre_insumo").value = data.nombre || "";
            document.getElementById("unidad_medida").value = data.unidad_medida || "";
            document.getElementById("unidad_composicion").value = data.unidad_composicion || "";
            document.getElementById("factor_conversion").value = data.factor_conversion ?? 1;
            document.getElementById("stock").value = data.stock ?? "";
            document.getElementById("precio_unitario").value = "$ " + formatearNumeroLocal(data.precio_unitario ?? 0);
            document.getElementById("activo").checked = !!data.activo;
            modalTitle.textContent = `Editar insumo: ${data.nombre}`;

            if (data.ultima_modificacion && data.modificado_por) {
              const fecha = new Date(data.ultima_modificacion);
              const fechaFormateada = fecha.toLocaleString("es-AR", {
                day: "2-digit",
                month: "2-digit",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit"
              });
              infoModificacion.textContent = `Última modificación: ${fechaFormateada} por ${data.modificado_por}`;
            }
          })
          .catch(error => {
            console.error("Error al cargar insumo:", error);
            alert("Hubo un problema al cargar el insumo. Intentá nuevamente.");
          });
      }
    });
  });
});


// Lógica que evita la eliminación de objetos listados en la cotización por un click involuntario.
(function () {
    const btnEliminacion = document.querySelectorAll(".btnEliminacion");
    btnEliminacion.forEach(btn=>{
        btn.addEventListener("click", (e)=>{
            const confirmacion = confirm("¿Está segur@ de que desea continuar con el borrado? (Esto no se puede deshacer.)");
            if(!confirmacion){
                e.preventDefault();
            }    
        });
    });
})();

// Escucha la carga de un archivo en el botón de carga masiva de Insumos y dispara el submit para automatizar la carga.
document.getElementById('excelFileInput').addEventListener('change', function() {
  if (this.files.length > 0) {
    document.getElementById('formCargaAuto').submit();
  }
});
