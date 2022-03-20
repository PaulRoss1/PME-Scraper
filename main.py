from selenium import webdriver
import os
import mysql.connector
import time
from time import sleep
from geopy.geocoders import Nominatim
from slugify import slugify
from selenium.webdriver.common.by import By
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
    executable_path=os.environ.get("CHROMEDRIVER_PATH"), chrome_options=chrome_options
)

# ================== DATABASE CONNECTION ==================

config = {
    "user": "",
    "password": "",
    "host": "",
    "database": "",
}

# establish connection
cnxn = mysql.connector.connect(**config)
cursor = cnxn.cursor()  # initialize connection cursor


live_music = "https://goout.net/cs/praha/koncerty/leznyvlkkzf/?sort=timestamp"
djs = "https://goout.net/cs/praha/parties/leznyvlkkzj/?sort=timestamp"


class CardsData:
    def __init__(self, name, slug, venue, address, date, lat_long, image, event_type):
        self.name = name
        self.slug = slug
        self.venue = venue
        self.address = address
        self.date = date
        self.lat_long = lat_long
        self.image = image
        self.event_type = event_type

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
    time.sleep(1)

    cards = driver.find_elements(By.CLASS_NAME, "column")
    events = []

    for card in cards:
        info = card.find_element(By.CLASS_NAME, "info")

        name = info.find_element(By.CLASS_NAME, "text-truncate").text
        slug = ""
        date = info.find_element(By.TAG_NAME, "time").get_attribute("datetime")
        image = card.find_element(By.TAG_NAME, "img").get_attribute("src")[:-8]
        venue = info.find_elements(By.CLASS_NAME, "text-truncate")[2].text
        event_type = event_type
        address = ""
        lat_long = ""

        data = CardsData(name, slug, venue, address, date, lat_long, image, event_type)

        events.append(data)
    return events


def save_to_db(events, all_events):
    geolocator = Nominatim(user_agent="agent")
    added_events = []

    for event in events:
        slug = slugify(event.name)
        address = geolocator.geocode(event.venue + ", Praha")
        event.date = f"{event.date[8:10]}. {event.date[5:7]}. {event.date[0:4]}"

        if address != None:
            # GEO LOCATION
            geo = geolocator.geocode(address)
            try:
                lat = geo.latitude
                long = geo.longitude
                lat_long = str(lat)[:8] + " " + str(long)[:8]

                event_string = f"'{slug}', '{event.venue}', '{address}', '{event.date}'"

                # INSERT INTO DB
                if not event_string in str(all_events):
                    cursor.execute(
                        "INSERT INTO event_event (name,slug,venue,address,date,lat_long,image,event_type) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            str(event.name),
                            str(slug),
                            str(event.venue),
                            str(address),
                            str(event.date),
                            str(lat_long),
                            str(event.image),
                            str(event.event_type),
                        ),
                    )
                    cnxn.commit()

                    event_info = f"Name: {event.name}, Slug: {event.slug}, Venue: {event.venue}, Address: {address}, Date: {event.date}, Lat and Long: {lat_long}, Image: {event.image}, Event Type: {event.event_type}"
                    added_events.append(event_info)

            except AttributeError:
                events.remove(event)

        else:
            events.remove(event)

    if not added_events:
        print("no new events")
    else:
        print("succesfully added: " + str(added_events))


def delete_old_events(all_events):
    for event in all_events:
        past = datetime.strptime(event[5], "%d. %m. %Y")
        present = datetime.now()

        if past.date() < present.date():
            cursor.execute(f"DELETE FROM event_event WHERE id = '{event[0]}'")
            cnxn.commit()


live_music_events = scraper(live_music, "Live Music")
save_to_db(live_music_events, all_events)

dj_events = scraper(djs, "DJ's")
save_to_db(dj_events, all_events)

delete_old_events(all_events)
