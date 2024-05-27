from flask import Flask, jsonify, request
from flask_cors import CORS
import aiohttp
import nest_asyncio
from bs4 import BeautifulSoup
import pandas as pd
import logging
import asyncio
import re
import json

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# User-Agent and Accept-Language headers
headers = {
    'User-Agent': 'Your user agent here',
    'Accept-Language': 'en-us,en;q=0.5'
}

# Apply nest_asyncio to allow running asyncio in a Flask app
nest_asyncio.apply()

async def fetch(url, session):
    async with session.get(url) as response:
        return await response.text()

async def scrape_flipkart_async(product_name, flipkart_link):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            response_text = await fetch(flipkart_link, session)
            soup = BeautifulSoup(response_text, 'html.parser')
            # Your scraping logic here
            title = soup.find("span", {"class": "B_NuCI"}).text.strip()
            price = float(soup.find("div", {"class": "_30jeq3 _16Jk6d"}).text.replace(',', '').replace('₹', '').strip())
            image_urls = [img['src'] for img in soup.find_all("img", {"class": "_396cs4 _3exPp9"})]
            product_specifications = soup.find("div", {"class": "_2418kt"}).text.strip()
            description = soup.find("div", {"class": "_1mXcCf RmoJUa"}).text.strip()
            offers_list = soup.find_all("li", class_="_16eBzU col")
            payment_options = [item.text.strip() for item in soup.find_all("li", {"class": "_1DuK2S"})]
            delivery_by = soup.find("div", {"class": "_3XINqE"}).text.replace('?', '').strip()
            color_storage = [item.text.strip() for item in soup.find_all("li", {"class": "_3V2wfe _2Wpvfz"})]
            rating = soup.find("div", {"class": "_3LWZlK"}).text.strip()
            no_of_ratings = soup.find("span", {"class": "_2_R_DZ"}).text.strip()

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
                "description": description,
                "payment_options": payment_options,
                "flipkart_offers": flipkart_offers,
                "color_storage": color_storage,
                "delivery_by": delivery_by,
                "total_rating": rating + " of " + no_of_ratings,
                "platform": "Flipkart"
            }
    except Exception as e:
        logging.error(f"Exception occurred while scraping Flipkart: {e}")
        return {}

async def scrape_amazon_with_retry_async(product_name, retry=5):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        for _ in range(retry):
            try:
                amazon_url = f"https://www.amazon.in/s?k={product_name}&ref=nb_sb_noss"
                response_text = await fetch(amazon_url, session)
                soup = BeautifulSoup(response_text, 'html.parser')
                product_link = soup.find("a", {"class": "a-link-normal s-no-outline"})['href']
                amazon_link = f"https://www.amazon.in{product_link}"
                title = soup.find("span", {"class": "a-size-medium a-color-base a-text-normal"}).text.strip()
                price = float(soup.find("span", {"class": "a-price-whole"}).text.replace(',', ''))
                
                return {
                    "title": title,
                    "amazon_price": price,
                    "amazon_buy_link": amazon_link,
                    "platform": "Amazon"
                }
            except Exception as e:
                logging.error(f"Exception occurred while scraping Amazon: {e}")
                await asyncio.sleep(1)  # Wait for 1 second before retrying
    return {}

async def scrape_product_info_async(product_title, flipkart_link):
    flipkart_details = await scrape_flipkart_async(product_title, flipkart_link)
    amazon_details = await scrape_amazon_with_retry_async(product_title)

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
        names = soup.find_all('p', class_='_2sc7ZR _2V5EHH')
        for name in names:
            customer_names.append(name.get_text())

        # Extract review titles
        title = soup.find_all('p', class_='_2-N8zT')
        for t in title:
            review_title.append(t.get_text())

        # Extract ratings
        rat = soup.find_all('div', class_='_3LWZlK _1BLPMq')
        for r in rat:
            rating = r.get_text()
            if rating:
                ratings.append(rating)
            else:
                ratings.append('0')  # Replace null ratings with 0

        # Extract comments
        cmt = soup.find_all('div', class_='t-ZTKy')
        for c in cmt:
            comment_text = c.div.div.get_text(strip=True)
            comments.append(comment_text)

        reviews_collected += len(names)

        # Check if there are more pages to scrape
        next_button = soup.find('a', class_='_1LKTO3')
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
async def search_products():
    data = request.get_json()
    product_name = data.get('product_name')
    if not product_name:
        return jsonify({"error": "Product name is required"}), 400
    
    products = await scrape_flipkart_async(product_name, f"https://www.flipkart.com/search?q={product_name}")
    print("Scraped products:", products)  # Add this line to print the scraped products
    return jsonify
