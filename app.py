from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
import time
import re
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# User-Agent and Accept-Language headers
headers = {
    'User-Agent': 'Your user agent here',
    'Accept-Language': 'en-us,en;q=0.5'
}

# Search Product
def scrape_product(product_name):
    products = []
    flipkart_url = f"https://www.flipkart.com/search?q={product_name}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    response = requests.get(flipkart_url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    product_cards = soup.find_all("div", class_="tUxRFH")
    for card in product_cards:
        title_element = card.find("div", class_="KzDlHZ")
        if title_element:
            title = title_element.text.strip()
            image_url = card.find("img")['src']
            product_link = "https://www.flipkart.com" + card.find("a")['href']
            products.append({"title": title, "image_url": image_url, "product_link": product_link})
    return products


# Scrap Product Information

# 1. Flipcart
def scrape_flipkart(product_name, flipkart_link):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        response = requests.get(flipkart_link, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # title 
        title = soup.find("span", {"class": "VU-ZEz"}).text.strip()
        
        # price
        price = float(soup.find("div", {"class": "Nx9bqj CxhGGd"}).text.replace(',', '').replace('₹', '').strip())
        
        # images
        image_urls = [img['src'] for img in soup.find_all("img", {"class": "DByuf4 IZexXJ jLEJ7H"})]
        
        product_specifications = soup.find("div", {"class": "U+9u4y"}).text.strip()
        
        description = soup.find("div", {"class": "yN+eNk w9jEaj"}).text.strip()
        offers_list = soup.find_all("li", class_="kF1Ml8 col")
        
        payment_options = [item.text.strip() for item in soup.find_all("li", {"class": "g11wDd"})]

        delivery_by = soup.find("div", {"class": "hVvnXm"}).text.replace('?','').strip()
        
        color_storage = [item.text.strip() for item in soup.find_all("li", {"class": "aJWdJI"})]
        
        rating = soup.find("div", {"class": "ipqd2A"}).text.strip()
        
        no_of_ratings = soup.find("div", {"class": "row j-aW8Z"}).text.replace('&','').strip()

        total_rating = rating + " of " + no_of_ratings

        
        flipkart_offers = []
        for offer in offers_list:
            offer_spans = offer.find_all("span", recursive=False)
            offer_text = ' '.join(span.get_text(strip=True) for span in offer_spans)
            flipkart_offers.append(offer_text)

        return {
            "title": title,
            "flipkart_price": price,
            "image_urls": image_urls,
            "flipkart_buy_link": flipkart_link,
            "product_specifications": product_specifications,
            "description" : description,
            "payment_options" : payment_options,
            "flipkart_offers" : flipkart_offers,
            "color_storage" : color_storage,
            "delivery_by" : delivery_by,
            "total_rating" : total_rating,
            "platform": "Flipkart"
            
        }
    except requests.HTTPError as e:
        logging.error(f"HTTP error occurred while scraping Flipkart: {e}")
        return {}
    except Exception as e:
        logging.error(f"Exception occurred while scraping Flipkart: {e}")
        return {}


# 2. Amazon
def scrape_amazon_with_retry(product_name, retry=5):
    for _ in range(retry):
        try:
            amazon_url = f"https://www.amazon.in/s?k={product_name}&ref=nb_sb_noss"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
            response = requests.get(amazon_url, headers=headers)
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

            soup = BeautifulSoup(response.content, 'html.parser')
            product_link = soup.find("a", {"class": "a-link-normal s-no-outline"})['href']
            flipkart_link = f"https://www.amazon.in{product_link}"
            title = soup.find("span", {"class": "a-size-medium a-color-base a-text-normal"}).text.strip()
            price = float(soup.find("span", {"class": "a-price-whole"}).text.replace(',', ''))
            
            return {
                "title": title,
                "amazon_price": price,
                "amazon_buy_link": flipkart_link,
                "platform": "Amazon"
            }
            
        except Exception as e:
            logging.error(f"Exception occurred while scraping Amazon: {e}")
            time.sleep(1)  # Wait for 1 second before retrying
    return {}

def scrape_product_info(product_title, flipkart_link):
    flipkart_details = scrape_flipkart(product_title, flipkart_link)
    amazon_details = scrape_amazon_with_retry(product_title)

    if flipkart_details and amazon_details:
        return {
            "title": product_title,
            "flipkart_details": flipkart_details,
            "amazon_details": amazon_details
        }
    elif flipkart_details:
        return {
            "title": product_title,
            "flipkart_details": flipkart_details,
            "amazon_details": {}
        }
    elif amazon_details:
        return {
            "title": product_title,
            "flipkart_details": {},
            "amazon_details": amazon_details
        }
    else:
        return {"error": "Product details not found on both Flipkart and Amazon."}

def get_review_url(flipkart_link):
    # Extract the product ID from the input URL
    product_id_match = re.search(r'/p/(.*?)\?', flipkart_link)
    if product_id_match:
        product_id = product_id_match.group(1)
        review_url = f"https://www.flipkart.com/{product_id}/product-reviews/{product_id}"
        return review_url
    else:
        return None

def scrape_reviews(url):
    customer_names = []
    review_title = []
    ratings = []
    comments = []

    reviews_collected = 0

    while reviews_collected < 100:
        # Send a GET request to the provided URL
        page = requests.get(url, headers=headers)
        soup = BeautifulSoup(page.content, 'html.parser')

        # Extract customer names
        names = soup.find_all('p', class_='_2NsDsF AwS1CA')
        for name in names:
            customer_names.append(name.get_text())

        # Extract review titles
        title = soup.find_all('p', class_='z9E0IG')
        for t in title:
            review_title.append(t.get_text())

        # Extract ratings
        rat = soup.find_all('div', class_='XQDdHH Ga3i8K')
        for r in rat:
            rating = r.get_text()
            if rating:
                ratings.append(rating)
            else:
                ratings.append('0')  # Replace null ratings with 0

        # Extract comments
        cmt = soup.find_all('div', class_='ZmyHeo')
        for c in cmt:
            comment_text = c.div.div.get_text(strip=True)
            comments.append(comment_text)

        reviews_collected += len(names)

        # Check if there are more pages to scrape
        next_button = soup.find('a', class_='_9QVEpD')
        if not next_button or reviews_collected >= 100:
            break

        # Get the URL for the next page
        url = 'https://www.flipkart.com' + next_button['href']

    # Ensure all lists have the same length
    min_length = min(len(customer_names), len(review_title), len(ratings), len(comments))
    customer_names = customer_names[:min_length]
    review_title = review_title[:min_length]
    ratings = ratings[:min_length]
    comments = comments[:min_length]

    # Create a DataFrame from the collected data
    data = {
        'user': customer_names,
        'review_title': review_title,
        'rating': ratings,
        'comment': comments
    }

    df = pd.DataFrame(data)

    # Convert DataFrame to JSON format
    result_json = df.to_json(orient='records')

    return result_json

@app.route('/')
def index():
    return 'Thanks For Searching'

@app.route('/search', methods=['POST'])
def search_products():
    data = request.get_json()
    product_name = data.get('product_name')
    if not product_name:
        return jsonify({"error": "Product name is required"}), 400
    
    products = scrape_product(product_name)
    print("Scraped products:", products)  # Add this line to print the scraped products
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
