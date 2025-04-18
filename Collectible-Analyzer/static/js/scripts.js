$(document).ready(function() {
    // Drag and Drop for Upload Area
    const uploadArea = $('#uploadArea');
    const fileInput = $('#image');
    const submitBtn = $('#submitBtn');

    uploadArea.on('dragover', function(e) {
        e.preventDefault();
        $(this).addClass('dragover');
    });

    uploadArea.on('dragleave', function(e) {
        e.preventDefault();
        $(this).removeClass('dragover');
    });

    uploadArea.on('drop', function(e) {
        e.preventDefault();
        $(this).removeClass('dragover');
        const files = e.originalEvent.dataTransfer.files;
        if (files.length) {
            fileInput[0].files = files;
            validateForm();
        }
    });

    fileInput.on('change', validateForm);

    function validateForm() {
        if (fileInput[0].files.length > 0) {
            submitBtn.prop('disabled', false);
        } else {
            submitBtn.prop('disabled', true);
        }
    }

    // Show Loading Spinner on Form Submit and Poll Status
    $('#uploadForm').on('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        $('#loadingModal').modal('show');
        $('#loadingMessage').text('Uploading and processing image...');

        // Submit form via AJAX
        $.ajax({
            url: '/upload',
            type: 'POST',
            data: formData,
            contentType: false,
            processData: false,
            timeout: 300000, // Set a long timeout (5 minutes) for the initial request
            success: function(response) {
                // Use the task_id from server response for polling
                const taskId = response.task_id;
                $('#loadingMessage').text(response.message);
                // Start polling status with the server-provided task ID
                pollStatus(taskId);
            },
            error: function(xhr, status, error) {
                $('#loadingMessage').text('Error occurred during upload: ' + (error || 'Unknown error'));
                setTimeout(function() {
                    $('#loadingModal').modal('hide');
                }, 5000);
            }
        });
    });

    function pollStatus(taskId) {
        let pollCount = 0;
        const maxPollCount = 300; // Allow polling for up to 10 minutes (300 * 2s)
        const interval = setInterval(function() {
            pollCount++;
            if (pollCount > maxPollCount) {
                clearInterval(interval);
                $('#loadingMessage').text('Processing is taking too long. Please check back later.');
                setTimeout(function() {
                    $('#loadingModal').modal('hide');
                }, 5000);
                return;
            }
            $.ajax({
                url: '/status/' + taskId,
                type: 'GET',
                timeout: 5000, // 5 seconds timeout per poll request
                success: function(data) {
                    $('#loadingMessage').text(data.message);
                    if (data.status === 'completed') {
                        clearInterval(interval);
                        $('#loadingModal').modal('hide');
                        // Redirect to history or results page
                        window.location.href = '/history';
                    } else if (data.status === 'error') {
                        clearInterval(interval);
                        $('#loadingMessage').text('Error: ' + data.message);
                        setTimeout(function() {
                            $('#loadingModal').modal('hide');
                        }, 5000);
                    }
                },
                error: function() {
                    $('#loadingMessage').text('Error checking status. Retrying...');
                    // Don't clear interval on error, keep polling until maxPollCount
                }
            });
        }, 2000); // Poll every 2 seconds
    }

    // Table Sorting
    $('.sortable').on('click', function() {
        const column = $(this).data('sort');
        const table = $('#historyTable');
        const rows = table.find('tr').get();

        const isAsc = !$(this).hasClass('sort-asc');
        $('.sortable').removeClass('sort-asc sort-desc');
        $(this).addClass(isAsc ? 'sort-asc' : 'sort-desc');

        rows.sort(function(a, b) {
            const aValue = $(a).children('td').eq($(this).index()).text();
            const bValue = $(b).children('td').eq($(this).index()).text();
            if (column === 'id') {
                return isAsc ? Number(aValue) - Number(bValue) : Number(bValue) - Number(aValue);
            } else if (column === 'timestamp') {
                return isAsc ? new Date(aValue) - new Date(bValue) : new Date(bValue) - new Date(aValue);
            } else {
                return isAsc ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
            }
        }.bind(this));

        table.children('tbody').empty().append(rows);
    });

    // Table Filtering
    $('#itemTypeFilter').on('change', function() {
        const filter = $(this).val().toLowerCase();
        $('#historyTable tr').each(function() {
            const itemType = $(this).data('item-type') || '';
            if (filter === '' || itemType === filter) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });
    });

    // Image Preview Modal
    $('.image-preview').on('click', function(e) {
        e.preventDefault();
        const imageSrc = $(this).data('image');
        $('#previewImage').attr('src', imageSrc);
        $('#imagePreviewModal').modal('show');
    });

    // Export Feedback
    $('a[href*="/export"]').on('click', function() {
        setTimeout(function() {
            alert('Export completed successfully!');
        }, 1000);
    });
});