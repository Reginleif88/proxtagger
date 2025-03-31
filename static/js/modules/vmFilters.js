/**
 * VM Filters module
 * Handles filtering VMs by various criteria including host, VMID range, and name pattern
 * 
 * @file modules/vmFilters.js
 */

import { showToast } from './utils.js';
import { selectedVMIDs, getDataTableInstance } from './dataTables.js';
import { updateSelectedVMsList } from './bulkTagManager.js';

// Module-scoped filter state
const filterState = {
    host: '',
    vmidStart: null,
    vmidEnd: null,
    namePattern: ''
};

/**
 * Initialize VM filtering functionality
 */
export function initVMFilters() {
    // Get references to filter elements
    const applyFiltersBtn = document.getElementById('applyFiltersBtn');
    const resetFiltersBtn = document.getElementById('resetFiltersBtn');
    const selectAllFilteredBtn = document.getElementById('selectAllFilteredBtn');
    
    // Apply filters button event
    if (applyFiltersBtn) {
        // Remove any existing event listeners
        const newApplyBtn = applyFiltersBtn.cloneNode(true);
        applyFiltersBtn.parentNode.replaceChild(newApplyBtn, applyFiltersBtn);
        
        newApplyBtn.addEventListener('click', (e) => {
            e.preventDefault();
            applyFilters();
        });
    }
    
    // Reset filters button event
    if (resetFiltersBtn) {
        // Remove any existing event listeners
        const newResetBtn = resetFiltersBtn.cloneNode(true);
        resetFiltersBtn.parentNode.replaceChild(newResetBtn, resetFiltersBtn);
        
        newResetBtn.addEventListener('click', (e) => {
            e.preventDefault();
            resetFilters();
        });
    }
    
    // Select All Filtered button event
    if (selectAllFilteredBtn) {
        // Remove any existing event listeners
        const newSelectAllBtn = selectAllFilteredBtn.cloneNode(true);
        selectAllFilteredBtn.parentNode.replaceChild(newSelectAllBtn, selectAllFilteredBtn);
        
        newSelectAllBtn.addEventListener('click', (e) => {
            e.preventDefault();
            selectAllFilteredVMs();
        });
    }

    // Register the custom DataTables filter function
    setupDataTablesCustomFilter();
}

/**
 * Set up the custom DataTables filter function
 * This is the core function that integrates with DataTables API to filter rows
 */
function setupDataTablesCustomFilter() {
    // Remove any existing custom filters first (to avoid duplicates)
    while ($.fn.dataTable.ext.search.length > 0) {
        $.fn.dataTable.ext.search.pop();
    }

    // Add the new custom filter
    $.fn.dataTable.ext.search.push(function(settings, data, dataIndex, rowData, counter) {
        // If no filters are active, show all rows
        if (!filterState.host && 
            filterState.vmidStart === null && 
            filterState.vmidEnd === null && 
            !filterState.namePattern) {
            return true;
        }

        // Get the row's DOM element to extract data from data attributes
        const dataTable = $(settings.nTable).DataTable();
        const rowNode = dataTable.row(dataIndex).node();
        
        if (!rowNode) return true; // Safety check
        
        const checkbox = rowNode.querySelector('.vm-checkbox');
        if (!checkbox) return true; // Safety check
        
        const vmid = parseInt(checkbox.dataset.vmid, 10);
        const node = checkbox.dataset.node || '';
        const name = (checkbox.dataset.name || '').toLowerCase();
        
        // Apply host filter
        const hostMatch = !filterState.host || node === filterState.host;
        
        // Apply VMID range filter
        let vmidMatch = true;
        if (filterState.vmidStart !== null && filterState.vmidEnd !== null) {
            // Full range
            vmidMatch = vmid >= filterState.vmidStart && vmid <= filterState.vmidEnd;
        } else if (filterState.vmidStart !== null) {
            // Only start specified
            vmidMatch = vmid >= filterState.vmidStart;
        } else if (filterState.vmidEnd !== null) {
            // Only end specified
            vmidMatch = vmid <= filterState.vmidEnd;
        }
        
        // Apply name pattern filter
        const nameMatch = !filterState.namePattern || name.includes(filterState.namePattern);
        
        // Return true if all filters match (AND condition)
        return hostMatch && vmidMatch && nameMatch;
    });
}

