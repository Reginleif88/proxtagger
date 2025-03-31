// Example of app.js *after* removing the problematic block:

document.addEventListener('DOMContentLoaded', function() {
    console.group('ProxTagger Initialization');
    console.time('Total Initialization');

    // Debug global state
    window.DEBUG = true; // Keep if needed for debugging

    // Initialize DataTables first
    console.log('Step 1: Initializing DataTables...');
    import('./modules/dataTables.js')
        .then(module => {
            console.log('DataTables module loaded');
            module.initializeDataTables(); // This will trigger initVMFilters via initComplete
            console.log('DataTables initialization sequence started');
        })
        .catch(err => console.error('Error loading DataTables module:', err));

    // Import other modules (these can load asynchronously)
    console.log('Step 2: Loading other modules...');

    import('./modules/tagEditor.js')
        .then(module => {
            console.log('Tag Editor module loaded');
            module.initializeTagEditor();
            console.log('Tag Editors initialized');
        })
        .catch(err => console.error('Error loading Tag Editor module:', err));

    import('./modules/bulkTagManager.js')
        .then(module => {
            console.log('Bulk Tag Manager module loaded');
            module.initBulkTagManagement();
            console.log('Bulk Tag Manager initialized');
        })
        .catch(err => console.error('Error loading Bulk Tag Manager module:', err));

    import('./modules/backupRestore.js')
        .then(module => {
            console.log('Backup/Restore module loaded');
            module.initBackupRestore();
            console.log('Backup/Restore initialized');
        })
        .catch(err => console.error('Error loading Backup/Restore module:', err));

    console.log('Initialization process setup.'); // Note: Actual completion depends on async modules
    console.timeEnd('Total Initialization'); // This might end before all async modules are fully done
    console.groupEnd();
});
