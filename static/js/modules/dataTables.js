/**
 * DataTables integration module
 * Handles initialization and configuration of DataTables for VM listing
 * 
 * @file modules/dataTables.js
 */

import { showToast } from './utils.js';
import { updateSelectedVMsList } from './bulkTagManager.js';
import { initVMFilters } from './vmFilters.js';

// Track selected VM IDs to persist across pagination
export const selectedVMIDs = new Set();

// Store the DataTable instance for global access
let dataTableInstance = null;

/**
 * Initializes DataTables with custom configuration
 */
export function initializeDataTables() {
    const vmTable = document.getElementById('vmTable');
    if (!vmTable) {
        console.error("VM table element (#vmTable) not found.");
        return;
    }
    
    try {
        // Initialize DataTable using jQuery
        const $table = $('#vmTable');
        dataTableInstance = $table.DataTable({
            // Basic configuration
            paging: true,
            search: {
                regex: true,
                smart: false // Optional: Disable smart filtering if you want only pure regex
            },            ordering: true,
            info: true,
            pageLength: 25,
            dom: '<"top"l>rt<"bottom"ip><"clear">',
            columnDefs: [
                { targets: [0, 5], orderable: false },
                { className: "align-middle", targets: "_all" }
            ],
            order: [[2, 'asc']],
            language: {
                search: "Search:",
                lengthMenu: "Show _MENU_ VMs",
                info: "Showing _START_ to _END_ of _TOTAL_ VMs",
                infoEmpty: "No VMs available",
                emptyTable: "No VMs found",
                paginate: {
                    first: "First",
                    last: "Last",
                    next: "›",
                    previous: "‹"
                }
            },
            drawCallback: function(settings) { // Added settings parameter
                console.log("drawCallback executed.");
                
                // Get DataTable instance CORRECTLY
                const dtInstance = getDataTableInstance(); // Use the helper function
                
                // Ensure dtInstance is valid before proceeding
                if (!dtInstance) {
                    console.error("drawCallback: Could not get DataTable instance.");
                    return;
                }
                
                // Restore checkbox states based on selectedVMIDs
                restoreCheckboxStates();
                
                // Update Select All checkbox state
                updateSelectAllCheckboxState(dtInstance); // Now dtInstance is the correct API object
                
                // Update selected VMs list
                if (typeof updateSelectedVMsList === 'function') {
                    updateSelectedVMsList();
                }
            },
            initComplete: function() {
                console.log("initComplete executed.");
                
                // 'this' refers to the DataTable API instance
                const dtInstance = this;
                
                // Set up custom search
                setupCustomSearch();
                
                // Set up VM selection handling
                setupVMSelectionHandling();
                
                // Initialize VM filters
                initVMFilters();
                
                console.log("DataTable initialization complete (initComplete finished)");
            }
        });
        
        console.log("DataTable initialization successful:", dataTableInstance);
    } catch (error) {
        console.error("Error initializing DataTable:", error);
    }
}

/**
 * Restore checkbox states based on selectedVMIDs
 * Called during drawCallback to update UI after pagination or other table redraws
 */
function restoreCheckboxStates() {
    document.querySelectorAll('.vm-checkbox').forEach(checkbox => {
        const vmid = checkbox.dataset.vmid;
        checkbox.checked = selectedVMIDs.has(vmid);
    });
}

/**
 * Sets up the custom search box to work with DataTables
 */
function setupCustomSearch() {
    const vmSearchInput = document.getElementById('vmSearchInput');
    const clearSearchBtn = document.getElementById('clearSearchBtn');
    
    // Bind our VM search to the DataTable search
    if (vmSearchInput) {
        vmSearchInput.addEventListener('input', () => {
            const dt = getDataTableInstance();
            if (dt) {
                dt.search(vmSearchInput.value).draw();
            } else {
                console.error("setupCustomSearch: DataTable instance not available for search");
            }
        });
    }
    
    // Clear search button
    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            if (vmSearchInput) {
                vmSearchInput.value = '';
                const dt = getDataTableInstance();
                if (dt) {
                    dt.search('').draw();
                } else {
                    console.error("setupCustomSearch: DataTable instance not available for clear search");
                }
            }
        });
    }
}

/**
 * Get the DataTable instance
 */
export function getDataTableInstance() {
    // Return our stored instance if it's already set and valid
    if (dataTableInstance) {
        return dataTableInstance;
    }

    // If not set (e.g., during initial drawCallback before main assignment),
    // try retrieving via jQuery directly. This is expected during startup.
    try {
        const $table = $('#vmTable');
        // Check if the table has been initialized as a DataTable
        if ($.fn.DataTable.isDataTable($table)) {
            // Retrieve the existing instance using the jQuery object
            const instance = $table.DataTable();
            // We don't strictly need to store it back to dataTableInstance here,
            // as the original assignment in initializeDataTables will eventually complete.
            return instance;
        } else {
             // This case implies the function is called before initializeDataTables even starts
             console.error("getDataTableInstance: Table has not been initialized as a DataTable yet.");
             return null;
        }
    } catch (error) {
        console.error("Error getting DataTable instance from jQuery:", error);
    }

    // If retrieval fails for any reason
    console.error("DataTable instance could not be retrieved.");
    return null;
}

/**
 * Set up VM selection handling (checkboxes and select all)
 */
function setupVMSelectionHandling() {
    // Set up the Select All checkbox
    setupSelectAllCheckbox();
    
    // Set up event delegation for VM checkboxes
    setupVMCheckboxEventDelegation();
}

