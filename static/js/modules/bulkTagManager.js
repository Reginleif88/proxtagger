/**
 * Bulk Tag Management module
 * Handles adding, removing, and applying tags to multiple VMs/containers at once
 * 
 * @file modules/bulkTagManager.js
 */

import { showToast } from './utils.js';
import { selectedVMIDs, getDataTableInstance } from './dataTables.js';

// Global variables for tracking bulk tag management elements
let selectedTagsContainer;

/**
 * Initialize the bulk tag management functionality
 * Handles adding, removing, and applying tags to multiple VMs/containers at once
 */
export function initBulkTagManagement() {
    // Get references to DOM elements
    const bulkPanel = document.getElementById('bulkTagPanel');
    const toggleBtn = document.getElementById('toggleBulkPanel');
    const addNewTagBtn = document.getElementById('addNewTagBtn');
    const newTagInput = document.getElementById('newTagInput');
    const clearSelectedVMsBtn = document.getElementById('clearSelectedVMsBtn');
    
    // Set the global selectedTagsContainer variable
    selectedTagsContainer = document.querySelector('.selected-tags-container');
    const bulkApplyBtn = document.getElementById('bulkApplyBtn');
    const selectAllVMs = document.getElementById('selectAllVMs');
    const vmCheckboxes = document.querySelectorAll('.vm-checkbox');
    const tagOperation = document.getElementsByName('tagOperation');
    const availableTags = document.getElementById('availableTags');
    
    // Ensure available tags are properly split (in case they contain semicolons)
    ensureProperTagSplitting();
    
    // Handle Clear Selected VMs button click
    if (clearSelectedVMsBtn) {
        clearSelectedVMsBtn.addEventListener('click', () => {
            clearSelectedVMs();
        });
    }
    
    // Handle 'Add Tag' button click
    if (addNewTagBtn) {
        addNewTagBtn.addEventListener('click', () => {
            // Only allow adding tags in 'Add' mode
            if (!document.getElementById('tagAdd').checked) {
                showToast('⚠️ New tags can only be added in "Add Tags" mode', 'warning');
                return;
            }
            
            const newTag = newTagInput.value.trim();
            
            if (!newTag) {
                showToast('⚠️ Tag cannot be empty', 'warning');
                return;
            }
            
            // Check if already selected
            const existingTags = getSelectedTags();
            if (existingTags.includes(newTag)) {
                showToast('⚠️ Tag already selected', 'warning');
                return;
            }
            
            // Add to selected tags
            addSelectedTag(newTag);
            
            // Clear input
            newTagInput.value = '';
            newTagInput.focus();
        });
    }
    
    // Toggle 'New Tag' input field based on operation mode
    document.getElementById('tagAdd')?.addEventListener('change', () => {
        // In Add mode, enable the input and button
        const newTagInput = document.getElementById('newTagInput');
        const addNewTagBtn = document.getElementById('addNewTagBtn');
        const newTagInputGroup = document.getElementById('newTagInputGroup');
        
        if (newTagInput && addNewTagBtn && newTagInputGroup) {
            newTagInput.disabled = false;
            addNewTagBtn.disabled = false;
            newTagInputGroup.classList.remove('opacity-50');
        }
    });
    
    document.getElementById('tagRemove')?.addEventListener('change', () => {
        // In Remove mode, disable the input and button
        const newTagInput = document.getElementById('newTagInput');
        const addNewTagBtn = document.getElementById('addNewTagBtn');
        const newTagInputGroup = document.getElementById('newTagInputGroup');
        
        if (newTagInput && addNewTagBtn && newTagInputGroup) {
            newTagInput.disabled = true;
            addNewTagBtn.disabled = true;
            newTagInputGroup.classList.add('opacity-50');
        }
    });
    
    // Handle new tag input - add tag on Enter key
    if (newTagInput) {
        newTagInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                
                // Only allow adding tags in 'Add' mode
                if (!document.getElementById('tagAdd').checked) {
                    showToast('⚠️ New tags can only be added in "Add Tags" mode', 'warning');
                    return;
                }
                
                const newTag = newTagInput.value.trim();
                
                if (!newTag) {
                    showToast('⚠️ Tag cannot be empty', 'warning');
                    return;
                }
                
                // Check if already selected
                const existingTags = getSelectedTags();
                if (existingTags.includes(newTag)) {
                    showToast('⚠️ Tag already selected', 'warning');
                    return;
                }
                
                // Add to selected tags
                addSelectedTag(newTag);
                
                // Clear input
                newTagInput.value = '';
            }
        });
    }
    
    // Handle tag checkboxes
    document.querySelectorAll('.tag-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', () => {
            const tag = checkbox.value;
            if (checkbox.checked) {
                addSelectedTag(tag);
            } else {
                removeSelectedTag(tag);
            }
        });
    });
    
    // Apply button event handler
    if (bulkApplyBtn) {
        bulkApplyBtn.addEventListener('click', () => {
            // Get the selected operation
            const operation = document.querySelector('input[name="tagOperation"]:checked').value;
            
            // Get selected tags
            const selectedTags = getSelectedTags();
            
            if (selectedTags.length === 0) {
                showToast('⚠️ Please select at least one tag', 'warning');
                return;
            }
            
            // Get selected VMs using our tracking Set - ensure we get all VMs across all pages
            const selectedVMs = [];
            const vmCheckboxes = document.querySelectorAll('.vm-checkbox');
            
            // Create a map of all VM data for quick lookup
            const vmDataMap = new Map();
            vmCheckboxes.forEach(cb => {
                const vmid = cb.dataset.vmid;
                vmDataMap.set(vmid, {
                    id: parseInt(vmid),
                    vmid: parseInt(vmid), // Add this for server compatibility
                    node: cb.dataset.node,
                    type: cb.dataset.type,
                    tags: cb.dataset.tags || '',
                    name: cb.dataset.name
                });
            });
            
            // Use the selectedVMIDs Set to get all selected VMs across all pages
            selectedVMIDs.forEach(vmid => {
                // If we have the data for this VM, use it
                if (vmDataMap.has(vmid)) {
                    selectedVMs.push(vmDataMap.get(vmid));
                } else {
                    // For VMs not on the current page, we need to fetch their info
                    // from the data-* attributes we stored when populating the table
                    // For now, include with minimal data - the server will look up the rest
                    selectedVMs.push({
                        id: parseInt(vmid),
                        vmid: parseInt(vmid), // Add this for server compatibility
                        // These fields will be looked up server-side
                        node: null,
                        type: null, 
                        tags: '',
                        name: `VM ${vmid}`
                    });
                }
            });
            
            if (selectedVMs.length === 0) {
                showToast('⚠️ Please select at least one VM or container', 'warning');
                return;
            }
            
            // Confirm the operation
            const tagWord = selectedTags.length === 1 ? 'tag' : 'tags';
            const vmWord = selectedVMs.length === 1 ? 'VM/container' : 'VMs/containers';
            const confirmMessage = `Are you sure you want to ${operation === 'add' ? 'add' : 'remove'} ${selectedTags.length} ${tagWord} to/from ${selectedVMs.length} ${vmWord}?`;
            
            if (confirm(confirmMessage)) {
                // Show loading message
                showToast('🔄 Applying tag changes...', 'info');
                
                // Make API request
                fetch('/api/bulk-tag-update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        operation: operation,
                        tags: selectedTags,
                        vms: selectedVMs
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showToast(`✅ Successfully updated tags for ${data.updated} ${data.updated === 1 ? 'VM/container' : 'VMs/containers'}`, 'success');
                        
                        // If there were any failures, show details
                        if (data.failed > 0) {
                            let failureMessage = `⚠️ Failed to update ${data.failed} ${data.failed === 1 ? 'VM/container' : 'VMs/containers'}`;
                            showToast(failureMessage, 'warning');
                        }
                        
                        // Reload the page after a short delay
                        setTimeout(() => location.reload(), 1500);
                    } else {
                        showToast(`⚠️ Error: ${data.error || 'Unknown error occurred'}`, 'danger');
                    }
                })
                .catch(error => {
                    showToast(`⚠️ Error: ${error.message}`, 'danger');
                });
            }
        });
    }
}

