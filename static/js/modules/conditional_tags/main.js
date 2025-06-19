/**
 * Main module for conditional tags functionality
 * Coordinates all conditional tags modules
 */

import { showToast } from '../utils.js';

// Module state
let rules = [];
let vmProperties = {};
let currentEditingRule = null;

// Rule templates
const ruleTemplates = {
    'debian-lxc': {
        name: 'Debian LXC Tagging',
        description: 'Automatically tag all Debian-based LXC containers',
        conditions: {
            operator: 'AND',
            rules: [
                { field: 'type', operator: 'equals', value: 'lxc' },
                { field: 'config.ostype', operator: 'contains', value: 'debian' }
            ]
        },
        actions: {
            add_tags: ['deb-lxc'],
            remove_tags: [],
            else_add_tags: [],
            else_remove_tags: []
        },
        schedule: {
            enabled: true,
            cron: '0 */6 * * *'
        }
    },
    'ha-validation': {
        name: 'HA Validation',
        description: 'Add "ha" tag for replicated + HA VMs, remove for others',
        conditions: {
            operator: 'AND',
            rules: [
                { field: 'ha.enabled', operator: 'equals', value: 'true' },
                { field: 'replication.enabled', operator: 'equals', value: 'true' }
            ]
        },
        actions: {
            add_tags: ['ha'],
            remove_tags: [],
            else_add_tags: [],
            else_remove_tags: ['ha']
        },
        schedule: {
            enabled: true,
            cron: '0 0 * * *'
        }
    },
    'high-resource': {
        name: 'High-Resource VMs',
        description: 'Tag VMs with more than 4 cores and 8GB RAM',
        conditions: {
            operator: 'AND',
            rules: [
                { field: 'maxcpu', operator: 'greater_than', value: '4' },
                { field: 'maxmem', operator: 'greater_than', value: '8589934592' }
            ]
        },
        actions: {
            add_tags: ['high-resource'],
            remove_tags: [],
            else_add_tags: [],
            else_remove_tags: []
        },
        schedule: {
            enabled: false,
            cron: ''
        }
    }
};

console.log('Conditional Tags module loaded!');

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', async function() {
    console.log('Initializing Conditional Tags...');
    
    // Test if basic elements exist
    console.log('Testing elements:');
    console.log('- addConditionBtn:', !!document.getElementById('addConditionBtn'));
    console.log('- conditionsContainer:', !!document.getElementById('conditionsContainer'));
    console.log('- propertiesStatus:', !!document.getElementById('propertiesStatus'));
    
    try {
        initializeUI();
        console.log('UI initialized');
        
        // Load VM properties first, then rules
        await loadVMProperties();
        console.log('VM properties loaded');
        
        await loadRules();
        console.log('Rules loaded');
        
        await loadExecutionHistory();
        console.log('Execution history loaded');
        
        console.log('Conditional Tags fully initialized');
    } catch (error) {
        console.error('Error during initialization:', error);
    }
});

/**
 * Initialize UI event handlers
 */
function initializeUI() {
    // Rule builder controls
    const enableScheduleCheckbox = document.getElementById('enableSchedule');
    const schedulePreset = document.getElementById('schedulePreset');
    const cronExpression = document.getElementById('cronExpression');
    
    // Schedule controls
    enableScheduleCheckbox?.addEventListener('change', function() {
        const enabled = this.checked;
        schedulePreset.disabled = !enabled;
        cronExpression.disabled = !enabled;
        
        if (!enabled) {
            schedulePreset.value = '';
            cronExpression.value = '';
            hideCronPreview();
        } else {
            // When enabling schedule, set default daily cron if empty
            if (!cronExpression.value.trim()) {
                cronExpression.value = '0 0 * * *';
                schedulePreset.value = '0 0 * * *';
            }
            validateAndPreviewCron(cronExpression.value.trim());
        }
    });
    
    schedulePreset?.addEventListener('change', function() {
        if (this.value) {
            cronExpression.value = this.value;
            validateAndPreviewCron(this.value);
        }
    });
    
    // Cron expression validation and preview
    const cronExpressionInput = document.getElementById('cronExpression');
    if (cronExpressionInput) {
        cronExpressionInput.addEventListener('input', function() {
            if (this.value.trim()) {
                validateAndPreviewCron(this.value.trim());
            } else {
                hideCronPreview();
            }
        });
    }
    
    
    // Condition management
    const addConditionBtn = document.getElementById('addConditionBtn');
    if (addConditionBtn) {
        console.log('Adding event listener to Add Condition button');
        addConditionBtn.addEventListener('click', addCondition);
    } else {
        console.error('Add Condition button not found!');
    }
    
    
    
    // Tag management - THEN actions
    document.getElementById('addTagBtn')?.addEventListener('click', () => addActionTag('add'));
    document.getElementById('removeTagBtn')?.addEventListener('click', () => addActionTag('remove'));
    
    // Tag management - ELSE actions
    document.getElementById('elseAddTagBtn')?.addEventListener('click', () => addActionTag('elseAdd'));
    document.getElementById('elseRemoveTagBtn')?.addEventListener('click', () => addActionTag('elseRemove'));
    
    // Rule actions
    document.getElementById('testRuleBtn')?.addEventListener('click', () => testRule());
    document.getElementById('clearRuleBtn')?.addEventListener('click', clearRuleForm);
    document.getElementById('saveRuleBtn')?.addEventListener('click', saveRule);
    
    // Template buttons
    document.querySelectorAll('.template-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const templateId = this.dataset.template;
            loadTemplate(templateId);
        });
    });
    
    // Import/Export functionality
    document.getElementById('importRulesBtn')?.addEventListener('click', function() {
        document.getElementById('importRulesInput').click();
    });
    
    document.getElementById('importRulesInput')?.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            importRules(file);
        }
    });
    
    // History filter
    document.getElementById('historyRuleFilter')?.addEventListener('change', function() {
        loadExecutionHistory(this.value);
    });
    
    // Enable Enter key for tag inputs
    document.getElementById('addTagInput')?.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            addActionTag('add');
        }
    });
    
    document.getElementById('removeTagInput')?.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            addActionTag('remove');
        }
    });
}

/**
 * Load available VM properties for rule builder
 */
