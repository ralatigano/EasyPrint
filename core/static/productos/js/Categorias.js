let dataTable;
let dataTableIsInitilized=false;
// Lógica que inicializa la dataTable Productos.
const initDataTable=async() => {
    if(dataTableIsInitilized){
        dataTable.destroy();
    }
    dataTable=$("#Categorias").DataTable({
        language: {
            lengthMenu: 'Mostrar _MENU_ categorías por página',
            zeroRecords: 'No hay categorías registradas',
            info: 'Mostrando de _START_ a _END_ de _TOTAL_ categorías',
            infoEmpty: 'No hay categorías',
            InfoFiltered: '(filtrado de _MAX_ productos totales)',
            search: 'Buscar:',
            LoadingRecords: 'Cargando...',
            paginate: {
                first: 'Primero',
                last: 'Ultimo',
                next: 'Siguiente',
                previous: 'Anterior'
            }
        }
    });
    dataTableIsInitilized=true;
}

window.addEventListener("load", async() => {
    await initDataTable();
    document.getElementById("nav_item_productos").style.fontWeight = "bold";
});
// Lógica que evita la eliminación de categorías por un click involuntario.
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


document.addEventListener('DOMContentLoaded', function() {
    var editarCategoriaModal = document.getElementById('editarCategoriaModal');

    editarCategoriaModal.addEventListener('show.bs.modal', function(event) {
        var button = event.relatedTarget;
        var categoriaId = button.getAttribute('data-bs-whatever');
        
        var inputNombre = editarCategoriaModal.querySelector('#nombre');
        var inputId = editarCategoriaModal.querySelector('#id');
        var modalTitle = editarCategoriaModal.querySelector('.modal-title');

        if (categoriaId) {
            modalTitle.textContent = 'Editar Categoría';
            
            fetch(`/productos/obtenerCategoria/${categoriaId}/`)  
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error(data.error);
                    } else {
                        inputNombre.value = data.nombre;
                        inputId.value = data.id;  
                    }
                })
                .catch(error => console.error('Error:', error));
        } else {
            modalTitle.textContent = 'Nueva Categoría';
            inputNombre.value = '';
            inputId.value = '';
        }
    });
});