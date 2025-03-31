/**
 * Tag Editor module
 * Handles the individual VM tag editing functionality
 * 
 * @file modules/tagEditor.js
 */

import { showToast } from './utils.js';
import { addToAvailableTags } from './bulkTagManager.js';

/**
 * Initialize individual tag editor for each VM/container
 */
export function initializeTagEditor() {
    document.querySelectorAll(".tag-editor").forEach(container => {
        const vmid = container.dataset.vmid;
        const node = container.dataset.node;
        const type = container.dataset.type;
        const tagList = container.querySelector(".tag-list");
        const inputContainer = container.querySelector('.tag-input-container');
        const input = container.querySelector(".tag-input");
        const addBtn = container.querySelector(".add-tag-btn");

        // Load initial tags from attribute
        const initialTags = (tagList.dataset.tags || '').split(';').filter(Boolean);
        renderTags(initialTags, true, tagList, vmid, node, type); // Skip backend update for initial render

        // Event handler: Remove tag when clicking the ✖ button
        container.addEventListener("click", e => {
            if (e.target.classList.contains("remove-tag")) {
                const tagToRemove = e.target.dataset.tag;
                const tags = getCurrentTags(tagList).filter(t => t !== tagToRemove);
                renderTags(tags, false, tagList, vmid, node, type);
                
                // Show success message for tag removal
                showToast(`🗑️ Tag "${tagToRemove}" removed successfully`, "success");
            }
        });

        // Event handler: Show input field when clicking "+ Add Tag"
        if (addBtn) {
            addBtn.addEventListener("click", () => {
                inputContainer.classList.remove("d-none");
                // Add a highlight class to make the input more visible
                inputContainer.classList.add("highlight-input");
                // Remove the highlight after 1.5 seconds
                setTimeout(() => inputContainer.classList.remove("highlight-input"), 1500);
                input.focus();
            });
        }

        // Event handler: Add tag on Enter key press
        if (input) {
            input.addEventListener("keydown", e => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    const newTag = input.value.trim();
                    
                    // Validate tag input
                    if (!newTag) {
                        showToast("⚠️ Tag cannot be empty", "warning");
                        return;
                    }
                    
                    if (getCurrentTags(tagList).includes(newTag)) {
                        showToast("⚠️ Tag already exists", "warning");
                        return;
                    }

                    const tags = getCurrentTags(tagList);
                    tags.push(newTag);
                    renderTags(tags, false, tagList, vmid, node, type);

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
        }
    });
}

/**
 * Get the current list of tags from the DOM elements
 * 
 * @param {HTMLElement} tagList - The tag list container element
 * @returns {string[]} Array of tag names
 */
function getCurrentTags(tagList) {
    return Array.from(tagList.querySelectorAll(".tag-chip span")).map(span =>
        span.textContent.trim()
    );
}

/**
 * Render tags as visual chips in the UI and optionally update the backend
 * 
 * @param {string[]} tags - Array of tag names to render
 * @param {boolean} skipBackendUpdate - If true, doesn't sync with server (default: false)
 * @param {HTMLElement} tagList - The tag list container element
 * @param {string} vmid - The VM ID
 * @param {string} node - The node name
 * @param {string} type - The VM type
 */
function renderTags(tags, skipBackendUpdate, tagList, vmid, node, type) {
    tagList.innerHTML = '';
    const updatedTags = tags.filter(t => t.trim());

    if (updatedTags.length === 0) {
        tagList.innerHTML = `<span class="text-muted small fst-italic">No tags</span>`;
        if (!skipBackendUpdate) {
            updateBackend([], vmid, node, type);
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
        updateBackend(updatedTags, vmid, node, type);
    }
}

/**
 * Send updated tags to the Proxmox backend via API
 * 
 * @param {string[]} tags - Array of tags to save to the server
 * @param {string} vmid - The VM ID
 * @param {string} node - The node name
 * @param {string} type - The VM type
 */
function updateBackend(tags, vmid, node, type) {
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