/**
 * Clear all selected VMs/Containers
 */
export function clearSelectedVMs() {
    // Check if there are any selected VMs
    if (selectedVMIDs.size === 0) {
        showToast('ℹ️ No VMs are currently selected', 'info');
        return;
    }
    
    // Get the number of selected VMs for the notification
    const count = selectedVMIDs.size;
    
    // Clear the Set of selected VM IDs
    selectedVMIDs.clear();
    
    // Uncheck all VM checkboxes
    document.querySelectorAll('.vm-checkbox').forEach(checkbox => {
        checkbox.checked = false;
    });
    
    // Uncheck the "Select All" checkbox and remove indeterminate state
    const selectAllVMs = document.getElementById('selectAllVMs');
    if (selectAllVMs) {
        selectAllVMs.checked = false;
        selectAllVMs.indeterminate = false;
    }
    
    // Update the selected VMs list display
    updateSelectedVMsList();
    
    // Show a success message
    showToast(`✅ Cleared ${count} selected VM${count === 1 ? '' : 's'}`, 'success');
    
    // Trigger a custom event that other modules can listen for
    document.dispatchEvent(new CustomEvent('vm-selection-changed'));
}

/**
 * Get all currently selected tags from the UI
 * 
 * @returns {string[]} Array of selected tag names
 */