async function loadVMProperties() {
    try {
        const response = await fetch('/conditional-tags/api/vm-properties');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Check if response contains error
        if (data.error) {
            throw new Error(data.error);
        }
        
        vmProperties = data;
        console.log(`Loaded ${Object.keys(vmProperties).length} VM properties`);
        updatePropertiesStatus();
        
    } catch (error) {
        console.error('Error loading VM properties:', error);
        showToast('Failed to load VM properties: ' + error.message, 'error');
        vmProperties = {}; // Ensure it's empty on failure
        updatePropertiesStatus();
    }
}

/**
 * Update the properties status indicator
 */
function updatePropertiesStatus() {
    const statusElement = document.getElementById('propertiesStatus');
    if (statusElement && vmProperties) {
        const count = Object.keys(vmProperties).length;
        statusElement.textContent = `${count} Properties`;
        statusElement.className = count > 0 ? 'badge bg-success me-2' : 'badge bg-warning me-2';
    }
}

/**
 * Load and display rules
 */
async function loadRules() {
    try {
        const response = await fetch('/conditional-tags/api/rules');
        if (!response.ok) throw new Error('Failed to load rules');
        
        rules = await response.json();
        console.log(`Loaded ${rules.length} rules`);
        
        displayRules();
        updateHistoryFilter();
    } catch (error) {
        console.error('Error loading rules:', error);
        showToast('Failed to load rules: ' + error.message, 'error');
    }
}

/**
 * Display rules in the table
 */
