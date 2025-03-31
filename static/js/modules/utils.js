/**
 * Utilities module
 * Contains common utility functions used across the application
 * 
 * @file modules/utils.js
 */

/**
 * Display a toast notification with a message and optional type
 * 
 * @param {string} message - The message to display
 * @param {string} type - Message type: 'info', 'success', 'warning', or 'danger'
 */
export function showToast(message, type = "info") {
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