/**
 * Set up the Select All checkbox functionality
 */
function setupSelectAllCheckbox() {
    const selectAllVMs = document.getElementById('selectAllVMs');
    if (!selectAllVMs) return;
    
    // Clear any existing listeners
    const newSelectAll = selectAllVMs.cloneNode(true);
    selectAllVMs.parentNode.replaceChild(newSelectAll, selectAllVMs);
    
    // Add event handler
    newSelectAll.addEventListener('change', () => {
        const dt = getDataTableInstance();
        if (dt) {
            selectAllVisibleVMs(dt, newSelectAll.checked);
        } else {
            console.error("Select All checkbox handler: Could not get DataTable instance.");
        }
    });
}

/**
 * Set up event delegation for VM checkboxes
 * This attaches a single listener to the DataTables wrapper that handles events from any checkbox,
 * including those created during pagination
 */
function setupVMCheckboxEventDelegation() {
    // Find the wrapper DIV created by DataTables around the table
    // Wait for a brief moment to ensure DataTables has created the wrapper
    setTimeout(() => {
        // Try to find the wrapper using standard DataTables naming
        let tableWrapper = document.querySelector('#vmTable_wrapper');
        
        // If not found, try alternative selectors
        if (!tableWrapper) {
            tableWrapper = document.querySelector('.dataTables_wrapper');
        }
        
        // If still not found, try to find parent of vmTable with dataTables class
        if (!tableWrapper) {
            const vmTable = document.getElementById('vmTable');
            if (vmTable && vmTable.parentElement) {
                tableWrapper = vmTable.closest('.dataTables_wrapper');
            }
        }
        
        if (!tableWrapper) {
            console.error("Could not find DataTable wrapper for event delegation");
            return;
        }
        
        console.log("Found DataTables wrapper for event delegation:", tableWrapper);
        
        // Use event delegation to handle all checkbox changes, including for elements
        // that get created during pagination
        tableWrapper.addEventListener('change', (event) => {
            // Only process events from vm-checkbox elements
            if (event.target && event.target.classList.contains('vm-checkbox')) {
                const checkbox = event.target;
                const vmid = checkbox.dataset.vmid;
                
                console.log("Checkbox change detected for VM:", vmid, "State:", checkbox.checked);
                
                // Update our tracking set based on current checkbox state
                if (checkbox.checked) {
                    selectedVMIDs.add(vmid);
                } else {
                    selectedVMIDs.delete(vmid);
                }
                
                // Update the Select All checkbox state
                const dt = getDataTableInstance();
                if (dt) {
                    updateSelectAllCheckboxState(dt);
                }
                
                // Update the selected VMs list
                if (typeof updateSelectedVMsList === 'function') {
                    updateSelectedVMsList();
                }
                
                // Trigger a custom event that other modules can listen for
                document.dispatchEvent(new CustomEvent('vm-selection-changed'));
            }
        });
        
        console.log("Event delegation setup complete for VM checkboxes");
    }, 100); // Brief timeout to ensure DataTables initialization is complete
    
    // Add a listener for the custom vm-selection-changed event
    document.addEventListener('vm-selection-changed', () => {
        if (typeof updateSelectedVMsList === 'function') {
            updateSelectedVMsList();
        }
        
        const dt = getDataTableInstance();
        if (dt) {
            updateSelectAllCheckboxState(dt);
        }
    });
}

/**
 * Select or deselect all currently visible VMs
 * @param {object} dt - The DataTable API instance
 * @param {boolean} select - Whether to select (true) or deselect (false) VMs
 */
function selectAllVisibleVMs(dt, select) {
    const rowsResult = dt.rows({ search: 'applied' });
    const visibleRows = rowsResult.nodes();
    
    // Update all checkboxes in visible rows
    Array.from(visibleRows).forEach(row => {
        const checkbox = row.querySelector('.vm-checkbox');
        if (checkbox) {
            checkbox.checked = select;
            
            // Update the tracking set
            const vmid = checkbox.dataset.vmid;
            if (select) {
                selectedVMIDs.add(vmid);
            } else {
                selectedVMIDs.delete(vmid);
            }
        }
    });
    
    // Trigger the event to update the UI
    document.dispatchEvent(new CustomEvent('vm-selection-changed'));
}

/**
 * Update the state of the Select All checkbox based on currently visible checkboxes
 * @param {object} dt - The DataTable API instance
 */
function updateSelectAllCheckboxState(dt) {
    const selectAllVMs = document.getElementById('selectAllVMs');
    if (!selectAllVMs) return;
    
    const rowsResult = dt.rows({ search: 'applied' });
    const visibleRows = rowsResult.nodes();
    
    if (visibleRows.length === 0) {
        // No visible checkboxes
        selectAllVMs.checked = false;
        selectAllVMs.indeterminate = false;
        return;
    }
    
    // Check if all visible checkboxes are checked
    const allChecked = Array.from(visibleRows).every(row => {
        const checkbox = row.querySelector('.vm-checkbox');
        return checkbox && checkbox.checked;
    });
    
    // Check if some visible checkboxes are checked
    const someChecked = Array.from(visibleRows).some(row => {
        const checkbox = row.querySelector('.vm-checkbox');
        return checkbox && checkbox.checked;
    });
    
    selectAllVMs.checked = allChecked;
    selectAllVMs.indeterminate = !allChecked && someChecked;
}
