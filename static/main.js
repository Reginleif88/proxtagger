/**
 * ProxTagger Main JavaScript
 * Handles the tag management user interface functionality including
 * individual VM tag editing, bulk tag management, and backup/restore operations.
 *
 * @file main.js
 * @version 1.0.0
 */

/**
 * Main initialization when DOM content is loaded
 * Sets up all event handlers and initializes tag management interfaces
 */
document.addEventListener("DOMContentLoaded", () => {
    // Initialize bulk tag management functionality
    initBulkTagManagement();
    
    // Initialize individual tag editor for each VM/container
    document.querySelectorAll(".tag-editor").forEach(container => {
        const vmid = container.dataset.vmid;
        const node = container.dataset.node;
        const type = container.dataset.type;
        const tagList = container.querySelector(".tag-list");
        const inputContainer = container.querySelector('.tag-input-container');
        const input = container.querySelector(".tag-input");
        const addBtn = container.querySelector(".add-tag-btn");

        /**
         * Get the current list of tags from the DOM elements
         * 
         * @returns {string[]} Array of tag names
         */
        function getCurrentTags() {
            return Array.from(tagList.querySelectorAll(".tag-chip span")).map(span =>
                span.textContent.trim()
            );
        }

        /**
         * Render tags as visual chips in the UI and optionally update the backend
         * 
         * @param {string[]} tags - Array of tag names to render
         * @param {boolean} skipBackendUpdate - If true, doesn't sync with server (default: false)
         */
        function renderTags(tags, skipBackendUpdate = false) {
            tagList.innerHTML = '';
            const updatedTags = tags.filter(t => t.trim());

            if (updatedTags.length === 0) {
                tagList.innerHTML = `<span class="text-muted small fst-italic">No tags</span>`;
                if (!skipBackendUpdate) {
                    updateBackend([]);
                }
                return;
            }

            updatedTags.forEach(tag => {
                const chip = document.createElement('span');
                chip.className = `badge bg-primary tag-chip me-1`;
                chip.title = `Tag: ${tag}`;

                const nameSpan = document.createElement('span');
                nameSpan.textContent = tag;
                chip.appendChild(nameSpan);

                const closeBtn = document.createElement('button');
                closeBtn.type = "button";
                closeBtn.className = "btn-close btn-close-white btn-sm ms-2 remove-tag";
                closeBtn.setAttribute("aria-label", "Remove");
                closeBtn.dataset.tag = tag;
                chip.appendChild(closeBtn);

                tagList.appendChild(chip);
            });

            if (!skipBackendUpdate) {
                updateBackend(updatedTags);
            }
        }

        /**
         * Send updated tags to the Proxmox backend via API
         * 
         * @param {string[]} tags - Array of tags to save to the server
         */
        function updateBackend(tags) {
            // Filter out any empty tags to avoid whitespace issues
            const filteredTags = tags.filter(tag => tag.trim());
            
            fetch(`/api/vm/${vmid}/tags`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ tags: filteredTags.join(";"), node, type })
            })
            .then(res => res.json())
            .then(data => {
                if (!data.success) {
                    showToast("⚠️ Error saving tags: " + (data.error || "Unknown error"), "danger");
                }
            })
            .catch(err => {
                showToast("⚠️ Network error: " + err.message, "danger");
            });
        }

        // Load initial tags from attribute
        const initialTags = (tagList.dataset.tags || '').split(';').filter(Boolean);
        renderTags(initialTags, true); // Skip backend update for initial render

        // Event handler: Remove tag when clicking the ✖ button
        container.addEventListener("click", e => {
            if (e.target.classList.contains("remove-tag")) {
                const tagToRemove = e.target.dataset.tag;
                const tags = getCurrentTags().filter(t => t !== tagToRemove);
                renderTags(tags);
                
                // Show success message for tag removal
                showToast(`🗑️ Tag "${tagToRemove}" removed successfully`, "success");
            }
        });

        // Event handler: Show input field when clicking "+ Add Tag"
        addBtn.addEventListener("click", () => {
            inputContainer.classList.remove("d-none");
            // Add a highlight class to make the input more visible
            inputContainer.classList.add("highlight-input");
            // Remove the highlight after 1.5 seconds
            setTimeout(() => inputContainer.classList.remove("highlight-input"), 1500);
            input.focus();
        });

        // Event handler: Add tag on Enter key press
        input.addEventListener("keydown", e => {
            if (e.key === "Enter") {
                e.preventDefault();
                const newTag = input.value.trim();
                
                // Validate tag input
                if (!newTag) {
                    showToast("⚠️ Tag cannot be empty", "warning");
                    return;
                }
                
                if (getCurrentTags().includes(newTag)) {
                    showToast("⚠️ Tag already exists", "warning");
                    return;
                }

                const tags = getCurrentTags();
                tags.push(newTag);
                renderTags(tags);

                // Show success message
                showToast(`✅ Tag "${newTag}" added successfully`, "success");

                // Add to available tags if it doesn't exist yet
                addToAvailableTags(newTag);
                
                input.value = "";
                inputContainer.classList.add("d-none");
            }
        });

        // Event handler: Hide input field when focus is lost
        input.addEventListener("blur", () => {
            inputContainer.classList.add("d-none");
        });
    });
    
    // Setup tag restore functionality
    const restoreTagsBtn = document.getElementById('restore-tags-btn');
    if (restoreTagsBtn) {
        restoreTagsBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Create a file input for selecting the JSON backup
            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.accept = 'application/json';
            fileInput.style.display = 'none';
            document.body.appendChild(fileInput);
            
            // Handle file selection
            fileInput.addEventListener('change', function() {
                if (fileInput.files.length === 0) return;
                
                const file = fileInput.files[0];
                const formData = new FormData();
                formData.append('backup_file', file);
                
                // Show loading message
                showToast("🔄 Restoring tags from backup...", "info");
                
                // Send file to server
                fetch('/api/restore-tags', {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    // First check if there's a response at all
                    if (!response) {
                        throw new Error('No response received from server');
                    }
                    
                    // Check if the response is ok before trying to parse JSON
                    if (!response.ok) {
                        throw new Error(`Server error: ${response.status} ${response.statusText}`);
                    }
                    
                    // Try to parse the JSON
                    return response.json().then(data => {
                        // Additional check to ensure data exists
                        if (!data) {
                            throw new Error('No data in server response');
                        }
                        return data;
                    });
                })
                .then(data => {
                    if (data && data.success) {
                        // Show success message
                        showToast(`✅ ${data.message}`, "success");                        
                        // Reload the page after a short delay
                        setTimeout(() => location.reload(), 2000);
                    } else {
                        // Display error message and don't reload the page on complete failure
                        if (data && data.error) {
                            showToast(`⚠️ Error: ${data.error}`, "danger");
                        } else {
                            // Show a more specific message about deleted VMs
                            showToast(`⚠️ Some VMs tags could not be restored. They may have been deleted since the backup was created.`, "warning");
                            
                            // Still reload the page after a delay
                            setTimeout(() => location.reload(), 4000);
                        }
                    }
                })
                .catch(error => {
                    
                        errorMessage = error.message || 'Unknown error during restore';
                        showToast(`⚠️ ${errorMessage}`, "warning");
                    }
                )
                .finally(() => {
                    // Remove the file input
                    document.body.removeChild(fileInput);
                    
                    // Always reload the page after 5 seconds as a fallback
                    // This ensures the UI is refreshed even if an error occurs
                    setTimeout(() => {
                        console.log('Forcing page reload');
                        location.reload();
                    }, 5000);
                });
            });
            
            // Trigger file selection dialog
            fileInput.click();
        });
    }
});