/**
 * Validate and normalize filter input values
 * 
 * @returns {boolean} - True if validation passes, false otherwise
 */
function validateFilters() {
    // Get filter values
    const host = document.getElementById('hostFilter')?.value || '';
    const vmidStart = document.getElementById('vmidRangeStart')?.value || '';
    const vmidEnd = document.getElementById('vmidRangeEnd')?.value || '';
    const namePattern = document.getElementById('namePattern')?.value || '';
    
    // Validate VMID range if provided
    if (vmidStart && vmidEnd) {
        const start = parseInt(vmidStart, 10);
        const end = parseInt(vmidEnd, 10);
        
        if (isNaN(start) || isNaN(end)) {
            showToast('⚠️ VMID range must be numeric values', 'warning');
            return false;
        }
        
        if (start > end) {
            showToast('⚠️ VMID start must be less than or equal to end', 'warning');
            return false;
        }
    } else if (vmidStart && !vmidEnd) {
        const start = parseInt(vmidStart, 10);
        if (isNaN(start)) {
            showToast('⚠️ VMID value must be numeric', 'warning');
            return false;
        }
    } else if (!vmidStart && vmidEnd) {
        const end = parseInt(vmidEnd, 10);
        if (isNaN(end)) {
            showToast('⚠️ VMID value must be numeric', 'warning');
            return false;
        }
    }
    
    // Update filter state
    filterState.host = host;
    filterState.vmidStart = vmidStart ? parseInt(vmidStart, 10) : null;
    filterState.vmidEnd = vmidEnd ? parseInt(vmidEnd, 10) : null;
    filterState.namePattern = namePattern.toLowerCase();
    
    return true;
}

/**
 * Apply all filters based on current filter inputs
 */
function applyFilters() {
    // Validate and update filter state
    if (!validateFilters()) {
        return;
    }
    
    // Get DataTable instance
    const dataTable = getDataTableInstance();
    if (!dataTable) {
        console.error("DataTable instance not available for filtering");
        showToast('⚠️ Error applying filters: Table not ready', 'warning');
        return;
    }
    
    // Apply filters by redrawing the table
    dataTable.draw();
    
    // Update filter status display
    updateFilterDisplay(dataTable);
}

/**
 * Update the filter display and status
 * 
 * @param {object} dataTable - The DataTable instance
 */
function updateFilterDisplay(dataTable) {
    const filterStatus = document.getElementById('filterStatus');
    if (!filterStatus) return;
    
    let filterMessage = '';
    const activeFilters = [];
    
    if (filterState.host) {
        activeFilters.push(`Host: ${filterState.host}`);
    }
    
    if (filterState.vmidStart !== null && filterState.vmidEnd !== null) {
        activeFilters.push(`VMID range: ${filterState.vmidStart}-${filterState.vmidEnd}`);
    } else if (filterState.vmidStart !== null) {
        activeFilters.push(`VMID from: ${filterState.vmidStart}`);
    } else if (filterState.vmidEnd !== null) {
        activeFilters.push(`VMID to: ${filterState.vmidEnd}`);
    }
    
    if (filterState.namePattern) {
        activeFilters.push(`Name pattern: "${filterState.namePattern}"`);
    }
    
    // Get visible count using DataTables API
    let visibleCount = 0;
    if (dataTable) {
        visibleCount = dataTable.rows({ search: 'applied' }).nodes().length;
    }
    
    if (activeFilters.length > 0) {
        filterMessage = `<i class="bi bi-funnel-fill"></i> Filters: ${activeFilters.join(', ')} `;
        filterMessage += `<span class="badge bg-primary ms-1">${visibleCount} VMs</span>`;
        filterStatus.innerHTML = filterMessage;
        showToast(`🔍 Filtered to ${visibleCount} VMs`, 'info');
    } else {
        filterStatus.innerHTML = '<i class="bi bi-info-circle"></i> No filters applied. Showing all VMs.';
        showToast('⚠️ No filters specified. Showing all VMs.', 'warning');
    }
    
    // Enable/disable the Select All Filtered button based on visible count
    const selectAllFilteredBtn = document.getElementById('selectAllFilteredBtn');
    if (selectAllFilteredBtn) {
        selectAllFilteredBtn.disabled = visibleCount === 0;
    }
}