function getSelectedTags() {
    if (!selectedTagsContainer) return [];
    
    return Array.from(selectedTagsContainer.querySelectorAll('.selected-tag')).map(tag => 
        tag.dataset.tag
    );
}

/**
 * Add a tag to the selected tags UI with visual representation
 * 
 * @param {string} tag - The tag name to add
 */
function addSelectedTag(tag) {
    if (!tag || !selectedTagsContainer || getSelectedTags().includes(tag)) return;
    
    // Create tag pill
    const tagElement = document.createElement('span');
    tagElement.className = 'badge bg-primary d-flex align-items-center selected-tag';
    tagElement.dataset.tag = tag;
    tagElement.innerHTML = `
        ${tag}
        <button type="button" class="btn-close btn-close-white ms-2" aria-label="Remove"></button>
    `;
    
    // Add to container
    selectedTagsContainer.appendChild(tagElement);
    
    // Check the corresponding checkbox if exists
    const checkbox = document.getElementById(`tag-${tag}`);
    if (checkbox) checkbox.checked = true;
    
    // Handle remove button
    tagElement.querySelector('.btn-close').addEventListener('click', () => {
        removeSelectedTag(tag);
    });
}

/**
 * Remove a tag from the selected tags UI
 * 
 * @param {string} tag - The tag name to remove
 */
function removeSelectedTag(tag) {
    if (!selectedTagsContainer) return;
    
    // Remove from selected tags
    const tagElements = selectedTagsContainer.querySelectorAll('.selected-tag');
    tagElements.forEach(element => {
        if (element.dataset.tag === tag) {
            element.remove();
        }
    });
    
    // Uncheck the corresponding checkbox if exists
    const checkbox = document.getElementById(`tag-${tag}`);
    if (checkbox) checkbox.checked = false;
}

/**
 * Ensure tags with semicolons are properly split into separate tags
 * This fixes issues where VM tags might contain semicolons themselves
 */
function ensureProperTagSplitting() {
    // Get all VM checkboxes to check for semicolon-separated tags
    document.querySelectorAll('.vm-checkbox').forEach(checkbox => {
        const tags = checkbox.dataset.tags;
        if (tags && tags.includes(';')) {
            // If we find semicolons, we need to ensure those tags are in the available tags section
            const tagArray = tags.split(';').filter(tag => tag.trim()).map(tag => tag.trim());
            
            // For each tag from the split, make sure it exists in the available tags
            tagArray.forEach(tag => {
                if (!document.getElementById(`tag-${tag}`)) {
                    // If the tag doesn't exist in available tags, we need to add it
                    addToAvailableTags(tag);
                }
            });
        }
    });
}

/**
 * Add a new tag to the Available Tags section for bulk operations
 * 
 * @param {string} tag - The tag to add to the available tags list
 */
