from flask import Flask, jsonify, Response
from flask_cors import CORS
from bs4 import BeautifulSoup
import requests
from geopy.geocoders import Nominatim
import json
import re
from datetime import date, datetime, timedelta
import logging
from time import sleep
from geopy.exc import GeocoderTimedOut
import html
import shutil
import os
from random import randint, uniform, choice
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CORS(app)
geolocator = Nominatim(user_agent="myGeocoder")
logging.basicConfig(level=logging.INFO)
google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
frontend_dir = os.getenv("FRONTEND_DIR")

# Define a mapping of keywords or patterns to activity types
activity_mapping = {
    'music': 'Music',
    'art': 'Art',
    'festival': 'Festival',
    'food': 'Food',
    'sports': 'Sports',
    'happy hour': 'Happy Hour',
    'museum': 'Museum',
    'dating': 'Dating',
    'entertainment': 'Entertainment',
    'center': 'Art',
    'bar': 'Bar',
    'club': 'Club',
    'lounge': 'Lounge',
    'concert': 'Music',
    'exhibition': 'Art',
    'fair': 'Festival',
    'restaurant': 'Food',
    'pub': 'Bar',
    'brewery': 'Bar',
    'beer garden': 'Bar',
    'gym': 'Sports',
    'fitness': 'Sports',
    'party': 'Happy Hour',
    'gallery': 'Art',
    'theater': 'Art',
    'cinema': 'Entertainment',
    'show': 'Art',
    'match': 'Sports',
    'tournament': 'Sports',
    'date': 'Dating',
    'speed dating': 'Dating',
    'board game': 'Entertainment',
    'games': 'Entertainment',
    'arcade': 'Entertainment',
    'cocktail': 'Happy Hour',
    'wine': 'Happy Hour',
    'dance': 'Club',
    'nightclub': 'Club',
    'pub': 'Bar',
    'lounge bar': 'Lounge',
    'karaoke': 'Music',
    'live music': 'Music',
    'comedy': 'Art',
    'mural': 'Art',
    'sculpture': 'Art',
    'craft': 'Art',
    'movie': 'Entertainment',
    'band': 'Music',
    'jazz': 'Music',
    'trivia': 'Trivia',
    'cafe': 'Food',
    'market': 'Food',
    'outdoor': 'Outdoor',
    'park': 'Outdoor',
    'beach': 'Outdoor',
    'hiking': 'Outdoor',
    'nature': 'Outdoor',
    'workshop': 'Workshop',
    'class': 'Workshop',
    'education': 'Workshop',
    'conference': 'Conference',
    'technology': 'Conference',
    'networking': 'Conference',
    'seminar': 'Conference',
    'charity': 'Charity',
    'fundraiser': 'Charity',
    'volunteering': 'Charity',
    'cause': 'Charity',
    'family': 'Family',
    'kids': 'Family',
    'children': 'Family',
    'parenting': 'Family',
    'yoga': 'Wellness',
    'meditation': 'Wellness',
    'mindfulness': 'Wellness',
    'health': 'Wellness',
    'well-being': 'Wellness',
    'spirituality': 'Wellness',
    'retreat': 'Wellness',
    'fashion': 'Fashion',
    'style': 'Fashion',
    'design': 'Fashion',
    'shopping': 'Shopping',
    'marketplace': 'Shopping',
    'vintage': 'Shopping',
    'crafts': 'Shopping',
    'sale': 'Shopping',
}

# Define a mapping of common street abbreviations
street_mapping = {
    'st': 'Street',
    'st.': 'Street',
    'ave': 'Avenue',
    'ave.': 'Avenue',
    'blvd': 'Boulevard',
    'blvd.': 'Boulevard',
    'dr': 'Drive',
    'dr.': 'Drive',
    'rd': 'Road',
    'rd.': 'Road',
    'ln': 'Lane',
    'ln.': 'Lane',
    'ct': 'Court',
    'ct.': 'Court'
}



def infer_activity_type(event_name, event_description):
    for keyword, activity_type in activity_mapping.items():
        if re.search(r'\b{}\b'.format(keyword), event_name, re.IGNORECASE) or \
                re.search(r'\b{}\b'.format(keyword), event_description, re.IGNORECASE):
            return activity_type
    return 'Entertainment'  # return 'Entertainment' if no matching keywords are found


@app.route('/events')
def get_events():
    today_events = load_events_from_file(get_events_filename())

    all_events = {
        "today": today_events,
    }

    json_response = json.dumps(all_events, indent=4)
    response = Response(json_response, content_type='application/json')

    return response


