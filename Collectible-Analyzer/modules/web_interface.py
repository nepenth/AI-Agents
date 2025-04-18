from flask import Flask, request, render_template, redirect, url_for
from .controller import Controller
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize controller
controller = Controller()

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

        # Save the uploaded file
        filename = file.filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        logger.info(f"Saved uploaded image: {file_path}")

        # Process the image
        result = controller.process_item(file_path, item_type)

        # Render results page
        return render_template('results.html', result=result, image_path=url_for('static', filename=f'uploads/{filename}'))

    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        return render_template('index.html', error=f"Error processing image: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)