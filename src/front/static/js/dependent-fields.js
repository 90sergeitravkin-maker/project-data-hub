document.addEventListener('DOMContentLoaded', function() {
    const dimDbSelect = document.querySelector('.dim-db-select');
    const schemaSelect = document.querySelector('.link-schema-select');
    const tableSelect = document.querySelector('.link-table-select');
    const columnSelect = document.querySelector('.link-column-select');

    function updateSelect(selectElement, url, selectedValue = '') {
        fetch(url)
            .then(response => response.json())
            .then(data => {
                selectElement.innerHTML = '<option value="">---------</option>';
                data.forEach(item => {
                    const option = document.createElement('option');
                    option.value = item.id;
                    option.textContent = item.name || item.columns || item.schema;
                    if (item.id == selectedValue) {
                        option.selected = true;
                    }
                    selectElement.appendChild(option);
                });
            });
    }

    // При изменении DimDB загружаем схемы
    dimDbSelect.addEventListener('change', function() {
        const dimDbId = this.value;
        if (dimDbId) {
            updateSelect(schemaSelect, `/api/schemas/?dim_db=${dimDbId}`);
            tableSelect.innerHTML = '<option value="">---------</option>';
            columnSelect.innerHTML = '<option value="">---------</option>';
        } else {
            schemaSelect.innerHTML = '<option value="">---------</option>';
            tableSelect.innerHTML = '<option value="">---------</option>';
            columnSelect.innerHTML = '<option value="">---------</option>';
        }
    });

    // При изменении схемы загружаем таблицы
    schemaSelect.addEventListener('change', function() {
        const schemaId = this.value;
        if (schemaId) {
            updateSelect(tableSelect, `/api/tables/?schema=${schemaId}`);
            columnSelect.innerHTML = '<option value="">---------</option>';
        } else {
            tableSelect.innerHTML = '<option value="">---------</option>';
            columnSelect.innerHTML = '<option value="">---------</option>';
        }
    });

    // При изменении таблицы загружаем столбцы
    tableSelect.addEventListener('change', function() {
        const tableId = this.value;
        if (tableId) {
            updateSelect(columnSelect, `/api/columns/?table=${tableId}`);
        } else {
            columnSelect.innerHTML = '<option value="">---------</option>';
        }
    });
});
