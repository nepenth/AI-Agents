# Implementation Plan for Collectible Analyzer

## Overview
The Collectible Analyzer is a web-based application designed to analyze images of collectible items, such as baseball cards and wine bottles, to extract details and estimate their market value. The system uses a combination of image processing, text analysis, and web scraping to provide users with detailed insights and historical data. This document outlines the high-level architecture, components, functionality, and data flow of the application.

## Objectives
- Allow users to upload images of collectibles (primarily baseball cards and wine bottles).
- Process images to detect and segment individual items.
- Extract textual information from images using vision models.
- Analyze extracted text to identify key details (e.g., player name, year, brand for cards; winery, vintage for wine).
- Estimate market value using external sources (eBay for cards, Vivino for wine).
- Store results in a database for historical reference and cataloging.
- Provide a user-friendly web interface for uploads, viewing results, and managing a catalog.

## Architecture Overview
The application follows a modular architecture with distinct components for handling different aspects of the analysis pipeline. The primary components are:
1. **Web Interface (`app.py`, `web_interface.py`)**: Handles user interactions, file uploads, and result display.
2. **Controller (`controller.py`)**: Orchestrates the overall processing pipeline, managing tasks and coordinating between other modules.
3. **Image Segmenter (`image_segmenter.py`)**: Detects and crops individual items from uploaded images.
4. **Image Processor (`image_processor.py`)**: Interprets content from individual cropped images using a vision model.
5. **Text Analyzer (`text_analyzer.py`)**: Processes extracted text to generate structured insights.
6. **eBay Searcher (`ebay_searcher.py`)**: Scrapes eBay for sold listings to estimate baseball card values.
7. **Vivino Searcher (`vivino_searcher.py`)**: Scrapes Vivino for wine bottle prices and ratings.
8. **Data Manager (`data_manager.py`)**: Manages storage and retrieval of analysis results in a SQLite database.
9. **Drink Window (`drink_window.py`)**: Determines the optimal drinking window for wine based on vintage and varietal.
10. **Templates (`templates/`)**: HTML templates for rendering the web interface.

## Component Details and Functionality

### 1. Web Interface (`app.py`, `web_interface.py`)
- **Purpose**: Serves as the entry point for user interactions via a Flask web application.
- **Key Functions**:
  - Handles image uploads and form submissions (`/upload` endpoint).
  - Displays the home page, history, catalog, and results pages using templates.
  - Manages task status polling for background processing (`/status/<task_id>`).
  - Provides export functionality for results as CSV (`/export`).
  - Supports catalog editing and re-evaluation of items (`/update_card/<id>`, `/reevaluate/<id>`).
- **Templates**:
  - `index.html`: Home page with upload form.
  - `history.html`: Displays all past analysis results with options to export or delete.
  - `catalog.html`: Editable catalog for baseball cards, allowing updates to details and re-evaluation of values.
  - `results.html`: Shows detailed results for a single analysis.

### 2. Controller (`controller.py`)
- **Purpose**: Central orchestrator that manages the processing pipeline for uploaded images.
- **Key Functions**:
  - Initiates background tasks for image processing (`start_image_processing`).
  - Coordinates between image segmentation, processing, text analysis, value estimation, and data storage.
  - Maintains a global task status dictionary to track processing progress.
  - Parses structured insights from text analysis for storage.
- **Flow**: Receives image path and item type from the web interface, starts a background thread to process the image through various stages, and updates task status.

### 3. Image Segmenter (`image_segmenter.py`)
- **Purpose**: Detects and segments individual collectible items from an uploaded image.
- **Key Functions**:
  - Uses a vision model (via Ollama) to detect items in a 3x3 grid or falls back to OpenCV contour detection (`segment_image`).
  - Crops detected items and saves them as separate images.
  - Returns a list of cropped image information for further processing.
- **Flow**: Takes a PIL image, attempts to detect 9 items using AI, falls back to OpenCV or a grid if detection fails, and saves cropped images.

### 4. Image Processor (`image_processor.py`)
- **Purpose**: Interprets the content of individual cropped images to extract raw text.
- **Key Functions**:
  - Converts images to base64 for API calls (`_image_to_base64`).
  - Sends images to a vision model (Ollama) for text extraction (`interpret_image`).
- **Flow**: Receives a PIL image of a single item, sends it to the vision model with a tailored prompt based on item type, and returns the extracted text description.

### 5. Text Analyzer (`text_analyzer.py`)
- **Purpose**: Analyzes raw text extracted from images to generate structured insights.
- **Key Functions**:
  - Uses a text model (via Ollama) to interpret raw text and format it into structured details (`generate_insights`).
  - For wine, integrates drink window calculation (`get_drink_window`).
- **Flow**: Takes raw text and item type, crafts a specific prompt for structured output (e.g., player, year, brand for cards), and returns formatted insights.

### 6. eBay Searcher (`ebay_searcher.py`)
- **Purpose**: Estimates the market value of baseball cards by scraping eBay sold listings.
- **Key Functions**:
  - Constructs search queries from card details and fetches sold listings (`search_card_value`).
  - Parses prices and calculates an average or range.