function displayRules() {
    const tbody = document.querySelector('#rulesTable tbody');
    if (!tbody) return;
    
    if (rules.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center text-muted p-4">
                    No rules created yet. Use the rule builder above to create your first rule.
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = rules.map(rule => `
        <tr>
            <td>
                <strong>${escapeHtml(rule.name)}</strong>
            </td>
            <td>
                <small class="text-muted">${escapeHtml(rule.description || 'No description')}</small>
            </td>
            <td>
                ${rule.schedule.enabled ? 
                    `<code class="small">${escapeHtml(rule.schedule.cron)}</code><br>
                     <small class="text-muted">Next: ${rule.next_run ? escapeHtml(new Date(rule.next_run).toLocaleString()) : 'N/A'}</small>` : 
                    '<span class="text-muted">Manual only</span>'
                }
            </td>
            <td>
                <small>
                    Matches: ${rule.stats.total_matches || 0}<br>
                    Added: ${rule.stats.tags_added || 0}<br>
                    Removed: ${rule.stats.tags_removed || 0}
                </small>
            </td>
            <td>
                ${rule.last_run ? 
                    `<small>${new Date(rule.last_run).toLocaleString()}</small>` : 
                    '<span class="text-muted">Never</span>'
                }
            </td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary" onclick="editRule('${rule.id}')" title="Edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-outline-success" onclick="executeRule('${rule.id}')" title="Run Now">
                        <i class="bi bi-play"></i>
                    </button>
                    <button class="btn btn-outline-info" onclick="testRule('${rule.id}')" title="Test">
                        <i class="bi bi-eye"></i>
                    </button>
                    <button class="btn btn-outline-danger" onclick="deleteRule('${rule.id}')" title="Delete">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}


/**
 * Get count of existing conditions
 */
function getConditionCount() {
    const container = document.getElementById('conditionsContainer');
    return container ? container.querySelectorAll('.condition-item').length : 0;
}

/**
 * Update logic preview based on current conditions
 */
function updateLogicPreview() {
    const preview = document.getElementById('logicPreview');
    if (!preview) return;
    
    const conditions = document.querySelectorAll('.condition-item');
    if (conditions.length === 0) {
        preview.textContent = 'No conditions yet';
        return;
    }
    
    let logic = '';
    conditions.forEach((condition, index) => {
        // Get field name for preview
        const fieldSelect = condition.querySelector('.condition-field');
        const fieldName = fieldSelect.value || `Condition ${index + 1}`;
        
        if (index === 0) {
            logic = fieldName;
        } else {
            // Get the logical operator for this condition
            const logicRadio = condition.querySelector('input[name^="logic-"]:checked');
            const operator = logicRadio ? logicRadio.value : 'AND';
            logic += ` ${operator} ${fieldName}`;
        }
    });
    
    preview.textContent = logic;
}

/**
 * Add a new condition to the rule builder
 */
function addCondition() {
    console.log('addCondition() called!');
    
    const container = document.getElementById('conditionsContainer');
    if (!container) {
        console.error('conditionsContainer not found');
        return;
    }
    console.log('conditionsContainer found');
    
    // Check if VM properties are loaded
    console.log('vmProperties check:', vmProperties, 'Keys:', Object.keys(vmProperties || {}));
    if (!vmProperties || Object.keys(vmProperties).length === 0) {
        console.warn('VM properties not loaded');
        showToast('VM properties not loaded. Please check your Proxmox connection.', 'error');
        return;
    }
    console.log('VM properties available, creating condition...');
    
    const conditionId = Date.now();
    const isFirst = getConditionCount() === 0;
    const conditionHtml = createConditionHTML(conditionId, isFirst);
    
    const conditionDiv = document.createElement('div');
    conditionDiv.innerHTML = conditionHtml;
    
    // Get the actual condition element (since we wrapped it in a div)
    const actualCondition = conditionDiv.firstElementChild;
    container.appendChild(actualCondition);
    
    // Hide placeholder if it exists
    const placeholder = document.getElementById('conditionsPlaceholder');
    if (placeholder) {
        placeholder.style.display = 'none';
    }
    
    // Initialize the field selector
    const fieldSelect = actualCondition.querySelector('.condition-field');
    const operatorSelect = actualCondition.querySelector('.condition-operator');
    
    populateFieldOptions(fieldSelect);
    
    // Add field change handler for dynamic operator filtering
    fieldSelect.addEventListener('change', function() {
        updateOperatorOptions(this.value, operatorSelect);
        updateLogicPreview();
    });
    
    // Add logic operator change handler
    const logicRadios = actualCondition.querySelectorAll('input[name^="logic-"]');
    logicRadios.forEach(radio => {
        radio.addEventListener('change', updateLogicPreview);
    });
    
    // Update condition numbers and logic preview
    updateConditionNumbers();
    updateLogicPreview();
}

/**
 * Update condition numbers in badges
 */
function updateConditionNumbers() {
    const conditions = document.querySelectorAll('.condition-item');
    conditions.forEach((condition, index) => {
        const badge = condition.querySelector('.condition-number');
        if (badge) {
            badge.textContent = index + 1;
        }
    });
}

/**
 * Create HTML for a condition with inline logic operators
 */
function createConditionHTML(conditionId, isFirst = false) {
    return `
        <div class="condition-item mb-3" data-condition-id="${conditionId}">
            ${!isFirst ? `
            <!-- Logical operator connection -->
            <div class="logic-connector d-flex justify-content-center mb-2">
                <div class="btn-group" role="group">
                    <input type="radio" class="btn-check" id="and-${conditionId}" name="logic-${conditionId}" value="AND" checked>
                    <label class="btn btn-outline-primary btn-sm" for="and-${conditionId}">AND</label>
                    
                    <input type="radio" class="btn-check" id="or-${conditionId}" name="logic-${conditionId}" value="OR">
                    <label class="btn btn-outline-secondary btn-sm" for="or-${conditionId}">OR</label>
                </div>
            </div>
            ` : ''}
            
            <!-- Condition content -->
            <div class="p-3 border rounded bg-white position-relative">
                <div class="row align-items-center">
                    <div class="col-md-4">
                        <label class="form-label">Field</label>
                        <select class="form-select condition-field" data-condition-id="${conditionId}">
                            <option value="">Select field...</option>
                        </select>
                    </div>
                    <div class="col-md-2">
                        <label class="form-label">Operator</label>
                        <select class="form-select condition-operator" data-condition-id="${conditionId}">
                            <option value="equals">Equals</option>
                            <option value="not_equals">Not Equals</option>
                            <option value="contains">Contains</option>
                            <option value="not_contains">Not Contains</option>
                            <option value="greater_than">Greater Than</option>
                            <option value="less_than">Less Than</option>
                            <option value="regex">Regex Match</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Value</label>
                        <input type="text" class="form-control condition-value" data-condition-id="${conditionId}" placeholder="Enter value...">
                    </div>
                    <div class="col-md-2">
                        <label class="form-label">&nbsp;</label>
                        <button type="button" class="btn btn-outline-danger w-100" onclick="removeCondition(this)">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
                
                <!-- Condition number badge -->
                <span class="position-absolute top-0 start-0 translate-middle badge rounded-pill bg-primary condition-number">
                    ${getConditionCount() + 1}
                </span>
            </div>
        </div>
    `;
}

/**
 * Populate field options in a select element
 */
function populateFieldOptions(selectElement) {
    if (!selectElement || !vmProperties) return;
    
    // Clear existing options except the first one
    while (selectElement.children.length > 1) {
        selectElement.removeChild(selectElement.lastChild);
    }
    
    // Categorize fields
    const categories = {
        'Basic Properties': [],
        'Resource Usage': [],
        'Configuration': [],
        'High Availability': [],
        'Replication & Backup': [],
        'Other': []
    };
    
    Object.entries(vmProperties).forEach(([field, meta]) => {
        if (['vmid', 'name', 'node', 'type', 'status', 'tags'].includes(field)) {
            categories['Basic Properties'].push([field, meta]);
        } else if (['cpu', 'maxcpu', 'mem', 'maxmem', 'disk', 'maxdisk'].includes(field)) {
            categories['Resource Usage'].push([field, meta]);
        } else if (field.startsWith('config.')) {
            categories['Configuration'].push([field, meta]);
        } else if (field.startsWith('ha.')) {
            categories['High Availability'].push([field, meta]);
        } else if (field.startsWith('replication.') || field.startsWith('backup.') || field.startsWith('snapshots.')) {
            categories['Replication & Backup'].push([field, meta]);
        } else {
            categories['Other'].push([field, meta]);
        }
    });
    
    // Add categorized options
    Object.entries(categories).forEach(([categoryName, fields]) => {
        if (fields.length > 0) {
            // Add category header
            const optgroup = document.createElement('optgroup');
            optgroup.label = categoryName;
            
            fields.forEach(([field, meta]) => {
                const option = document.createElement('option');
                option.value = field;
                option.textContent = `${field} (${meta.description})`;
                optgroup.appendChild(option);
            });
            
            selectElement.appendChild(optgroup);
        }
    });
}

/**
 * Update operator options based on selected field type
 */
function updateOperatorOptions(fieldName, operatorSelect) {
    if (!fieldName || !vmProperties[fieldName]) return;
    
    const fieldMeta = vmProperties[fieldName];
    const fieldType = fieldMeta.type;
    
    // Define operators for different field types
    const operatorsByType = {
        'string': [
            { value: 'equals', text: 'Equals' },
            { value: 'not_equals', text: 'Not Equals' },
            { value: 'contains', text: 'Contains' },
            { value: 'not_contains', text: 'Not Contains' },
            { value: 'regex', text: 'Regex Match' }
        ],
        'number': [
            { value: 'equals', text: 'Equals' },
            { value: 'not_equals', text: 'Not Equals' },
            { value: 'greater_than', text: 'Greater Than' },
            { value: 'less_than', text: 'Less Than' },
            { value: 'greater_equals', text: 'Greater or Equal' },
            { value: 'less_equals', text: 'Less or Equal' }
        ],
        'boolean': [
            { value: 'equals', text: 'Equals' }
        ]
    };
    
    const operators = operatorsByType[fieldType] || operatorsByType['string'];
    
    // Clear current options
    operatorSelect.innerHTML = '';
    
    // Add appropriate operators
    operators.forEach(op => {
        const option = document.createElement('option');
        option.value = op.value;
        option.textContent = op.text;
        operatorSelect.appendChild(option);
    });
    
    // Add placeholder text for value field
    const valueInput = operatorSelect.closest('.condition-item').querySelector('.condition-value');
    if (valueInput) {
        updateValuePlaceholder(fieldName, valueInput);
    }
}

/**
 * Update value input placeholder based on field type
 */
function updateValuePlaceholder(fieldName, valueInput) {
    if (!fieldName || !vmProperties[fieldName]) return;
    
    const fieldMeta = vmProperties[fieldName];
    
    let placeholder = 'Enter value...';
    
    if (fieldMeta.example !== undefined) {
        placeholder = `e.g., ${fieldMeta.example}`;
    } else if (fieldMeta.values) {
        placeholder = `e.g., ${fieldMeta.values.join(', ')}`;
    } else if (fieldMeta.type === 'boolean') {
        placeholder = 'true or false';
    } else if (fieldMeta.type === 'number') {
        placeholder = 'Enter number...';
    }
    
    valueInput.placeholder = placeholder;
}

/**
 * Remove a condition
 */
window.removeCondition = function(button) {
    const conditionDiv = button.closest('.condition-item');
    if (conditionDiv) {
        conditionDiv.remove();
        
        // Update condition numbers and logic preview
        updateConditionNumbers();
        updateLogicPreview();
        
        // Show placeholder if no conditions remain
        const container = document.getElementById('conditionsContainer');
        const remainingConditions = container.querySelectorAll('.condition-item');
        const placeholder = document.getElementById('conditionsPlaceholder');
        
        if (remainingConditions.length === 0 && placeholder) {
            placeholder.style.display = 'block';
        }
    }
};



/**
 * Add an action tag
 */
function addActionTag(type) {
    let inputId, listId, badgeClass;
    
    switch(type) {
        case 'add':
            inputId = 'addTagInput';
            listId = 'addTagsList';
            badgeClass = 'success';
            break;
        case 'remove':
            inputId = 'removeTagInput';
            listId = 'removeTagsList';
            badgeClass = 'danger';
            break;
        case 'elseAdd':
            inputId = 'elseAddTagInput';
            listId = 'elseAddTagsList';
            badgeClass = 'success';
            break;
        case 'elseRemove':
            inputId = 'elseRemoveTagInput';
            listId = 'elseRemoveTagsList';
            badgeClass = 'danger';
            break;
        default:
            return;
    }
    
    const input = document.getElementById(inputId);
    const list = document.getElementById(listId);
    
    if (!input || !list) return;
    
    const tag = input.value.trim().toLowerCase();
    if (!tag) return;
    
    // Check if tag already exists
    const existingTags = Array.from(list.querySelectorAll('.tag-badge')).map(el => el.dataset.tag);
    if (existingTags.includes(tag)) {
        showToast(`Tag "${tag}" is already in the list`, 'warning');
        return;
    }
    
    // Create tag element
    const tagElement = document.createElement('span');
    tagElement.className = `badge bg-${badgeClass} tag-badge`;
    tagElement.dataset.tag = tag;
    tagElement.innerHTML = `
        ${escapeHtml(tag)}
        <button type="button" class="btn-close btn-close-white ms-1" onclick="removeActionTag(this)"></button>
    `;
    
    list.appendChild(tagElement);
    input.value = '';
}

/**
 * Remove an action tag
 */
window.removeActionTag = function(button) {
    const tagElement = button.closest('.tag-badge');
    if (tagElement) {
        tagElement.remove();
    }
};

/**
 * Test a rule (dry run)
 */
async function testRule(ruleId = null) {
    try {
        showToast('Testing rule...', 'info');
        let ruleData;
        
        if (ruleId) {
            // Test existing rule
            const response = await fetch(`/conditional-tags/api/rules/${ruleId}/dry-run`, {
                method: 'POST'
            });
            if (!response.ok) throw new Error('Failed to test rule');
            ruleData = await response.json();
        } else {
            // Test rule from form - create temporary rule and test it
            const rule = buildRuleFromForm();
            if (!rule) return;
            
            // Create a temporary rule for testing
            const tempResponse = await fetch('/conditional-tags/api/rules', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    ...rule,
                    name: `TEMP_TEST_${Date.now()}`,
                    enabled: false
                })
            });
            
            if (!tempResponse.ok) throw new Error('Failed to create temporary rule');
            const tempRule = await tempResponse.json();
            
            // Test the temporary rule
            const testResponse = await fetch(`/conditional-tags/api/rules/${tempRule.id}/dry-run`, {
                method: 'POST'
            });
            
            if (!testResponse.ok) throw new Error('Failed to test rule');
            ruleData = await testResponse.json();
            
            // Delete the temporary rule
            await fetch(`/conditional-tags/api/rules/${tempRule.id}`, {
                method: 'DELETE'
            });
        }
        
        // Show detailed test results
        showTestResults(ruleData);
        
    } catch (error) {
        console.error('Error testing rule:', error);
        showToast('Failed to test rule: ' + error.message, 'error');
    }
}

/**
 * Show detailed test results in a modal
 */
function showTestResults(ruleData) {
    const matchedCount = ruleData.matched_vms ? ruleData.matched_vms.length : 0;
    const tagsAddedCount = Object.keys(ruleData.tags_added || {}).length;
    const tagsRemovedCount = Object.keys(ruleData.tags_removed || {}).length;
    const isDryRun = ruleData.dry_run !== false; // Default to true for safety
    
    // Build detailed HTML content
    let resultClass = 'success';
    let resultIcon = 'check-circle';
    let resultTitle = 'Test Successful';
    
    if (ruleData.errors && ruleData.errors.length > 0) {
        resultClass = 'danger';
        resultIcon = 'x-circle';
        resultTitle = 'Test Failed';
    } else if (matchedCount === 0) {
        resultClass = 'warning';
        resultIcon = 'exclamation-triangle';
        resultTitle = 'No Matches Found';
    }
    
    let html = `
        <div class="alert alert-${resultClass} d-flex align-items-center">
            <i class="bi bi-${resultIcon} me-2"></i>
            <div>
                <strong>${resultTitle}</strong>
                ${isDryRun ? ' (Dry Run - No changes applied)' : ' (Changes were applied)'}
            </div>
        </div>
        
        <div class="row mb-3">
            <div class="col-md-4">
                <div class="card border-primary">
                    <div class="card-body text-center">
                        <h5 class="card-title text-primary">${matchedCount}</h5>
                        <p class="card-text">VMs Matched</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card border-success">
                    <div class="card-body text-center">
                        <h5 class="card-title text-success">${tagsAddedCount}</h5>
                        <p class="card-text">VMs Getting Tags</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card border-danger">
                    <div class="card-body text-center">
                        <h5 class="card-title text-danger">${tagsRemovedCount}</h5>
                        <p class="card-text">VMs Losing Tags</p>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Show matched VMs
    if (matchedCount > 0) {
        html += `
            <h6><i class="bi bi-server"></i> Matched VMs:</h6>
            <div class="mb-3">
                ${ruleData.matched_vms.map(vmid => `<span class="badge bg-secondary me-1">${escapeHtml(vmid)}</span>`).join('')}
            </div>
        `;
    }
    
    // Show tag changes
    if (tagsAddedCount > 0) {
        html += `<h6><i class="bi bi-plus-circle"></i> Tags to be Added:</h6><div class="mb-3">`;
        Object.entries(ruleData.tags_added || {}).forEach(([vmid, tags]) => {
            html += `<div class="mb-1"><strong>VM ${escapeHtml(vmid)}:</strong> `;
            html += tags.map(tag => `<span class="badge bg-success me-1">${escapeHtml(tag)}</span>`).join('');
            html += `</div>`;
        });
        html += `</div>`;
    }
    
    if (tagsRemovedCount > 0) {
        html += `<h6><i class="bi bi-dash-circle"></i> Tags to be Removed:</h6><div class="mb-3">`;
        Object.entries(ruleData.tags_removed || {}).forEach(([vmid, tags]) => {
            html += `<div class="mb-1"><strong>VM ${escapeHtml(vmid)}:</strong> `;
            html += tags.map(tag => `<span class="badge bg-danger me-1">${escapeHtml(tag)}</span>`).join('');
            html += `</div>`;
        });
        html += `</div>`;
    }
    
    // Show tags already present
    const tagsAlreadyPresentCount = Object.keys(ruleData.tags_already_present || {}).length;
    if (tagsAlreadyPresentCount > 0) {
        html += `<h6><i class="bi bi-check-circle"></i> Tags Already Present:</h6><div class="mb-3">`;
        Object.entries(ruleData.tags_already_present || {}).forEach(([vmid, tags]) => {
            html += `<div class="mb-1"><strong>VM ${escapeHtml(vmid)}:</strong> `;
            html += tags.map(tag => `<span class="badge bg-secondary me-1">${escapeHtml(tag)}</span>`).join('');
            html += `</div>`;
        });
        html += `</div>`;
    }
    
    // Show errors if any
    if (ruleData.errors && ruleData.errors.length > 0) {
        html += `
            <h6><i class="bi bi-exclamation-circle"></i> Errors:</h6>
            <div class="alert alert-danger">
                ${ruleData.errors.map(error => `<div>• ${escapeHtml(error)}</div>`).join('')}
            </div>
        `;
    }
    
    // Show execution time (only for actual executions, not dry runs)
    if (ruleData.execution_time && !isDryRun) {
        html += `<small class="text-muted">Execution time: ${ruleData.execution_time.toFixed(3)}s</small>`;
    }
    
    // Update modal content and show it
    document.getElementById('testResultsContent').innerHTML = html;
    
    
    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('testResultsModal'));
    modal.show();
}

window.testRule = testRule;

/**
 * Save the current rule
 */
async function saveRule() {
    try {
        const rule = buildRuleFromForm();
        if (!rule) return;
        
        const method = currentEditingRule ? 'PUT' : 'POST';
        const url = currentEditingRule ? 
            `/conditional-tags/api/rules/${currentEditingRule}` : 
            '/conditional-tags/api/rules';
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(rule)
        });
        
        if (!response.ok) throw new Error('Failed to save rule');
        
        showToast('Rule saved successfully!', 'success');
        clearRuleForm();
        loadRules();
        
    } catch (error) {
        console.error('Error saving rule:', error);
        showToast('Failed to save rule: ' + error.message, 'error');
    }
}

