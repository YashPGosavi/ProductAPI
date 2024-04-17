from flask import jsonify, request
from app import app
from app.scraper import scrape_flipkart, scrape_product_info, get_review_url, scrape_reviews
import json


@app.route('/search', methods=['POST'])
def search_products():
    data = request.get_json()
    product_name = data.get('product_name')
    if not product_name:
        return jsonify({"error": "Product name is required"}), 400
    
    products = scrape_flipkart(product_name)
    return jsonify({"products": products})

@app.route('/productInfo', methods=['POST'])
def product_info():
    data = request.json
    product_title = data.get('title')
    flipkart_link = data.get('flipkart_link')

    if not product_title or not flipkart_link:
        return jsonify({"error": "Title and Flipkart link are required."}), 400

    product_info = scrape_product_info(product_title, flipkart_link)

    # Get the review URL from the product URL
    review_url = get_review_url(flipkart_link)
    if not review_url:
        return jsonify({'error': 'Invalid product URL'}), 400

    # Scrape the reviews
    result_json = scrape_reviews(review_url)

    # Parse the JSON string into a Python object
    reviews = json.loads(result_json)

    # Append reviews to product info
    product_info['reviews'] = reviews

    # Return product info with reviews
    return jsonify(product_info)
