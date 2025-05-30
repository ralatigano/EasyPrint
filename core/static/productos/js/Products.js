
let dataTable;
let dataTableIsInitilized=false;
// Lógica que inicializa la dataTable Productos.
const initDataTable = async () => {
    if (dataTableIsInitilized) {
        dataTable.destroy();
    }

    dataTable = $("#Productos").DataTable({
        dom: "<'row'<'col-sm-6'<'#categoriaContainer'>><'col-sm-6'f>>" +
             "t" +
             "<'row'<'col-sm-6'i><'col-sm-6'p>>", // Define la ubicación de controles
        language: {
            lengthMenu: 'Mostrar _MENU_ productos por página',
            zeroRecords: 'No hay productos registrados',
            info: 'Mostrando de _START_ a _END_ de _TOTAL_ productos',
            infoEmpty: 'No hay productos',
            InfoFiltered: '(filtrado de _MAX_ productos totales)',
            search: 'Buscar:',
            LoadingRecords: 'Cargando...',
            paginate: {
                first: 'Primero',
                last: 'Último',
                next: 'Siguiente',
                previous: 'Anterior'
            }
        },
        initComplete: function () {
            var categoriaFilter = $('<label>Filtrar por categoría: </label><select id="categoriaFilter" class="form-select"><option value="">Todas</option></select>');

            // Agregar el `<select>` dentro del contenedor de DataTables
            $('#categoriaContainer').append(categoriaFilter);

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
        }
    });

    dataTableIsInitilized = true;
};

window.addEventListener("load", async() => {
    await initDataTable();
    document.getElementById("nav_item_productos").style.fontWeight = "bold";
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