// Global variables for tracking bulk tag management elements
let selectedTagsContainer;

/**
 * Add a new tag to the Available Tags section for bulk operations
 * 
 * @param {string} tag - The tag to add to the available tags list
 */
function addToAvailableTags(tag) {
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
 * Display a toast notification with a message and optional type
 * 
 * @param {string} message - The message to display
 * @param {string} type - Message type: 'info', 'success', 'warning', or 'danger'
 */
function showToast(message, type = "info") {
    // Create toast container if it doesn't exist
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement("div");
        toastContainer.className = "toast-container position-fixed bottom-0 end-0 p-3";
        toastContainer.style.zIndex = "1050";
        document.body.appendChild(toastContainer);
    }
    
    // Create toast
    const toast = document.createElement("div");
    toast.className = `toast align-items-center text-bg-${type} border-0 show`;
    toast.role = "alert";
    toast.setAttribute("aria-live", "assertive");
    toast.setAttribute("aria-atomic", "true");
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body fw-medium">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>`;
    
    // Add to container and set up auto-removal
    toastContainer.appendChild(toast);
    
    // Add animation
    toast.style.transform = "translateY(100%)";
    setTimeout(() => {
        toast.style.transition = "transform 0.3s ease-out";
        toast.style.transform = "translateY(0)";
    }, 10);
    
    // Remove after delay
    setTimeout(() => {
        toast.style.transform = "translateY(100%)";
        setTimeout(() => toast.remove(), 300);
    }, 5000);
    
    // Close button functionality
    toast.querySelector('.btn-close').addEventListener('click', () => {
        toast.style.transform = "translateY(100%)";
        setTimeout(() => toast.remove(), 300);
    });
}