export function addToAvailableTags(tag) {
    // Make sure the tag is valid and not already in available tags
    if (!tag || !tag.trim() || document.getElementById(`tag-${tag}`)) {
        return;
    }
    
    const tagsContainer = document.getElementById('availableTags');
    if (!tagsContainer) return;
    
    const tagElement = document.createElement('div');
    tagElement.className = 'form-check form-check-inline';
    tagElement.innerHTML = `
        <input class="form-check-input tag-checkbox" type="checkbox" id="tag-${tag}" value="${tag}">
        <label class="form-check-label" for="tag-${tag}">${tag}</label>
    `;
    tagsContainer.appendChild(tagElement);
    
    // Add event listener to the new checkbox
    const newCheckbox = tagElement.querySelector('.tag-checkbox');
    newCheckbox.addEventListener('change', () => {
        if (newCheckbox.checked && selectedTagsContainer) {
            // Create tag pill
            const tagElement = document.createElement('span');
            tagElement.className = 'badge bg-primary d-flex align-items-center selected-tag';
            tagElement.dataset.tag = tag;
            tagElement.innerHTML = `
                ${tag}
                <button type="button" class="btn-close btn-close-white ms-2" aria-label="Remove"></button>
            `;
            
            // Add to container
            selectedTagsContainer.appendChild(tagElement);
            
            // Handle remove button
            tagElement.querySelector('.btn-close').addEventListener('click', () => {
                // Remove this tag element
                tagElement.remove();
                // Uncheck the corresponding checkbox
                newCheckbox.checked = false;
            });
        } else if (!newCheckbox.checked && selectedTagsContainer) {
            // Remove from selected tags if unchecked
            const tagElements = selectedTagsContainer.querySelectorAll('.selected-tag');
            tagElements.forEach(element => {
                if (element.dataset.tag === tag) {
                    element.remove();
                }
            });
        }
    });
}

/**
 * Update the selected VMs list display with selected VM names and IDs
 */
export function updateSelectedVMsList() {
    const selectedVMsList = document.getElementById('selectedVMsList');
    if (!selectedVMsList) return;
    
    // If we have no selected VMs, show a message
    if (selectedVMIDs.size === 0) {
        selectedVMsList.innerHTML = '<span class="text-muted small fst-italic">No VMs selected</span>';
        return;
    }
    
    // Clear the container
    selectedVMsList.innerHTML = '';
    
    // Create a map to store all VM data
    const vmData = new Map();
    
    // Collect data from all VM checkboxes
    document.querySelectorAll('.vm-checkbox').forEach(checkbox => {
        const vmid = checkbox.dataset.vmid;
        vmData.set(vmid, {
            name: checkbox.dataset.name || 'Unnamed',
            vmid: vmid
        });
    });
    
    // Now use our stored VM IDs to display badges, whether the VM is on the current page or not
    const vmsToShow = [];
    selectedVMIDs.forEach(vmid => {
        // If we have data for this VM, add it to the list
        if (vmData.has(vmid)) {
            vmsToShow.push(vmData.get(vmid));
        } else {
            // If we don't have the data (rare case), still show something
            vmsToShow.push({
                name: `VM ${vmid}`,
                vmid: vmid
            });
        }
    });
    
    // Sort VMs by ID for consistent display
    vmsToShow.sort((a, b) => parseInt(a.vmid) - parseInt(b.vmid));
    
    // If we have too many VMs, only show a subset with a counter
    const maxToShow = 15; // Maximum number of VMs to display individually
    const totalVMs = vmsToShow.length;
    
    if (totalVMs > maxToShow) {
        // Show a subset of VMs
        for (let i = 0; i < maxToShow; i++) {
            const vm = vmsToShow[i];
            const badge = document.createElement('span');
            badge.className = 'badge bg-secondary d-flex align-items-center me-1 mb-1';
            badge.innerHTML = `${vm.name} (${vm.vmid})`;
            selectedVMsList.appendChild(badge);
        }
        
        // Add a count badge for the remaining VMs
        const remaining = totalVMs - maxToShow;
        const countBadge = document.createElement('span');
        countBadge.className = 'badge bg-info d-flex align-items-center me-1 mb-1';
        countBadge.innerHTML = `+ ${remaining} more VMs selected`;
        selectedVMsList.appendChild(countBadge);
        
        // Also add a total counter
        const totalBadge = document.createElement('div');
        totalBadge.className = 'mt-1 small text-muted';
        totalBadge.innerHTML = `<strong>${totalVMs}</strong> VMs selected total`;
        selectedVMsList.appendChild(totalBadge);
    } else {
        // Display all selected VMs when fewer than maxToShow
        vmsToShow.forEach(vm => {
            const badge = document.createElement('span');
            badge.className = 'badge bg-secondary d-flex align-items-center me-1 mb-1';
            badge.innerHTML = `${vm.name} (${vm.vmid})`;
            selectedVMsList.appendChild(badge);
        });
    }
}
