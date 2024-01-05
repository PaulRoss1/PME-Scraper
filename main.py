from selenium import webdriver
import os
import mysql.connector
import time
from time import sleep
from geopy.geocoders import Nominatim
from slugify import slugify
from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime

# ================== CHROME WEBDRIVER SETUP ==================


chrome_options = webdriver.ChromeOptions()


# ADD THIS ON DEPLOYMENT
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")


chrome_options.binary_location = os.environ.get("GOOGLE_CHROME_BIN")



driver = webdriver.Chrome(
    executable_path=os.environ.get("CHROMEDRIVER_PATH"), options=chrome_options
)




# # ================== DATABASE CONNECTION ==================

config = {
    "user": "your_database_user",
    "password": "your_database_password",
    "host": "your_database_host",
    "database": "your_database",
}

# establish connection
cnxn = mysql.connector.connect(**config)
cursor = cnxn.cursor()  # initialize connection cursor


live_music = "https://goout.net/cs/praha/koncerty/leznyvlkkzf/?sort=news"
djs = "https://goout.net/cs/praha/parties/leznyvlkkzj/?sort=news"

# live_music = "https://goout.net/cs/praha/koncerty/leznyvlkkzf/?sort=popularity"
# djs = "https://goout.net/cs/praha/parties/leznyvlkkzj/?sort=popularity"

# live_music = "https://goout.net/cs/praha/koncerty/leznyvlkkzf/?sort=timestamp"
# djs = "https://goout.net/cs/praha/parties/leznyvlkkzj/?sort=timestamp"

# live_music = "https://goout.net/cs/praha/koncerty/leznyvlkkzf/?sort=recommendations"
# djs = "https://goout.net/cs/praha/parties/leznyvlkkzj/?sort=recommendations"


class CardsData:
    def __init__(self, name, slug, venue, address, date, lat_long, image, event_type, price):
        self.name = name
        self.slug = slug
        self.venue = venue
        self.address = address
        self.date = date
        self.lat_long = lat_long
        self.image = image
        self.event_type = event_type
        self.price = price

    def __repr__(self):
        return str(self.name)


cursor.execute("SELECT * FROM event_event")
all_events = list(cursor)

def scraper(url, event_type):
    # selenium
    driver.get(url)

    #  scrolling
    time.sleep(3)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    cards = driver.find_elements(By.CLASS_NAME, "column")

    events = []

    for card in cards:
        try:
            info = card.find_element(By.CLASS_NAME, "info")
            name = info.find_element(By.CLASS_NAME, "text-truncate").text

            # Extract the price from the embedded JSON data
            json_data = card.find_element(By.TAG_NAME, "script").get_attribute("innerHTML")
            price = ""
            try:
                import json
                data = json.loads(json_data)
                offers = data.get("offers", [])
                if offers:
                    price = offers[0].get("price", "")
            except json.JSONDecodeError:
                pass
            price = price.split('–')[0].strip()
            if not price or price == "0":
                                    price = "100"
            slug = ""
            date = info.find_element(By.TAG_NAME, "time").get_attribute("datetime")
            # image = card.find_element(By.TAG_NAME, "img").get_attribute("src")[:-8]
            script_tag = card.find_element(By.TAG_NAME, "script").get_attribute("innerHTML")
            image = json.loads(script_tag).get("image", "")
            venue = info.find_elements(By.CLASS_NAME, "text-truncate")[2].text
            event_type = event_type
            address = ""
            lat_long = ""

            data = CardsData(name, slug, venue, address, date, lat_long, image, event_type, price)

            events.append(data)
        except Exception as e:
            print("An error occurred:", str(e))

    return events



def save_to_db(events, all_events):
    geolocator = Nominatim(user_agent="agent")
    added_events = []

    # Extract unique identifiers for events from the all_events list
    existing_events_identifiers = [(e[2], e[3], e[5]) for e in all_events]

    for event in events:
        slug = slugify(event.name)
        address = geolocator.geocode(event.venue + ", Praha")

        if address is not None:
            # GEO LOCATION
            geo = geolocator.geocode(address)
            try:
                lat = geo.latitude
                long = geo.longitude
                lat_long = str(lat)[:8] + " " + str(long)[:8]

                # Parse the date to extract the "YYYY-MM-DD" part
                event_date = datetime.strptime(event.date, "%Y-%m-%dT%H:%M:%S.%fZ").date()

                # Check if the event already exists in the database using unique identifiers
                event_identifier = (slug, event.venue, str(event.date)[:10])

                if event_identifier not in existing_events_identifiers:
                    cursor.execute(
                        "INSERT INTO sys.event_event (name,slug,venue,address,date,lat_long,image,event_type,price) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            str(event.name),
                            str(slug),
                            str(event.venue),
                            str(address),
                            event_date,   
                            str(lat_long),
                            str(event.image),
                            str(event.event_type),
                            event.price
                        ),
                    )
                    cnxn.commit()

                    event_info = f"Name: {event.name}, Venue: {event.venue}, Date: {event_date}, Event Type: {event.event_type}"
                    added_events.append(event_info)

            except AttributeError:
                events.remove(event)

        else:
            events.remove(event)

    if not added_events:
        print("no new events")
    else:
        print("successfully added: " + str(added_events))


def delete_old_events(all_events):
    for event in all_events:
        past = datetime.strptime(str(event[5]), "%Y-%m-%d")
        present = datetime.now()

        if past.date() < present.date():
            cursor.execute(f"DELETE FROM sys.event_event WHERE id = '{event[0]}'")
            cnxn.commit()


live_music_events = scraper(live_music, "Live Music")
save_to_db(live_music_events, all_events)

dj_events = scraper(djs, "DJ's")
save_to_db(dj_events, all_events)

delete_old_events(all_events)