/**
 * Initialize the bulk tag management functionality
 * Handles adding, removing, and applying tags to multiple VMs/containers at once
 */
function initBulkTagManagement() {
    // Get references to DOM elements
    const bulkPanel = document.getElementById('bulkTagPanel');
    const toggleBtn = document.getElementById('toggleBulkPanel');
    const addNewTagBtn = document.getElementById('addNewTagBtn');
    const newTagInput = document.getElementById('newTagInput');
    
    // Set the global selectedTagsContainer variable
    selectedTagsContainer = document.querySelector('.selected-tags-container');
    const bulkApplyBtn = document.getElementById('bulkApplyBtn');
    const selectAllVMs = document.getElementById('selectAllVMs');
    const vmCheckboxes = document.querySelectorAll('.vm-checkbox');
    const tagOperation = document.getElementsByName('tagOperation');
    const availableTags = document.getElementById('availableTags');
    
    // Ensure available tags are properly split (in case they contain semicolons)
    ensureProperTagSplitting();
    
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
    
    // Select All VMs checkbox
    if (selectAllVMs) {
        selectAllVMs.addEventListener('change', () => {
            document.querySelectorAll('.vm-checkbox:not(.filtered-out)').forEach(cb => {
                cb.checked = selectAllVMs.checked;
                updateSelectedVMsList();
            });
        });
    }
    
    // VM Search functionality
    const vmSearchInput = document.getElementById('vmSearchInput');
    const clearSearchBtn = document.getElementById('clearSearchBtn');
    
    if (vmSearchInput) {
        vmSearchInput.addEventListener('input', filterVMs);
    }
    
    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            vmSearchInput.value = '';
            filterVMs();
        });
    }
    
    /**
     * Filter VM list based on search input
     * Shows/hides rows based on VM name or ID matching the search term
     */
    function filterVMs() {
        const searchTerm = vmSearchInput.value.toLowerCase();
        const vmRows = document.querySelectorAll('table tbody tr');
        
        vmRows.forEach(row => {
            const vmName = row.querySelector('td:nth-child(2)').textContent.toLowerCase();
            const vmId = row.querySelector('td:nth-child(3)').textContent.toLowerCase();
            const vmCheckbox = row.querySelector('.vm-checkbox');
            
            if (vmName.includes(searchTerm) || vmId.includes(searchTerm) || searchTerm === '') {
                row.style.display = '';
                if (vmCheckbox) {
                    vmCheckbox.classList.remove('filtered-out');
                }
            } else {
                row.style.display = 'none';
                if (vmCheckbox) {
                    vmCheckbox.classList.add('filtered-out');
                }
            }
        });
    }
    
    // Update Selected VMs list on checkbox changes
    document.querySelectorAll('.vm-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', updateSelectedVMsList);
    });
    
    // Update Selected VMs list initially
    updateSelectedVMsList();
    
    /**
     * Update the selected VMs list display with selected VM names and IDs
     */
    function updateSelectedVMsList() {
        const selectedVMsList = document.getElementById('selectedVMsList');
        if (!selectedVMsList) return;
        
        const selectedCheckboxes = document.querySelectorAll('.vm-checkbox:checked');
        
        if (selectedCheckboxes.length === 0) {
            selectedVMsList.innerHTML = '<span class="text-muted small fst-italic">No VMs selected</span>';
            return;
        }
        
        selectedVMsList.innerHTML = '';
        
        selectedCheckboxes.forEach(checkbox => {
            const vmName = checkbox.dataset.name || 'Unnamed';
            const vmId = checkbox.dataset.vmid;
            
            const badge = document.createElement('span');
            badge.className = 'badge bg-secondary d-flex align-items-center me-1 mb-1';
            badge.innerHTML = `
                ${vmName} (${vmId})
            `;
            
            selectedVMsList.appendChild(badge);
        });
    }
    
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
            
            // Get selected VMs
            const selectedVMs = [];
            vmCheckboxes.forEach(cb => {
                if (cb.checked) {
                    selectedVMs.push({
                        id: parseInt(cb.dataset.vmid),
                        node: cb.dataset.node,
                        type: cb.dataset.type,
                        tags: cb.dataset.tags || '',
                        name: cb.dataset.name
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
    
    /**
     * Get all currently selected tags from the UI
     * 
     * @returns {string[]} Array of selected tag names
     */
    function getSelectedTags() {
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
        if (!tag || getSelectedTags().includes(tag)) return;
        
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
                        const tagsContainer = document.getElementById('availableTags');
                        if (tagsContainer) {
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
                                if (newCheckbox.checked) {
                                    addSelectedTag(tag);
                                } else {
                                    removeSelectedTag(tag);
                                }
                            });
                        }
                    }
                });
            }
        });
    }
}