/**
 * Reset all filter inputs and show all VMs
 */
function resetFilters() {
    // Reset filter input values
    const hostFilter = document.getElementById('hostFilter');
    const vmidRangeStart = document.getElementById('vmidRangeStart');
    const vmidRangeEnd = document.getElementById('vmidRangeEnd');
    const namePattern = document.getElementById('namePattern');
    
    if (hostFilter) hostFilter.value = '';
    if (vmidRangeStart) vmidRangeStart.value = '';
    if (vmidRangeEnd) vmidRangeEnd.value = '';
    if (namePattern) namePattern.value = '';
    
    // Reset filter state
    filterState.host = '';
    filterState.vmidStart = null;
    filterState.vmidEnd = null;
    filterState.namePattern = '';
    
    // Get DataTable instance
    const dataTable = getDataTableInstance();
    if (!dataTable) {
        console.error("DataTable instance not available for resetting filters");
        showToast('⚠️ Error resetting filters: Table not ready', 'warning');
        return;
    }
    
    // Redraw the table to apply the reset
    dataTable.draw();
    
    // Update filter status display
    const filterStatus = document.getElementById('filterStatus');
    if (filterStatus) {
        filterStatus.innerHTML = '<i class="bi bi-info-circle"></i> No filters applied yet';
    }
    
    // Enable the Select All Filtered button
    const selectAllFilteredBtn = document.getElementById('selectAllFilteredBtn');
    if (selectAllFilteredBtn) {
        selectAllFilteredBtn.disabled = false;
    }
    
    showToast('🔄 Filters reset. Showing all VMs.', 'info');
}

/**
 * Select all VMs that are currently visible (not filtered out)
 */
function selectAllFilteredVMs() {
    const dataTable = getDataTableInstance();
    if (!dataTable) {
        console.error("DataTable instance not available for selecting VMs");
        showToast('⚠️ Error selecting VMs: Table not ready', 'warning');
        return;
    }
    
    const rowsResult = dataTable.rows({ search: 'applied' });
    const visibleRows = rowsResult.nodes();
    const count = visibleRows.length;
    
    if (count === 0) {
        showToast('⚠️ No VMs match the current filters', 'warning');
        return;
    }
    
    // Check all visible checkboxes
    Array.from(visibleRows).forEach(row => {
        const checkbox = row.querySelector('.vm-checkbox');
        if (checkbox) {
            checkbox.checked = true;
            
            // Update tracking set
            const vmid = checkbox.dataset.vmid;
            selectedVMIDs.add(vmid);
        }
    });
    
    // Update Select All checkbox state
    const selectAllVMs = document.getElementById('selectAllVMs');
    if (selectAllVMs) {
        selectAllVMs.checked = true;
        selectAllVMs.indeterminate = false;
    }
    
    // Update the UI
    if (typeof updateSelectedVMsList === 'function') {
        updateSelectedVMsList();
    }
    
    showToast(`✅ Selected ${count} VMs matching the current filters`, 'success');
    
    // Trigger the event to update the UI
    document.dispatchEvent(new CustomEvent('vm-selection-changed'));
}

/**
 * Public method to get the current filter state
 * This allows other modules to access the filter state if needed
 * 
 * @returns {Object} Current filter state
 */
export function getFilterState() {
    return {...filterState}; // Return a copy to prevent direct mutation
}