/**
 * Execute a rule
 */
window.executeRule = async function(ruleId) {
    if (!confirm('Are you sure you want to execute this rule? This will apply tag changes to matching VMs.')) {
        return;
    }
    
    try {
        showToast('Executing rule...', 'info');
        
        const response = await fetch(`/conditional-tags/api/rules/${ruleId}/execute`, {
            method: 'POST'
        });
        
        if (!response.ok) throw new Error('Failed to execute rule');
        
        const result = await response.json();
        showToast(`Rule executed: ${result.matched_vms.length} VMs processed`, 'success');
        
        loadRules(); // Refresh to update stats
        loadExecutionHistory(); // Refresh execution history
        
    } catch (error) {
        console.error('Error executing rule:', error);
        showToast('Failed to execute rule: ' + error.message, 'error');
    }
};

/**
 * Delete a rule
 */
window.deleteRule = async function(ruleId) {
    const rule = rules.find(r => r.id === ruleId);
    if (!rule) return;
    
    if (!confirm(`Are you sure you want to delete the rule "${rule.name}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/conditional-tags/api/rules/${ruleId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('Failed to delete rule');
        
        showToast('Rule deleted successfully!', 'success');
        loadRules();
        loadExecutionHistory(); // Refresh execution history
        
    } catch (error) {
        console.error('Error deleting rule:', error);
        showToast('Failed to delete rule: ' + error.message, 'error');
    }
};

/**
 * Edit a rule
 */
window.editRule = function(ruleId) {
    const rule = rules.find(r => r.id === ruleId);
    if (!rule) return;
    
    currentEditingRule = ruleId;
    loadRuleIntoForm(rule);
    
    // Show rule builder if collapsed
    const ruleBuilderContainer = document.getElementById('ruleBuilderContainer');
    if (!ruleBuilderContainer.classList.contains('show')) {
        const builderCollapse = new bootstrap.Collapse(ruleBuilderContainer, {
            show: true
        });
    }
    
};

/**
 * Build rule object from form data
 */
function buildRuleFromForm() {
    const name = document.getElementById('ruleName')?.value.trim();
    const description = document.getElementById('ruleDescription')?.value.trim();
    
    if (!name) {
        showToast('Rule name is required', 'error');
        return null;
    }
    
    // Validate and build conditions with inline logic operators
    const conditions = [];
    const logicOperators = [];
    const validationErrors = [];
    
    const conditionItems = document.querySelectorAll('.condition-item');
    
    if (conditionItems.length === 0) {
        showToast('At least one condition is required', 'error');
        return null;
    }
    
    conditionItems.forEach((item, index) => {
        const field = item.querySelector('.condition-field').value;
        const operator = item.querySelector('.condition-operator').value;
        const value = item.querySelector('.condition-value').value.trim();
        
        // Validate each condition
        if (!field) {
            validationErrors.push(`Condition ${index + 1}: Field is required`);
        }
        if (!operator) {
            validationErrors.push(`Condition ${index + 1}: Operator is required`);
        }
        if (!value) {
            validationErrors.push(`Condition ${index + 1}: Value is required`);
        }
        
        // Only add valid conditions
        if (field && operator && value) {
            conditions.push({ field, operator, value });
            
            // Get logic operator for this condition (except the first one)
            if (index > 0) {
                const logicRadio = item.querySelector('input[name^="logic-"]:checked');
                const logicOp = logicRadio ? logicRadio.value : 'AND';
                logicOperators.push(logicOp);
            }
        }
    });
    
    // Show validation errors if any
    if (validationErrors.length > 0) {
        showToast(`Please fix the following issues:\n• ${validationErrors.join('\n• ')}`, 'error');
        return null;
    }
    
    // For now, convert to simple AND/OR logic for backend compatibility
    // TODO: Extend backend to support complex logic expressions
    const hasAnyOr = logicOperators.includes('OR');
    const primaryOperator = hasAnyOr ? 'OR' : 'AND';
    
    // Show warning if mixing operators (for future enhancement)
    const hasAnyAnd = logicOperators.includes('AND');
    if (hasAnyOr && hasAnyAnd) {
        // Mixed operators detected - simplified to primary operator for compatibility
    }
    
    // Build actions
    const addTags = Array.from(document.querySelectorAll('#addTagsList .tag-badge'))
        .map(el => el.dataset.tag);
    const removeTags = Array.from(document.querySelectorAll('#removeTagsList .tag-badge'))
        .map(el => el.dataset.tag);
    const elseAddTags = Array.from(document.querySelectorAll('#elseAddTagsList .tag-badge'))
        .map(el => el.dataset.tag);
    const elseRemoveTags = Array.from(document.querySelectorAll('#elseRemoveTagsList .tag-badge'))
        .map(el => el.dataset.tag);
    
    if (addTags.length === 0 && removeTags.length === 0 && 
        elseAddTags.length === 0 && elseRemoveTags.length === 0) {
        showToast('At least one action (THEN or ELSE add/remove tags) is required', 'error');
        return null;
    }
    
    // Build schedule
    const enableSchedule = document.getElementById('enableSchedule')?.checked || false;
    const cronExpression = document.getElementById('cronExpression')?.value.trim() || '';
    
    return {
        name,
        description,
        enabled: true,
        conditions: {
            operator: primaryOperator,
            rules: conditions
        },
        actions: {
            add_tags: addTags,
            remove_tags: removeTags,
            else_add_tags: elseAddTags,
            else_remove_tags: elseRemoveTags
        },
        schedule: {
            enabled: enableSchedule,
            cron: cronExpression
        }
    };
}

/**
 * Load a template into the rule builder
 */
function loadTemplate(templateId) {
    const template = ruleTemplates[templateId];
    if (!template) {
        showToast('Template not found', 'error');
        return;
    }
    
    // Clear current form
    clearRuleForm();
    
    // Show rule builder if collapsed
    const ruleBuilderContainer = document.getElementById('ruleBuilderContainer');
    if (!ruleBuilderContainer.classList.contains('show')) {
        const builderCollapse = new bootstrap.Collapse(ruleBuilderContainer, {
            show: true
        });
    }
    
    // Load template data like a rule
    loadRuleIntoForm(template);
    
    
    console.log(`Loaded template: ${template.name}`);
}

/**
 * Load a rule into the form for editing
 */
function loadRuleIntoForm(rule) {
    // Basic info
    document.getElementById('ruleName').value = rule.name;
    document.getElementById('ruleDescription').value = rule.description || '';
    
    // Clear existing conditions and actions
    clearRuleForm(false);
    
    // Load conditions
    const primaryOperator = rule.conditions.operator || 'AND';
    
    rule.conditions.rules?.forEach((condition, index) => {
        addCondition();
        const conditionItems = document.querySelectorAll('.condition-item');
        const lastItem = conditionItems[conditionItems.length - 1];
        
        // Set field, operator, and value
        lastItem.querySelector('.condition-field').value = condition.field;
        lastItem.querySelector('.condition-operator').value = condition.operator;
        lastItem.querySelector('.condition-value').value = condition.value;
        
        // Set logical operator for non-first conditions
        if (index > 0) {
            const logicRadio = lastItem.querySelector(`input[value="${primaryOperator}"]`);
            if (logicRadio) {
                logicRadio.checked = true;
            }
        }
        
        // Trigger field change to update operator options
        const fieldSelect = lastItem.querySelector('.condition-field');
        fieldSelect.dispatchEvent(new Event('change'));
    });
    
    // Load THEN actions
    rule.actions.add_tags?.forEach(tag => {
        document.getElementById('addTagInput').value = tag;
        addActionTag('add');
    });
    
    rule.actions.remove_tags?.forEach(tag => {
        document.getElementById('removeTagInput').value = tag;
        addActionTag('remove');
    });
    
    // Load ELSE actions
    rule.actions.else_add_tags?.forEach(tag => {
        document.getElementById('elseAddTagInput').value = tag;
        addActionTag('elseAdd');
    });
    
    rule.actions.else_remove_tags?.forEach(tag => {
        document.getElementById('elseRemoveTagInput').value = tag;
        addActionTag('elseRemove');
    });
    
    // Load schedule
    document.getElementById('enableSchedule').checked = rule.schedule.enabled || false;
    document.getElementById('cronExpression').value = rule.schedule.cron || '';
    
    // Trigger schedule change event and validate cron if present
    document.getElementById('enableSchedule').dispatchEvent(new Event('change'));
    
    if (rule.schedule.enabled && rule.schedule.cron) {
        validateAndPreviewCron(rule.schedule.cron);
    }
}

/**
 * Clear the rule form
 */
function clearRuleForm(clearBasicInfo = true) {
    if (clearBasicInfo) {
        document.getElementById('ruleName').value = '';
        document.getElementById('ruleDescription').value = '';
    }
    
    // Clear conditions
    const container = document.getElementById('conditionsContainer');
    container.innerHTML = '';
    
    // Show placeholder
    const placeholder = document.getElementById('conditionsPlaceholder');
    if (placeholder) {
        placeholder.style.display = 'block';
    }
    
    // Reset logic preview
    updateLogicPreview();
    
    // Clear THEN actions
    document.getElementById('addTagsList').innerHTML = '';
    document.getElementById('removeTagsList').innerHTML = '';
    document.getElementById('addTagInput').value = '';
    document.getElementById('removeTagInput').value = '';
    
    // Clear ELSE actions
    document.getElementById('elseAddTagsList').innerHTML = '';
    document.getElementById('elseRemoveTagsList').innerHTML = '';
    document.getElementById('elseAddTagInput').value = '';
    document.getElementById('elseRemoveTagInput').value = '';
    
    // Clear schedule
    document.getElementById('enableSchedule').checked = false;
    document.getElementById('cronExpression').value = '';
    document.getElementById('schedulePreset').value = '';
    
    // Hide cron preview and errors
    hideCronPreview();
    hideCronError();
    
    // Trigger schedule change event
    document.getElementById('enableSchedule').dispatchEvent(new Event('change'));
    
    // Only clear currentEditingRule if we're doing a full clear
    if (clearBasicInfo) {
        currentEditingRule = null;
    }
}

/**
 * Load and display execution history
 */
async function loadExecutionHistory(ruleFilter = '') {
    try {
        const url = new URL('/conditional-tags/api/history', window.location.origin);
        if (ruleFilter) {
            url.searchParams.set('rule', ruleFilter);
        }
        
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to load execution history');
        
        const history = await response.json();
        console.log(`Loaded ${history.length} execution history entries`);
        
        displayExecutionHistory(history);
        updateHistoryFilter();
    } catch (error) {
        console.error('Error loading execution history:', error);
        showToast('Failed to load execution history: ' + error.message, 'error');
    }
}

/**
 * Display execution history in the table
 */
function displayExecutionHistory(history) {
    const tbody = document.getElementById('historyTableBody');
    if (!tbody) return;
    
    if (history.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted p-4">
                    No executions yet. Create and run some rules to see history here.
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = history.map(execution => {
        const timestamp = new Date(execution.timestamp);
        const matchedCount = execution.matched_vms ? execution.matched_vms.length : 0;
        const tagsAddedCount = Object.keys(execution.tags_added || {}).length;
        const tagsRemovedCount = Object.keys(execution.tags_removed || {}).length;
        const duration = execution.execution_time ? `${execution.execution_time.toFixed(2)}s` : 'N/A';
        
        // Determine result status
        let resultBadge = '';
        if (execution.dry_run) {
            resultBadge = '<span class="badge bg-info">Dry Run</span>';
        } else if (execution.errors && execution.errors.length > 0) {
            resultBadge = '<span class="badge bg-danger">Error</span>';
        } else if (matchedCount > 0) {
            resultBadge = '<span class="badge bg-success">Success</span>';
        } else {
            resultBadge = '<span class="badge bg-warning">No Matches</span>';
        }
        
        return `
            <tr>
                <td>
                    <strong>${escapeHtml(execution.rule_name || 'Unknown Rule')}</strong>
                    <br><small class="text-muted">${escapeHtml(execution.rule_id)}</small>
                </td>
                <td>
                    <small>${escapeHtml(timestamp.toLocaleString())}</small>
                </td>
                <td>${resultBadge}</td>
                <td>
                    <span class="badge bg-secondary">${matchedCount}</span>
                    ${matchedCount > 0 && execution.matched_vms ? 
                        `<br><small class="text-muted">${escapeHtml(execution.matched_vms.slice(0, 3).join(', '))}${execution.matched_vms.length > 3 ? '...' : ''}</small>` : 
                        ''
                    }
                </td>
                <td>
                    ${tagsAddedCount > 0 ? 
                        `<span class="badge bg-success">${tagsAddedCount}</span>` : 
                        '<span class="text-muted">-</span>'
                    }
                </td>
                <td>
                    ${tagsRemovedCount > 0 ? 
                        `<span class="badge bg-danger">${tagsRemovedCount}</span>` : 
                        '<span class="text-muted">-</span>'
                    }
                </td>
                <td><small>${duration}</small></td>
            </tr>
        `;
    }).join('');
}

/**
 * Update the history filter dropdown with available rules
 */
function updateHistoryFilter() {
    const filterSelect = document.getElementById('historyRuleFilter');
    if (!filterSelect || !rules) return;
    
    // Clear existing options except the first one
    while (filterSelect.children.length > 1) {
        filterSelect.removeChild(filterSelect.lastChild);
    }
    
    // Add rule options
    rules.forEach(rule => {
        const option = document.createElement('option');
        option.value = rule.id;
        option.textContent = rule.name;
        filterSelect.appendChild(option);
    });
}

/**
 * Validate and preview cron expression
 */
function validateAndPreviewCron(cronExpression) {
    try {
        const validation = validateCronExpression(cronExpression);
        
        if (validation.isValid) {
            showCronPreview(validation.nextRuns, validation.description);
            hideCronError();
        } else {
            showCronError(validation.error);
            hideCronPreview();
        }
    } catch (error) {
        showCronError('Invalid cron expression format');
        hideCronPreview();
    }
}

/**
 * Basic cron expression validator and next run calculator
 */
function validateCronExpression(cron) {
    const parts = cron.trim().split(/\s+/);
    
    if (parts.length !== 5) {
        return {
            isValid: false,
            error: 'Cron expression must have exactly 5 parts: minute hour day month weekday'
        };
    }
    
    const [minute, hour, day, month, weekday] = parts;
    
    // Basic validation patterns
    const patterns = {
        minute: /^(\*|([0-5]?[0-9])|(\*\/[0-9]+)|([0-5]?[0-9]-[0-5]?[0-9])|([0-5]?[0-9](,[0-5]?[0-9])*))$/,
        hour: /^(\*|([01]?[0-9]|2[0-3])|(\*\/[0-9]+)|([01]?[0-9]|2[0-3])-([01]?[0-9]|2[0-3])|([01]?[0-9]|2[0-3])(,([01]?[0-9]|2[0-3]))*)$/,
        day: /^(\*|([1-9]|[12][0-9]|3[01])|(\*\/[0-9]+)|([1-9]|[12][0-9]|3[01])-([1-9]|[12][0-9]|3[01])|([1-9]|[12][0-9]|3[01])(,([1-9]|[12][0-9]|3[01]))*)$/,
        month: /^(\*|([1-9]|1[0-2])|(\*\/[0-9]+)|([1-9]|1[0-2])-([1-9]|1[0-2])|([1-9]|1[0-2])(,([1-9]|1[0-2]))*)$/,
        weekday: /^(\*|[0-6]|(\*\/[0-9]+)|[0-6]-[0-6]|[0-6](,[0-6])*)$/
    };
    
    // Validate each part
    if (!patterns.minute.test(minute)) {
        return { isValid: false, error: 'Invalid minute field (0-59)' };
    }
    if (!patterns.hour.test(hour)) {
        return { isValid: false, error: 'Invalid hour field (0-23)' };
    }
    if (!patterns.day.test(day)) {
        return { isValid: false, error: 'Invalid day field (1-31)' };
    }
    if (!patterns.month.test(month)) {
        return { isValid: false, error: 'Invalid month field (1-12)' };
    }
    if (!patterns.weekday.test(weekday)) {
        return { isValid: false, error: 'Invalid weekday field (0-6, 0=Sunday)' };
    }
    
    // Generate description and next runs
    const description = describeCronExpression(minute, hour, day, month, weekday);
    const nextRuns = calculateNextRuns(minute, hour, day, month, weekday);
    
    return {
        isValid: true,
        description,
        nextRuns
    };
}

/**
 * Generate human-readable description of cron expression
 */
function describeCronExpression(minute, hour, day, month, weekday) {
    // Common patterns
    if (minute === '0' && hour === '0' && day === '*' && month === '*' && weekday === '*') {
        return 'Daily at midnight';
    }
    if (minute === '0' && hour === '0' && day === '*' && month === '*' && weekday === '0') {
        return 'Weekly on Sunday at midnight';
    }
    if (minute === '0' && hour === '0' && day === '1' && month === '*' && weekday === '*') {
        return 'Monthly on the 1st at midnight';
    }
    if (minute === '0' && hour.startsWith('*/') && day === '*' && month === '*' && weekday === '*') {
        const hours = hour.split('/')[1];
        return `Every ${hours} hours`;
    }
    if (minute.startsWith('*/') && hour === '*' && day === '*' && month === '*' && weekday === '*') {
        const minutes = minute.split('/')[1];
        return `Every ${minutes} minutes`;
    }
    
    // Generic description
    let desc = 'Runs ';
    if (minute === '*') desc += 'every minute';
    else if (minute.includes('/')) desc += `every ${minute.split('/')[1]} minutes`;
    else desc += `at minute ${minute}`;
    
    if (hour !== '*') {
        if (hour.includes('/')) desc += `, every ${hour.split('/')[1]} hours`;
        else desc += `, at hour ${hour}`;
    }
    
    if (day !== '*') {
        desc += `, on day ${day}`;
    }
    
    if (weekday !== '*') {
        const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        desc += `, on ${days[parseInt(weekday)] || `weekday ${weekday}`}`;
    }
    
    return desc;
}

/**
 * Calculate next few run times (simplified)
 */
function calculateNextRuns(minute, hour, day, month, weekday) {
    const now = new Date();
    const nextRuns = [];
    
    // This is a simplified calculator for common patterns
    // For production, you'd want a more robust cron parser library
    
    try {
        for (let i = 0; i < 5; i++) {
            const nextRun = new Date(now);
            
            // Simple calculation for common cases
            if (hour.includes('*/')) {
                const hourInterval = parseInt(hour.split('/')[1]);
                nextRun.setHours(now.getHours() + (i + 1) * hourInterval);
                nextRun.setMinutes(parseInt(minute) || 0);
                nextRun.setSeconds(0);
            } else if (minute.includes('*/')) {
                const minuteInterval = parseInt(minute.split('/')[1]);
                nextRun.setMinutes(now.getMinutes() + (i + 1) * minuteInterval);
                nextRun.setSeconds(0);
            } else {
                // Daily at specific time
                nextRun.setDate(now.getDate() + i + 1);
                nextRun.setHours(parseInt(hour) || 0);
                nextRun.setMinutes(parseInt(minute) || 0);
                nextRun.setSeconds(0);
            }
            
            nextRuns.push(nextRun.toLocaleString());
        }
    } catch (error) {
        // Fallback for complex expressions
        return ['Next run calculation not available for complex expressions'];
    }
    
    return nextRuns;
}

/**
 * Show cron preview
 */
function showCronPreview(nextRuns, description) {
    const preview = document.getElementById('cronPreview');
    const nextRunsDiv = document.getElementById('cronNextRuns');
    
    if (preview && nextRunsDiv) {
        nextRunsDiv.innerHTML = `
            <div class="mb-1"><strong>${escapeHtml(description)}</strong></div>
            ${nextRuns.map(run => `<div class="text-muted">• ${escapeHtml(run)}</div>`).join('')}
        `;
        preview.style.display = 'block';
    }
}

/**
 * Hide cron preview
 */
function hideCronPreview() {
    const preview = document.getElementById('cronPreview');
    if (preview) {
        preview.style.display = 'none';
    }
}

/**
 * Show cron error
 */
function showCronError(errorMessage) {
    const error = document.getElementById('cronError');
    const errorMsg = document.getElementById('cronErrorMessage');
    
    if (error && errorMsg) {
        errorMsg.textContent = errorMessage;
        error.style.display = 'block';
    }
}

/**
 * Hide cron error
 */
function hideCronError() {
    const error = document.getElementById('cronError');
    if (error) {
        error.style.display = 'none';
    }
}

/**
 * Import rules from uploaded JSON file
 */
async function importRules(file) {
    try {
        showToast('Importing rules...', 'info');
        
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/conditional-tags/api/import-rules', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast(result.message, 'success');
            // Reload rules to show imported ones
            await loadRules();
        } else {
            let errorMessage = result.error || 'Import failed';
            if (result.details && result.details.failures.length > 0) {
                errorMessage += '\n\nFailures:\n• ' + result.details.failures.join('\n• ');
            }
            showToast(errorMessage, 'error');
        }
    } catch (error) {
        console.error('Error importing rules:', error);
        showToast('Failed to import rules: ' + error.message, 'error');
    } finally {
        // Clear the file input
        document.getElementById('importRulesInput').value = '';
    }
}

/**
 * Utility function to escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}