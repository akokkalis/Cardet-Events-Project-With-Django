/**
 * CSV Import Progress Tracker
 * Handles background CSV import with real-time progress updates
 * Similar to https://data-star.dev/examples/progress_bar
 */

class CSVImportProgress {
    constructor() {
        this.importId = null;
        this.pollInterval = null;
        this.isPolling = false;
        this.maxRetries = 3;
        this.retryCount = 0;
    }

    // Initialize the progress modal
    createProgressModal() {
        const modalHTML = `
            <div id="import-progress-modal" class="fixed inset-0 bg-gray-600 bg-opacity-75 flex items-center justify-center z-50" style="display: none;">
                <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
                    <div class="p-6">
                        <div class="flex items-center justify-between mb-4">
                            <h3 class="text-lg font-medium text-gray-900">
                                <i class="fas fa-upload text-blue-500 mr-2"></i>
                                Importing Participants
                            </h3>
                            <div class="text-sm text-gray-500" id="import-status">
                                Starting...
                            </div>
                        </div>
                        
                        <!-- Progress Bar -->
                        <div class="mb-4">
                            <div class="flex justify-between text-sm text-gray-600 mb-2">
                                <span id="progress-text">Preparing import...</span>
                                <span id="progress-percentage">0%</span>
                            </div>
                            <div class="w-full bg-gray-200 rounded-full h-3">
                                <div id="progress-bar" class="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full transition-all duration-500 ease-out" style="width: 0%"></div>
                            </div>
                        </div>
                        
                        <!-- Stats -->
                        <div class="grid grid-cols-3 gap-4 text-sm">
                            <div class="text-center">
                                <div class="font-semibold text-green-600" id="successful-count">0</div>
                                <div class="text-gray-500">Successful</div>
                            </div>
                            <div class="text-center">
                                <div class="font-semibold text-red-600" id="failed-count">0</div>
                                <div class="text-gray-500">Failed</div>
                            </div>
                            <div class="text-center">
                                <div class="font-semibold text-gray-600" id="total-count">0</div>
                                <div class="text-gray-500">Total</div>
                            </div>
                        </div>
                        
                        <!-- Recent Errors -->
                        <div id="error-container" class="mt-4" style="display: none;">
                            <h4 class="text-sm font-medium text-gray-700 mb-2">Recent Errors:</h4>
                            <div id="error-list" class="text-xs text-red-600 bg-red-50 rounded p-2 max-h-20 overflow-y-auto"></div>
                        </div>
                        
                        <!-- Spinning Animation -->
                        <div class="flex items-center justify-center mt-4">
                            <div id="spinner" class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
                            <span class="ml-2 text-sm text-gray-600">Processing in background...</span>
                        </div>
                        
                        <!-- Completion Message -->
                        <div id="completion-message" class="mt-4 text-center" style="display: none;">
                            <div class="text-green-600 font-medium">
                                <i class="fas fa-check-circle mr-2"></i>
                                Import completed successfully!
                            </div>
                            <div class="text-sm text-gray-500 mt-1">
                                Redirecting to event page...
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if present
        const existingModal = document.getElementById('import-progress-modal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Add modal to body
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }

    // Show the progress modal
    showModal() {
        const modal = document.getElementById('import-progress-modal');
        if (modal) {
            modal.style.display = 'flex';
            // Add fade-in animation
            modal.classList.add('animate-fade-in');
        }
    }

    // Hide the progress modal
    hideModal() {
        const modal = document.getElementById('import-progress-modal');
        if (modal) {
            modal.style.display = 'none';
            modal.classList.remove('animate-fade-in');
        }
    }

    // Hide the import participants modal (from the main template)
    hideImportModal() {
        const importModal = document.getElementById('importParticipantsModal');
        if (importModal) {
            importModal.classList.add('hidden');
        }
    }

    // Start tracking import progress
    startImport(importId, totalRows) {
        console.log('CSV Import Progress: startImport called with', importId, totalRows);
        this.importId = importId;
        this.retryCount = 0;
        
        // Create and show modal
        console.log('CSV Import Progress: Creating modal');
        this.createProgressModal();
        this.showModal();
        
        // Update initial values
        document.getElementById('total-count').textContent = totalRows;
        document.getElementById('import-status').textContent = 'In Progress';
        
        // Start polling for progress
        console.log('CSV Import Progress: Starting polling');
        this.startPolling();
    }

    // Test function to manually show progress bar (for debugging)
    testProgressBar() {
        console.log('CSV Import Progress: Testing progress bar');
        this.startImport('test-123', 100);
        
        // Simulate progress updates
        setTimeout(() => {
            this.updateProgress({
                status: 'in_progress',
                progress_percentage: 25,
                processed_rows: 25,
                total_rows: 100,
                successful_imports: 23,
                failed_imports: 2,
                error_messages: ['Test error message']
            });
        }, 2000);
        
        setTimeout(() => {
            this.updateProgress({
                status: 'completed',
                progress_percentage: 100,
                processed_rows: 100,
                total_rows: 100,
                successful_imports: 98,
                failed_imports: 2,
                redirect_url: null
            });
        }, 5000);
    }

    // Start polling the progress endpoint
    startPolling() {
        if (this.isPolling) return;
        
        this.isPolling = true;
        this.pollInterval = setInterval(() => {
            this.checkProgress();
        }, 1000); // Poll every second
    }

    // Stop polling
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
        this.isPolling = false;
    }

    // Check import progress via AJAX
    async checkProgress() {
        if (!this.importId) return;

        try {
            const response = await fetch(`/import-progress/${this.importId}/`, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.updateProgress(data);
            this.retryCount = 0; // Reset retry count on success

        } catch (error) {
            console.error('Error checking import progress:', error);
            this.retryCount++;
            
            if (this.retryCount >= this.maxRetries) {
                this.handleError('Failed to check import progress. Please refresh the page.');
            }
        }
    }

    // Update the progress UI
    updateProgress(data) {
        const {
            status,
            progress_percentage,
            processed_rows,
            total_rows,
            successful_imports,
            failed_imports,
            error_messages,
            redirect_url
        } = data;

        // Update progress bar
        const progressBar = document.getElementById('progress-bar');
        const progressPercentage = document.getElementById('progress-percentage');
        const progressText = document.getElementById('progress-text');
        
        if (progressBar && progressPercentage && progressText) {
            progressBar.style.width = `${progress_percentage}%`;
            progressPercentage.textContent = `${Math.round(progress_percentage)}%`;
            progressText.textContent = `Processing row ${processed_rows} of ${total_rows}`;
        }

        // Update counts
        document.getElementById('successful-count').textContent = successful_imports || 0;
        document.getElementById('failed-count').textContent = failed_imports || 0;
        
        // Update status
        const statusElement = document.getElementById('import-status');
        if (statusElement) {
            statusElement.textContent = status === 'in_progress' ? 'In Progress' : 
                                      status === 'completed' ? 'Completed' : 
                                      status === 'failed' ? 'Failed' : status;
        }

        // Show errors if any
        if (error_messages && error_messages.length > 0) {
            this.showErrors(error_messages);
        }

        // Handle completion
        if (status === 'completed' || status === 'failed') {
            this.handleCompletion(status, redirect_url, successful_imports, failed_imports);
        }
    }

    // Show error messages
    showErrors(errors) {
        const errorContainer = document.getElementById('error-container');
        const errorList = document.getElementById('error-list');
        
        if (errorContainer && errorList && errors.length > 0) {
            errorList.innerHTML = errors.map(error => `<div class="mb-1">${error}</div>`).join('');
            errorContainer.style.display = 'block';
        }
    }

    // Handle import completion
    handleCompletion(status, redirectUrl, successful, failed) {
        this.stopPolling();
        
        const spinner = document.getElementById('spinner');
        const completionMessage = document.getElementById('completion-message');
        
        if (spinner) spinner.style.display = 'none';
        
        if (status === 'completed') {
            if (completionMessage) {
                completionMessage.style.display = 'block';
            }
            
            // Show success message
            this.showSuccessMessage(successful, failed);
            
            // Redirect after delay
            setTimeout(() => {
                if (redirectUrl) {
                    window.location.href = redirectUrl;
                } else {
                    this.hideModal();
                    location.reload();
                }
            }, 2000);
            
        } else if (status === 'failed') {
            this.handleError('Import failed. Please check the errors and try again.');
        }
    }

    // Show success message
    showSuccessMessage(successful, failed) {
        const message = failed > 0 ? 
            `Import completed with ${successful} successful and ${failed} failed imports.` :
            `Successfully imported ${successful} participants!`;
            
        // You can integrate with your existing notification system here
        console.log(message);
    }

    // Handle errors
    handleError(message) {
        this.stopPolling();
        
        const spinner = document.getElementById('spinner');
        const completionMessage = document.getElementById('completion-message');
        
        if (spinner) spinner.style.display = 'none';
        if (completionMessage) {
            completionMessage.innerHTML = `
                <div class="text-red-600 font-medium">
                    <i class="fas fa-exclamation-circle mr-2"></i>
                    ${message}
                </div>
                <button onclick="csvImportProgress.hideModal()" class="mt-2 px-4 py-2 bg-gray-300 text-gray-700 rounded hover:bg-gray-400">
                    Close
                </button>
            `;
            completionMessage.style.display = 'block';
        }
    }

    // Handle CSV form submission
    handleFormSubmit(event) {
        console.log('CSV Import Progress: handleFormSubmit called');
        event.preventDefault();
        
        const form = event.target;
        const formData = new FormData(form);
        
        // Check if file is selected
        const csvFile = formData.get('csv_file');
        console.log('CSV Import Progress: File selected:', csvFile);
        
        if (!csvFile || csvFile.size === 0) {
            alert('Please select a CSV file to upload.');
            return;
        }

        // Validate file type
        if (!csvFile.name.toLowerCase().endsWith('.csv')) {
            alert('Please select a valid CSV file.');
            return;
        }

        // Validate file size (5MB limit)
        if (csvFile.size > 5 * 1024 * 1024) {
            alert('File size must be less than 5MB.');
            return;
        }

        console.log('CSV Import Progress: Validation passed, hiding modal');
        // Hide the import modal
        this.hideImportModal();

        console.log('CSV Import Progress: Starting AJAX submission');
        // Submit form via AJAX
        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            },
        })
        .then(response => {
            console.log('CSV Import Progress: Response received', response);
            return response.json();
        })
        .then(data => {
            console.log('CSV Import Progress: JSON data received', data);
            if (data.status === 'started') {
                this.startImport(data.import_id, data.total_rows);
            } else {
                throw new Error(data.message || 'Import failed to start');
            }
        })
        .catch(error => {
            console.error('Error starting import:', error);
            alert('Error starting import: ' + error.message);
        });
    }
}

// Global instance
const csvImportProgress = new CSVImportProgress();

// Global test function for debugging
window.testCSVProgressBar = function() {
    console.log('Testing CSV Import Progress Bar...');
    csvImportProgress.testProgressBar();
};

// Simple function to just show the modal immediately
window.showProgressModal = function() {
    console.log('Showing progress modal...');
    csvImportProgress.createProgressModal();
    csvImportProgress.showModal();
    
    // Set some initial values
    document.getElementById('total-count').textContent = '100';
    document.getElementById('successful-count').textContent = '45';
    document.getElementById('failed-count').textContent = '3';
    document.getElementById('progress-percentage').textContent = '48%';
    document.getElementById('progress-text').textContent = 'Processing row 48 of 100';
    document.getElementById('progress-bar').style.width = '48%';
    document.getElementById('import-status').textContent = 'In Progress';
    
    console.log('Progress modal should now be visible!');
};

// Super simple test modal to check if modals work at all
window.testSimpleModal = function() {
    console.log('Creating super simple modal...');
    
    // Remove any existing test modal
    const existing = document.getElementById('simple-test-modal');
    if (existing) {
        existing.remove();
    }
    
    // Create the simplest possible modal
    const modalHTML = `
        <div id="simple-test-modal" style="
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 99999;
        ">
            <div style="
                background: white;
                padding: 40px;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            ">
                <h2 style="color: #333; margin-bottom: 20px;">🎉 Modal Test Success!</h2>
                <p style="color: #666; margin-bottom: 20px;">If you can see this, modals work on your page.</p>
                <button onclick="document.getElementById('simple-test-modal').remove()" style="
                    background: #3b82f6;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    cursor: pointer;
                ">Close</button>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    console.log('Simple modal created and should be visible!');
};

// Debug function to check for common issues
window.debugModalIssues = function() {
    console.log('=== DEBUGGING MODAL ISSUES ===');
    
    // Check if body exists
    console.log('Document body:', document.body);
    
    // Check current z-index issues
    const allElements = document.querySelectorAll('*');
    const highZIndexElements = [];
    allElements.forEach(el => {
        const zIndex = window.getComputedStyle(el).zIndex;
        if (zIndex && zIndex !== 'auto' && parseInt(zIndex) > 9000) {
            highZIndexElements.push({element: el, zIndex: zIndex});
        }
    });
    console.log('Elements with high z-index (>9000):', highZIndexElements);
    
    // Check for existing modals
    const existingModals = document.querySelectorAll('[id*="modal"], [class*="modal"]');
    console.log('Existing modal elements:', existingModals);
    
    // Check if our progress modal exists
    const progressModal = document.getElementById('import-progress-modal');
    console.log('Our progress modal exists:', progressModal);
    
    if (progressModal) {
        const styles = window.getComputedStyle(progressModal);
        console.log('Progress modal display:', styles.display);
        console.log('Progress modal z-index:', styles.zIndex);
        console.log('Progress modal position:', styles.position);
    }
    
    // Test basic HTML insertion
    console.log('Testing basic HTML insertion...');
    const testDiv = document.createElement('div');
    testDiv.innerHTML = '<p style="color: red; font-size: 20px;">TEST DIV INSERTED</p>';
    testDiv.style.position = 'fixed';
    testDiv.style.top = '10px';
    testDiv.style.right = '10px';
    testDiv.style.zIndex = '99999';
    testDiv.style.background = 'yellow';
    testDiv.style.padding = '10px';
    testDiv.id = 'debug-test-div';
    
    // Remove existing test div
    const existing = document.getElementById('debug-test-div');
    if (existing) existing.remove();
    
    document.body.appendChild(testDiv);
    console.log('Yellow test div should appear in top-right corner');
    
    setTimeout(() => {
        testDiv.remove();
        console.log('Test div removed');
    }, 3000);
    
    console.log('=== END DEBUGGING ===');
};

// Function to hide the progress modal
window.hideProgressModal = function() {
    console.log('Hiding progress modal...');
    csvImportProgress.hideModal();
};

// Demonstration function with animated progress
window.demoProgressBar = function() {
    console.log('Starting progress bar demonstration...');
    
    // Show the modal first
    csvImportProgress.createProgressModal();
    csvImportProgress.showModal();
    
    // Simulate progress from 0 to 100%
    let progress = 0;
    const totalRows = 100;
    
    const interval = setInterval(() => {
        progress += Math.random() * 10; // Random progress increments
        if (progress > 100) progress = 100;
        
        const processed = Math.floor(progress);
        const successful = Math.floor(progress * 0.95); // 95% success rate
        const failed = processed - successful;
        
        // Update progress bar
        document.getElementById('progress-bar').style.width = `${progress}%`;
        document.getElementById('progress-percentage').textContent = `${Math.round(progress)}%`;
        document.getElementById('progress-text').textContent = `Processing row ${processed} of ${totalRows}`;
        document.getElementById('successful-count').textContent = successful;
        document.getElementById('failed-count').textContent = failed;
        document.getElementById('total-count').textContent = totalRows;
        
        if (progress >= 100) {
            clearInterval(interval);
            document.getElementById('import-status').textContent = 'Completed';
            document.getElementById('spinner').style.display = 'none';
            document.getElementById('completion-message').style.display = 'block';
            console.log('Demo completed!');
        }
    }, 200); // Update every 200ms
};

// Test function to manually trigger form submission (for debugging)
window.testFormSubmission = function() {
    console.log('Testing form submission manually...');
    const form = document.getElementById('csv-import-form');
    if (form) {
        console.log('Form found, triggering submission handler...');
        // Create a mock file for testing
        const mockEvent = {
            preventDefault: () => console.log('preventDefault called'),
            target: form
        };
        
        // We can't create a real file easily, so let's just test the modal creation
        csvImportProgress.startImport('manual-test', 50);
    } else {
        console.log('Form not found, cannot test submission');
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('CSV Import Progress: DOM loaded');
    
    // Try multiple ways to find the form
    const csvForm = document.getElementById('csv-import-form');
    const allForms = document.querySelectorAll('form');
    const modalDiv = document.getElementById('importParticipantsModal');
    
    console.log('CSV Import Progress: Form found:', csvForm);
    console.log('CSV Import Progress: All forms count:', allForms.length);
    console.log('CSV Import Progress: Modal found:', modalDiv);
    
    // List all form IDs for debugging
    allForms.forEach((form, index) => {
        console.log(`Form ${index}: ID="${form.id}", action="${form.action}"`);
    });
    
    if (csvForm) {
        console.log('CSV Import Progress: Adding event listener to form');
        csvForm.addEventListener('submit', (event) => {
            console.log('CSV Import Progress: Form submitted');
            csvImportProgress.handleFormSubmit(event);
        });
    } else {
        console.warn('CSV Import Progress: csv-import-form not found');
        
        // Try to find it after a delay (in case of timing issues)
        setTimeout(() => {
            const delayedForm = document.getElementById('csv-import-form');
            console.log('CSV Import Progress: Delayed search found:', delayedForm);
            if (delayedForm) {
                console.log('CSV Import Progress: Adding delayed event listener');
                delayedForm.addEventListener('submit', (event) => {
                    console.log('CSV Import Progress: Delayed form submitted');
                    csvImportProgress.handleFormSubmit(event);
                });
            }
        }, 1000);
    }
    
    // Add CSS styles
    addProgressStyles();
});

// Add CSS styles for animations
function addProgressStyles() {
    if (!document.getElementById('progress-styles')) {
        const styleElement = document.createElement('style');
        styleElement.id = 'progress-styles';
        styleElement.textContent = `
            .animate-fade-in {
                animation: fadeIn 0.3s ease-in-out;
            }

            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }

            .animate-spin {
                animation: spin 1s linear infinite;
            }

            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(styleElement);
    }
} 