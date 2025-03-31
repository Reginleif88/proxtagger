/**
 * Advanced Filters module
 * Handles advanced filtering of VMs by various criteria
 * 
 * @file modules/advancedFilters.js
 */

import { showToast } from './utils.js';

/**
 * Initialize advanced filters functionality
 */
export function initializeAdvancedFilters() {
    // Node filter
    setupNodeFilter();
    
    // VMID range filter
    setupVmidRangeFilter();
    
    // Name pattern filter
    setupNamePatternFilter();
    
    // Type filter
    setupTypeFilter();
    
    // Clear all filters
    setupClearFiltersButton();
}

/**
 * Setup the node filter dropdown
 */
function setupNodeFilter() {
    const nodeFilter = document.getElementById('nodeFilter');
    if (!nodeFilter) return;
    
    nodeFilter.addEventListener('change', () => {
        const selectedNode = nodeFilter.value;
        
        // Use DataTables API for filtering
        if ($.fn.DataTable.isDataTable('#vmTable')) {
            const table = $('#vmTable').DataTable();
            
            // Clear existing column filter first
            table.column(3).search(''); // Clear node column filter
            
            // Apply filter if a specific node is selected
            if (selectedNode) {
                table.column(3).search(`^${escapeRegExp(selectedNode)}$`, true, false);
            }
            
            // Draw the table with the filter applied
            table.draw();
            
            showToast(`📊 Filtered to ${selectedNode || 'all'} node${selectedNode ? '' : 's'}`, 'info');
        }
    });
}

/**
 * Setup the VMID range filter
 */
function setupVmidRangeFilter() {
    const vmidStart = document.getElementById('vmidStart');
    const vmidEnd = document.getElementById('vmidEnd');
    const applyVmidRange = document.getElementById('applyVmidRange');
    
    if (!vmidStart || !vmidEnd || !applyVmidRange) return;
    
    applyVmidRange.addEventListener('click', () => {
        const start = parseInt(vmidStart.value) || 0;
        const end = parseInt(vmidEnd.value) || Number.MAX_SAFE_INTEGER;
        
        if (start > end) {
            showToast('⚠️ Invalid range: start should be less than or equal to end', 'warning');
            return;
        }
        
        // Use DataTables API for VMID range filtering
        if ($.fn.DataTable.isDataTable('#vmTable')) {
            const table = $('#vmTable').DataTable();
            
            // Custom search function for VMID range
            $.fn.dataTable.ext.search.push(
                function(settings, data, dataIndex) {
                    // Get VMID from the 3rd column (index 2)
                    const vmid = parseInt(data[2]) || 0;
                    return (vmid >= start && vmid <= end);
                }
            );
            
            // Redraw the table with the filter applied
            table.draw();
            
            // Remove our custom search function to avoid stacking filters
            $.fn.dataTable.ext.search.pop();
            
            showToast(`📊 Filtered to VMs with IDs between ${start} and ${end}`, 'info');
        }
    });
}

/**
 * Setup the name pattern filter
 */
function setupNamePatternFilter() {
    const namePattern = document.getElementById('namePattern');
    const useRegex = document.getElementById('useRegex');
    const applyNamePattern = document.getElementById('applyNamePattern');
    
    if (!namePattern || !useRegex || !applyNamePattern) return;
    
    applyNamePattern.addEventListener('click', () => {
        const pattern = namePattern.value.trim();
        const isRegex = useRegex.checked;
        
        if (!pattern) {
            showToast('⚠️ Please enter a name pattern', 'warning');
            return;
        }
        
        // Use DataTables API for name pattern filtering
        if ($.fn.DataTable.isDataTable('#vmTable')) {
            const table = $('#vmTable').DataTable();
            
            if (isRegex) {
                try {
                    // Test if the regex is valid
                    new RegExp(pattern);
                    
                    // Apply regex search to the name column (index 1)
                    table.column(1).search(pattern, true, false);
                } catch (e) {
                    showToast(`⚠️ Invalid regex pattern: ${e.message}`, 'danger');
                    return;
                }
            } else {
                // For wildcard patterns, convert to regex
                const wildcardToRegex = pattern
                    .replace(/\*/g, '.*')
                    .replace(/\?/g, '.');
                
                table.column(1).search(`^${wildcardToRegex}$`, true, false);
            }
            
            // Draw the table with the filter applied
            table.draw();
            
            showToast(`📊 Filtered to VMs with names matching the pattern`, 'info');
        }
    });
}

/**
 * Setup the type filter (VM vs LXC)
 */
function setupTypeFilter() {
    const typeRadios = document.querySelectorAll('input[name="typeFilter"]');
    
    typeRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            const selectedType = radio.value; // '' for All, 'qemu' for VMs, 'lxc' for LXC
            
            // Use DataTables API for filtering
            if ($.fn.DataTable.isDataTable('#vmTable')) {
                const table = $('#vmTable').DataTable();
                
                // Clear existing column filter first
                table.column(4).search(''); // Clear type column filter
                
                // Apply filter if a specific type is selected
                if (selectedType) {
                    table.column(4).search(`^${selectedType}$`, true, false);
                }
                
                // Draw the table with the filter applied
                table.draw();
                
                const typeLabel = selectedType === 'qemu' ? 'VMs' : 
                                  selectedType === 'lxc' ? 'LXC containers' : 
                                  'all types';
                                  
                showToast(`📊 Filtered to ${typeLabel}`, 'info');
            }
        });
    });
}

/**
 * Setup the clear all filters button
 */
function setupClearFiltersButton() {
    const clearAllFilters = document.getElementById('clearAllFilters');
    
    if (!clearAllFilters) return;
    
    clearAllFilters.addEventListener('click', () => {
        // Reset all filter inputs
        document.getElementById('vmidStart').value = '';
        document.getElementById('vmidEnd').value = '';
        document.getElementById('namePattern').value = '';
        document.getElementById('useRegex').checked = false;
        document.getElementById('nodeFilter').value = '';
        document.getElementById('typeAll').checked = true;
        
        // Clear all DataTables filters
        if ($.fn.DataTable.isDataTable('#vmTable')) {
            const table = $('#vmTable').DataTable();
            
            // Reset DataTables search
            table.search('').columns().search('').draw();
            
            showToast('🔄 All filters have been reset', 'success');
        }
    });
}

/**
 * Utility function to escape special characters in a string for use in regex
 * 
 * @param {string} string - The string to escape
 * @returns {string} The escaped string
 */
function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
