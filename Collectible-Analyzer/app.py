from flask import Flask, request, render_template, redirect, url_for, send_file, jsonify
from modules.controller import Controller
from modules.data_manager import DataManager
import os
import logging
from datetime import datetime
import uuid
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize controller and data manager
controller = Controller()
data_manager = DataManager()

# In-memory storage for task status
task_status = {}

@app.route('/')
def index():
    """Render the home page with upload form."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_image():
    """Handle image upload and process it."""
    try:
        # Check if a file was uploaded
        if 'image' not in request.files:
            return render_template('index.html', error="No image uploaded")
        
        file = request.files['image']
        if file.filename == '':
            return render_template('index.html', error="No image selected")

        # Get item type from form
        item_type = request.form.get('item_type', 'baseball card')

        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        task_status[task_id] = {"status": "starting", "message": "Upload started", "result": None, "image_path": ""}

        # Save the uploaded file
        filename = file.filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        logger.info(f"Saved uploaded image: {file_path}")

        # Update status to processing
        task_status[task_id]["status"] = "processing"
        task_status[task_id]["message"] = "Processing image..."
        task_status[task_id]["image_path"] = file_path

        # Function to process item in background
        def process_in_background(task_id, file_path, item_type):
            try:
                # process_item now returns a list of results
                results_list = controller.process_item(file_path, item_type, task_id=task_id, task_status=task_status)
                
                # Update status upon successful completion
                task_status[task_id]["status"] = "completed"
                # Message is updated inside controller
                task_status[task_id]["message"] = "Processing complete." 
                task_status[task_id]["result"] = results_list # Store the list of results
                logger.info(f"Completed processing for task {task_id}, found {len(results_list)} items.")
            except Exception as e:
                logger.error(f"Error processing task {task_id}: {str(e)}")
                # Status should be updated inside controller.process_item on error
                if task_id in task_status:
                    task_status[task_id]["status"] = "error"
                    # Ensure message reflects error if not already set
                    if not task_status[task_id].get("message", "").startswith("Error:"):
                        task_status[task_id]["message"] = f"Error: {str(e)}"

        # Return task ID immediately for AJAX requests and start background processing
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Start background thread for processing
            thread = threading.Thread(target=process_in_background, args=(task_id, file_path, item_type))
            thread.daemon = True  # Ensure thread exits if app shuts down
            thread.start()
            return jsonify({"task_id": task_id, "status": "processing", "message": "Processing started"})

        # For non-AJAX (fallback), process and render results
        result = controller.process_item(file_path, item_type)
        task_status[task_id]["status"] = "completed"
        task_status[task_id]["message"] = "Processing complete"
        task_status[task_id]["result"] = result

        return render_template('results.html', result=result, image_path=url_for('static', filename=f'uploads/{filename}'), task_id=task_id)

    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        if 'task_id' in locals():
            task_status[task_id]["status"] = "error"
            task_status[task_id]["message"] = f"Error: {str(e)}"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"task_id": task_id if 'task_id' in locals() else "unknown", "status": "error", "message": f"Error: {str(e)}"})
        return render_template('index.html', error=f"Error processing image: {str(e)}")

@app.route('/status/<task_id>')
def get_status(task_id):
    """Return the status of a processing task."""
    status_info = task_status.get(task_id, {"status": "unknown", "message": "Task not found"})
    return jsonify(status_info)

@app.route('/history')
def history():
    """Display all analysis results from the database."""
    try:
        results = data_manager.get_all_results()
        return render_template('history.html', results=results)
    except Exception as e:
        logger.error(f"Error fetching history: {str(e)}")
        return render_template('history.html', results=[], error=f"Error fetching history: {str(e)}")

@app.route('/export')
@app.route('/export/<item_type>')
def export_csv(item_type=None):
    """Export results to CSV and serve for download."""
    try:
        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"results_{timestamp}.csv" if not item_type else f"wine_bottles_{timestamp}.csv"
        output_path = os.path.join("data/exports", filename)

        # Export using DataManager
        result = data_manager.export_to_csv(output_path, item_type)
        if not result:
            return render_template('history.html', results=data_manager.get_all_results(), error="No results to export")

        # Serve the file for download
        return send_file(output_path, as_attachment=True, download_name=filename)
    except Exception as e:
        logger.error(f"Error exporting CSV: {str(e)}")
        return render_template('history.html', results=data_manager.get_all_results(), error=f"Error exporting CSV: {str(e)}")

@app.route('/delete/<int:result_id>', methods=['POST'])
def delete_item(result_id):
    """Handle deletion of a single history item."""
    try:
        success = data_manager.delete_result_by_id(result_id)
        if success:
            # Optional: Add flash message for success
            pass
        else:
            # Optional: Add flash message for error
            pass
    except Exception as e:
        logger.error(f"Error trying to delete item {result_id}: {str(e)}")
        # Optional: Add flash message for error
    return redirect(url_for('history'))

@app.route('/clear_history', methods=['POST'])
def clear_history():
    """Handle deletion of all history items."""
    try:
        success = data_manager.delete_all_results()
        if success:
            # Optional: Add flash message
            pass
        else:
            # Optional: Add flash message
            pass
    except Exception as e:
        logger.error(f"Error trying to clear history: {str(e)}")
        # Optional: Add flash message
    return redirect(url_for('history'))

@app.route('/catalog')
def catalog():
    """Display the editable card catalog."""
    try:
        # Fetch only baseball cards for the catalog? Or all items?
        # Assuming catalog is primarily for cards for now.
        all_results = data_manager.get_all_results()
        # Filter for baseball cards if needed, or adjust template logic
        card_results = [r for r in all_results if r.get('item_type', '').lower() == 'baseball card']
        return render_template('catalog.html', results=card_results)
    except Exception as e:
        logger.error(f"Error fetching catalog data: {str(e)}")
        # Render catalog page with an error message
        return render_template('catalog.html', results=[], error=f"Error loading catalog: {str(e)}")

@app.route('/update_card/<int:result_id>', methods=['POST'])
def update_card(result_id):
    """Handle updates to card details from the catalog."""
    if not request.is_json:
        return jsonify({"success": False, "message": "Invalid request format, JSON expected."}), 400
        
    data = request.get_json()
    player = data.get('player')
    year = data.get('year')
    brand = data.get('brand')

    # Basic validation (optional but recommended)
    if player is None or year is None or brand is None:
         return jsonify({"success": False, "message": "Missing required fields (player, year, brand)."}), 400

    try:
        success = data_manager.update_result_details(result_id, player, year, brand)
        if success:
            logger.info(f"Successfully updated card details for ID {result_id}")
            # In future, trigger re-evaluation here if needed
            return jsonify({"success": True, "message": "Card details updated successfully."})
        else:
            logger.warning(f"Update failed or no changes made for card ID {result_id}")
            return jsonify({"success": False, "message": "Update failed or item not found."}), 404
    except Exception as e:
        logger.error(f"Error updating card {result_id}: {str(e)}")
        return jsonify({"success": False, "message": f"Internal server error: {str(e)}"}), 500

@app.route('/reevaluate/<int:result_id>', methods=['POST'])
def reevaluate_item(result_id):
    """Re-run eBay search for a given item ID using potentially updated details."""
    try:
        # 1. Fetch the latest data for the item from DB
        item_data = data_manager.get_result_by_id(result_id)
        if not item_data:
            return jsonify({"success": False, "message": "Item not found."}), 404

        # Check if it's a baseball card (or adaptable for other types if needed)
        if item_data.get('item_type', '').lower() != 'baseball card':
            return jsonify({"success": False, "message": "Re-evaluation only supported for baseball cards."}), 400

        # 2. Construct search query from potentially edited fields
        player = item_data.get('card_player')
        year = item_data.get('card_year')
        brand = item_data.get('card_brand')
        
        search_query = f"{year or ''} {brand or ''} {player or ''}".strip()
        
        if not search_query:
            logger.warning(f"Cannot re-evaluate ID {result_id}: Not enough details (player, year, brand).")
            return jsonify({"success": False, "message": "Not enough card details to perform search."}), 400
            
        logger.info(f"Re-evaluating ID {result_id} with query: '{search_query}'")

        # 3. Call eBay Searcher (Accessing via controller instance)
        # Assuming Controller has an instance of eBaySearcher accessible
        # If controller.__init__ doesn't set self.ebay_searcher, you need to instantiate it here or access it differently
        try:
            # *** Critical Dependency: Ensure controller.ebay_searcher exists and returns (value, url) ***
            ebay_result = controller.ebay_searcher.search_card_value(search_query) 
        except AttributeError:
             logger.error("Controller instance does not have 'ebay_searcher' attribute initialized.")
             return jsonify({"success": False, "message": "Server configuration error: eBay searcher not available."}), 500
        except Exception as search_e:
            logger.error(f"Error during eBay search re-evaluation for ID {result_id}: {search_e}")
            return jsonify({"success": False, "message": f"eBay search failed: {search_e}"}), 500

        new_ebay_value = None
        new_ebay_search_url = None
        if ebay_result and isinstance(ebay_result, (list, tuple)) and len(ebay_result) == 2:
            new_ebay_value = str(ebay_result[0])
            new_ebay_search_url = str(ebay_result[1])
            logger.info(f"Re-evaluation successful for ID {result_id}: Value='{new_ebay_value}', URL='{new_ebay_search_url}'")
        else:
            logger.warning(f"Re-evaluation eBay search returned no result or invalid format for ID {result_id}")
            new_ebay_value = "No Result Found" # Provide specific feedback

        # 4. Update the database record with the new eBay info
        try:
            # Need an update method specifically for eBay results in DataManager
            update_success = data_manager.update_result_ebay_info(result_id, new_ebay_value, new_ebay_search_url)
            if not update_success:
                 logger.error(f"Failed to update eBay info in DB for ID {result_id}")
                 # Decide if this is a critical failure
        except Exception as db_e:
             logger.error(f"DB Error updating eBay info for ID {result_id}: {db_e}")
             # Decide if this is a critical failure

        # 5. Return JSON response to the client
        return jsonify({
            "success": True,
            "message": "Re-evaluation complete.",
            "ebay_value": new_ebay_value,
            "ebay_search_url": new_ebay_search_url
        })

    except Exception as e:
        logger.error(f"General error during re-evaluation for ID {result_id}: {str(e)}")
        return jsonify({"success": False, "message": f"Internal server error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)