- **Flow**: Receives a description or query, searches eBay, extracts price data, and returns a formatted value range.

### 7. Vivino Searcher (`vivino_searcher.py`)
- **Purpose**: Estimates the market value and rating of wine bottles by scraping Vivino.
- **Key Functions**:
  - Searches Vivino with wine description (`search_wine_value`).
  - Extracts price and rating data from top results.
- **Flow**: Takes a wine description, queries Vivino, parses results, and returns a formatted value and rating.

### 8. Data Manager (`data_manager.py`)
- **Purpose**: Manages persistent storage of analysis results in a SQLite database.
- **Key Functions**:
  - Initializes database and schema (`_init_database`).
  - Saves analysis results with detailed fields (`save_result`).
  - Retrieves results for history and catalog views (`get_all_results`, `get_result_by_id`).
  - Supports updating card details and eBay info (`update_result_details`, `update_result_ebay_info`).
  - Handles export to CSV and deletion of records (`export_to_csv`, `delete_result_by_id`, `delete_all_results`).
- **Flow**: Stores results after processing, retrieves data for display, and manages user edits or deletions.

### 9. Drink Window (`drink_window.py`)
- **Purpose**: Calculates the optimal drinking window for wine based on vintage and varietal.
- **Key Functions**:
  - Extracts vintage from description and applies aging rules based on wine type (`get_drink_window`).
- **Flow**: Analyzes wine description for vintage and varietal, computes drink window based on predefined rules, and returns a recommendation.

## Data Flow and Processing Pipeline
1. **User Upload**: User uploads an image via `index.html` to the `/upload` endpoint in `app.py`.
2. **Task Initiation**: Web interface saves the image and calls `Controller.start_image_processing`, which starts a background thread with a unique task ID.
3. **Image Segmentation**: `Controller` passes the image to `ImageSegmenter.segment_image`, which detects and crops individual items (up to 9 for a 3x3 grid).
4. **Image Interpretation**: Each cropped image is sent to `ImageProcessor.interpret_image` to extract raw text using a vision model.
5. **Text Analysis**: Raw text is analyzed by `TextAnalyzer.generate_insights` to produce structured details (e.g., player, year for cards).
6. **Value Estimation**:
   - For baseball cards, `eBaySearcher.search_card_value` fetches market value from eBay.
   - For wine bottles, `VivinoSearcher.search_wine_value` fetches value and rating, and `drink_window.get_drink_window` computes the drink window.
7. **Data Storage**: Results are saved to the database via `DataManager.save_result`, including raw text, insights, and value data.
8. **Status Updates**: Task status is updated in a global dictionary (`tasks` in `controller.py`) throughout processing.
9. **Result Display**: User is redirected to `history.html` after processing, where results are fetched from the database via `DataManager.get_all_results`.
10. **Catalog Management**: Users can edit card details in `catalog.html`, updating the database via `DataManager.update_result_details`, and re-evaluate eBay values using existing details.

## Logical Diagram
```
User --> Web Interface (app.py)
         |
         v
Controller (controller.py) --> Task Status (tasks dict)
         |
         v
Image Segmenter (image_segmenter.py) --> Crop Images (3x3 grid)
         |
         v
Image Processor (image_processor.py) --> Extract Raw Text (Vision Model)
         |
         v
Text Analyzer (text_analyzer.py) --> Structured Insights (Text Model)
         |
         v
Value Estimation --> eBay Searcher (ebay_searcher.py) for Cards
             --> Vivino Searcher (vivino_searcher.py) for Wine
             --> Drink Window (drink_window.py) for Wine
         |
         v
Data Manager (data_manager.py) --> SQLite DB (Store Results)
         |
         v
Web Interface (Templates) --> Display Results (history.html, catalog.html)


## Key Dependencies
- **Flask**: Web framework for the interface.
- **Pillow (PIL)**: Image handling and manipulation.
- **OpenCV (cv2)**: Fallback image segmentation.
- **Requests & BeautifulSoup**: Web scraping for eBay and Vivino.
- **SQLite**: Lightweight database for result storage.
- **Ollama API**: External service for vision and text model inference.

## Future Enhancements
- Implement additional collectible types beyond cards and wine.
- Improve image segmentation accuracy with better models or preprocessing.
- Add user authentication for personalized catalogs.
- Enhance export options (e.g., PDF, detailed reports).
- Cache external API results to reduce redundant searches.
- Optimize background task management (e.g., using Celery for scalability).

## Maintenance Notes
- Regularly update scraping logic in `ebay_searcher.py` and `vivino_searcher.py` to handle website changes.
- Monitor Ollama API availability and model performance, adjusting prompts or models as needed.
- Ensure database schema evolves with new fields or item types via `data_manager.py`.
- Review task status handling in `controller.py` for potential race conditions in high-load scenarios.

## Conclusion
This implementation plan provides a roadmap for building and maintaining the Collectible Analyzer. By following the modular design and data flow outlined, the system can be extended or modified as needed while preserving a clear logical structure.