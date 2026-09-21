// Lógica que inicializa la dataTable Proveedores.
window.addEventListener("load", () => {
    $("#Proveedores").DataTable({
        responsive: true,
        language: {
            lengthMenu: 'Mostrar _MENU_ proveedores por página',
            zeroRecords: 'No hay proveedores registrados',
            info: 'Mostrando de _START_ a _END_ de _TOTAL_ proveedores',
            infoEmpty: 'No hay proveedores',
            infoFiltered: '(filtrado de _MAX_ proveedores totales)',
            search: 'Buscar:',
            loadingRecords: 'Cargando...',
            paginate: {
                first: 'Primero',
                last: 'Último',
                next: 'Siguiente',
                previous: 'Anterior'
            }
        },
        columnDefs: [
            { responsivePriority: 1, targets: 0 }, // Nombre
            { responsivePriority: 2, targets: 5 }, // Acciones
            { responsivePriority: 3, targets: 1 }, // Teléfono
        ],
    });
    document.getElementById("nav_item_insumos").style.fontWeight = "bold";
});

// Precarga el modal: vacío para uno nuevo, con los datos del proveedor al editar.
document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("editarProveedorModal");
    const titulo = document.getElementById("editarProveedorModalLabel");

    modal.addEventListener("show.bs.modal", (event) => {
        const id = event.relatedTarget?.getAttribute("data-id");
        modal.querySelector("form").reset();
        document.getElementById("proveedor_id").value = "";
        titulo.textContent = "Nuevo proveedor";
        if (!id) return;

        titulo.textContent = "Editar proveedor";
        fetch(`/productos/obtenerProveedor/${id}/`)
            .then(res => res.json())
            .then(data => {
                if (data.error) throw new Error(data.error);
                document.getElementById("proveedor_id").value = data.id;
                document.getElementById("proveedor_nombre").value = data.nombre;
                document.getElementById("proveedor_telefono").value = data.telefono;
                document.getElementById("proveedor_whatsapp").checked = data.telefono_whatsapp;
                document.getElementById("proveedor_email").value = data.email;
                document.getElementById("proveedor_web").value = data.web;
                titulo.textContent = `Editar proveedor: ${data.nombre}`;
            })
            .catch(err => {
                console.error("Error al cargar proveedor:", err);
                alert("Hubo un problema al cargar el proveedor. Intentá nuevamente.");
            });
    });
});
