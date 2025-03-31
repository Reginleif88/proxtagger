/**
 * Backup and Restore module
 * Handles the tag backup and restore functionality
 * 
 * @file modules/backupRestore.js
 */

import { showToast } from './utils.js';

/**
 * Initialize backup/restore functionality
 */
export function initBackupRestore() {
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
                    const errorMessage = error.message || 'Unknown error during restore';
                    showToast(`⚠️ ${errorMessage}`, "warning");
                })
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
}