def preprocess_address(address):
    # Split the address into parts
    parts = address.split(',')
    
    # Remove duplicate parts
    parts = list(dict.fromkeys(parts))
    
    # Reassemble the address
    address = ', '.join(parts).strip()
    
    # Standardize street abbreviations
    for abbreviation, full in street_mapping.items():
        address = re.sub(r'\b{}\b'.format(abbreviation), full, address, flags=re.IGNORECASE)
    
    # Remove any non-address related information (e.g., anything inside parentheses)
    address = re.sub(r'\(.*?\)', '', address).strip()
    
    return address

def remove_duplicates(events):
    unique_events = []
    event_set = set()

    for event in events:
        event_tuple = (
            event['name'],
            event['date'],
            event['address'],
            event['description'],
            event['activity_type']
        )

        if event_tuple not in event_set:
            unique_events.append(event)
            event_set.add(event_tuple)

    return unique_events

def assign_unique_coordinates(events):
    event_coordinates = {}

    for event in events:
        coordinates = (event['latitude'], event['longitude'])
        if coordinates not in event_coordinates:
            event_coordinates[coordinates] = 0
        else:
            event_coordinates[coordinates] += 1
            offset = (event_coordinates[coordinates] + 1) * 0.0001  # Adjust the offset as needed
            event['latitude'] += uniform(-offset, offset)
            event['longitude'] += uniform(-offset, offset)

def scrape_page(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537",
    }

    logging.info(f"Scraping page: {url}")
    res = requests.get(url, headers=headers)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, 'html.parser')
    event_list = []

    if 'nycgovparks' in url:
        events = soup.select('.event')

        for event in events:
            name = event.select_one('.event-title').text.strip()

            start_date_tag = event.select_one('meta[itemprop="startDate"]')
            end_date_tag = event.select_one('meta[itemprop="endDate"]')
            start_date_str = convert_date(start_date_tag['content']) if start_date_tag else 'N/A'
            end_date_str = convert_date(end_date_tag['content']) if end_date_tag else 'N/A'
            date_str = f"{start_date_str} - {end_date_str}"

            location_tag = event.select_one('.location span[itemprop="name"]')
            address = location_tag.text.strip() if location_tag else 'N/A'
            description_tag = event.select_one('.description')
            description = description_tag.text.strip() if description_tag else 'N/A'

            activity_type_tag = event.select_one('.activity-type')
            activity_type = activity_type_tag.text.strip() if activity_type_tag else 'Entertainment'

            event_list.append({
                "name": name,
                "date": date_str,
                "address": address,
                "description": description,
                "activity_type": activity_type
            })

    else:
        events = soup.select('.item-info-container')

        for event in events:
            name = event.select_one('.item-title').text.strip()
            date_tag = event.select_one('.event-period')
            date_str = ' '.join(date_tag.text.split()) if date_tag else 'N/A'
            location_tag = event.select_one('.event-location')
            address = location_tag.text.strip() if location_tag else 'N/A'
            description_tag = event.select_one('.event-description')
            description = description_tag.text.strip() if description_tag else 'N/A'

            activity_type_tag = event.select_one('.activity-type')
            activity_type = activity_type_tag.text.strip() if activity_type_tag else 'Entertainment'

            event_list.append({
                "name": name,
                "date": date_str,
                "address": address,
                "description": description,
                "activity_type": activity_type
            })

    return event_list




def parse_event(event):
    # Get event details
    name = event['name']
    description = event['description']
    date_str = event['date']
    address = html.unescape(event['address'])  # Decode HTML entities in the address field

    # Add "New York, NY" to addresses that don't have it
    if "New York" not in address:
        address = f"{address}, New York, NY"

    # Extract address components
    street = ''
    city = ''
    state = ''
    zip_code = ''

    # Split the address into parts
    parts = address.split(',')

    # Extract street, city, state, and ZIP code
    for part in parts:
        part = part.strip()

        # Match the street address
        if not street:
            street = part

        # Match the city
        match_city = re.search(r'(?<=\s)\b\w+\b(?=,|\s)', part)
        if match_city:
            city = match_city.group()

        # Match the state
        match_state = re.search(r'(?<!\S)\b(?:New\s)?York\b(?=\s|$)', part)
        if match_state:
            state = match_state.group()

        # Match the ZIP code
        match_zip = re.search(r'\b\d{5}\b', part)
        if match_zip:
            zip_code = match_zip.group()

    # Get coordinates based on address components
    lat, lon = get_coordinates(street, city, state, zip_code)

    # Infer activity type based on event name and description
    activity_type = infer_activity_type(name, description)
    if activity_type is None:
        activity_type = 'Entertainment'

    # Create the event dictionary
    event_dict = {
        'name': name,
        'description': description,
        'date': date_str,
        'address': address,
        'activity_type': activity_type  # Add inferred activity type to the dictionary
    }

    # Add latitude and longitude if they are not None
    if lat is not None and lon is not None:
        event_dict['latitude'] = lat
        event_dict['longitude'] = lon

    return event_dict



