import requests
from bs4 import BeautifulSoup
import logging
import time
import re
import json

def scrape_flipkart(product_name, flipkart_link=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            if flipkart_link:
                headers = {
                    'User-Agent': 'Your user agent here',
                    'Accept-Language': 'en-us,en;q=0.5'
                }
                response = requests.get(flipkart_link, headers=headers)
                response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

                soup = BeautifulSoup(response.content, 'html.parser')
                title = soup.find("span", {"class": "B_NuCI"}).text.strip()
                price = float(soup.find("div", {"class": "_30jeq3 _16Jk6d"}).text.replace(',', '').replace('₹', '').strip())
                image_urls = [img['src'] for img in soup.find_all("img", {"class": "_396cs4"})]
                description = soup.find("div", {"class": "_1mXcCf RmoJUa"}).text.strip()
                return {
                    "title": title,
                    "flipkart_price": price,
                    "image_urls": image_urls,
                    "flipkart_buy_link": flipkart_link,
                    "description": description,
                    "platform": "Flipkart"
                }
            else:
                products = []
                flipkart_url = f"https://www.flipkart.com/search?q={product_name}"
                headers = {
                    'User-Agent': 'Your user agent here',
                    'Accept-Language': 'en-us,en;q=0.5'
                }
                response = requests.get(flipkart_url, headers=headers)
                response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

                soup = BeautifulSoup(response.content, 'html.parser')
                product_cards = soup.find_all("div", class_="_1AtVbE")
                for card in product_cards:
                    title_element = card.find("div", class_="_4rR01T")
                    if title_element:
                        title = title_element.text.strip()
                        image_url = card.find("img")['src']
                        product_link = "https://www.flipkart.com" + card.find("a")['href']
                        products.append({"title": title, "image_url": image_url, "product_link": product_link})
                return products
        except requests.HTTPError as e:
            logging.error(f"HTTP error occurred while scraping Flipkart: {e}")
            time.sleep(1)  # Wait for 1 second before retrying
        except Exception as e:
            logging.error(f"Exception occurred while scraping Flipkart: {e}")
            time.sleep(1)  # Wait for 1 second before retrying

    # If all retries fail, return an empty dictionary or list
    return {}

def scrape_amazon_with_retry(product_name, retry=5):
    for _ in range(retry):
        try:
            amazon_url = f"https://www.amazon.in/s?k={product_name}"
            headers = {
                'User-Agent': 'Your user agent here',
                'Accept-Language': 'en-us,en;q=0.5'
            }
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
        page = requests.get(url)
        soup = BeautifulSoup(page.content, 'html.parser')

        names = soup.find_all('p', class_='_2sc7ZR _2V5EHH')
        for name in names:
            customer_names.append(name.get_text())

        title = soup.find_all('p', class_='_2-N8zT')
        for t in title:
            review_title.append(t.get_text())

        rat = soup.find_all('div', class_='_3LWZlK _1BLPMq')
        for r in rat:
            rating = r.get_text()
            if rating:
                ratings.append(rating)
            else:
                ratings.append('0')

        cmt = soup.find_all('div', class_='t-ZTKy')
        for c in cmt:
            comment_text = c.div.div.get_text(strip=True)
            comments.append(comment_text)

        reviews_collected += len(names)

        next_button = soup.find('a', class_='_1LKTO3')
        if not next_button or reviews_collected >= 100:
            break

        url = 'https://www.flipkart.com' + next_button['href']

    min_length = min(len(customer_names), len(review_title), len(ratings), len(comments))
    customer_names = customer_names[:min_length]
    review_title = review_title[:min_length]
    ratings = ratings[:min_length]
    comments = comments[:min_length]

    data = {
        'user': customer_names,
        'review_title': review_title,
        'rating': ratings,
        'comment': comments
    }

    df = pd.DataFrame(data)

    result_json = df.to_json(orient='records')

    return result_json