def is_address_valid(street, city, state, zip_code):
    return any([street, city, state, zip_code])

import requests

def get_coordinates(street, city, state, zip_code):
    if not is_address_valid(street, city, state, zip_code):
        print(f"Invalid address: {street}, {city}, {state}, {zip_code}")
        return (None, None)

    try:
        # Construct the full address
        full_address = f"{street}, {city}, {state} {zip_code}"

        # Define the bounding box coordinates for NYC
        nyc_bounds = "40.477399,-74.25909|40.917577,-73.700181"

        # Define the API request URL with the address, API key, components, and bounds parameters
        components = f"locality:New York|administrative_area:NY"  # Specify city as "New York" and state as "NY"
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={full_address}&components={components}&bounds={nyc_bounds}&key={google_maps_api_key}"

        # Send the API request and get the response
        response = requests.get(url)
        sleep(0.1)  # To avoid hitting the rate limit

        # If the request was successful, parse the JSON response
        if response.status_code == 200:
            geocoding_data = response.json()

            # Check if the geocoding results contain any valid coordinates
            if geocoding_data['status'] == 'OK' and len(geocoding_data['results']) > 0:
                location = geocoding_data['results'][0]['geometry']['location']
                lat = location['lat']
                lon = location['lng']

                # Add a small random offset to the coordinates
                lat += uniform(-0.0001, 0.0001)
                lon += uniform(-0.0001, 0.0001)

                return (lat, lon)

            # If no valid coordinates were found, log an error
            else:
                print(f"No geocoding results found for address: {full_address}")

        # If the request failed, log an error
        else:
            print(f"Geocoding API request failed with status code: {response.status_code} for address: {full_address}")

    # If an exception occurred while making the API request, log the exception
    except Exception as e:
        print(f"An error occurred while geocoding the address: {full_address}. Error: {e}")

    # If we reach this point, the geocoding failed, so return None for the latitude and longitude
    return (None, None)


def save_events_to_file(events, filename):
    # Save the file in the backend data directory
    backend_path = os.path.dirname(os.path.abspath(__file__))  # Get the absolute path of the backend file
    data_dir = os.path.join(backend_path, 'data')  # Path to the "data" directory in the backend

    # Create the data directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)

    # Save the file in the backend data directory
    backend_file = os.path.join(data_dir, filename)
    with open(backend_file, 'w') as file:
        json.dump(events, file, indent=4)

def load_events_from_file(filename):
    data_dir = 'data'
    file_path = os.path.join(data_dir, filename)
    with open(file_path, 'r') as file:
        events = json.load(file)
    return events


def get_events_filename():
    current_date = date.today().strftime("%Y-%m-%d")
    filename = f"events_{current_date}.json"
    return filename

def convert_date(date_str):
    # Parse the date and time from the ISO string
    date_time_obj = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S%z')

    # Format the date and time in the desired format
    formatted_date = date_time_obj.strftime('%B %d @ %I%p')
    return formatted_date

def main():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"SCRIPT RUNNING, EXECUTED AT {current_time}")

if __name__ == '__main__':
    base_url_1 = os.getenv('BASE_URL_1')
    base_url_2 =  os.getenv('BASE_URL_2')
    query_params = "q=New%20York,%20NY,%20United%20States&lat=40.7127753&lng=-74.0059728&rad=30&order=distance&startDate="
    current_date = date.today().strftime("%Y-%m-%d")

    events = []
    new_events_count = 0

    # Scrape pages 
    for page in range(1, 11):  # Scrape pages 1-10
        url = f"{base_url_1}?page={page}&{query_params}{current_date}"
        scraped_events = scrape_page(url)
        for event in scraped_events:
            parsed_event = parse_event(event)  # Parse each event to add lat, lon, and activity type
            events.append(parsed_event)  # Append the parsed event to the list
            new_events_count += 1

    for page in range(1, 11):  # Scrape pages 1-10
        url = base_url_2.format(current_date, current_date, page)
        scraped_events = scrape_page(url)
        for event in scraped_events:
            parsed_event = parse_event(event)  # Parse each event to add lat, lon, and activity type
            events.append(parsed_event)  # Append the parsed event to the list
            new_events_count += 1

    save_events_to_file(events, get_events_filename())
    logging.info(f"Number of new events added: {new_events_count}")

    main()
    app.run()





