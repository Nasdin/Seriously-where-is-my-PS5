import requests
from ast import literal_eval
import json
import urllib
import os
import time
import datetime

# Product Search Settings
HACHI_SEARCH_PAGE_LINK = (
    "https://www.hachi.tech/game-on/gaming-consoles-accessories/playstation-consoles"
)
SEARCH_ITEM = "PS4"

HACHI_JS_LINK = "https://www.hachi.tech/js/app.js"
HACHI_PRODUCT_LINK = "https://www.hachi.tech/sony/sony/obffr/"
SEARCH_QUERY = "https://{ALGOLIA_APPLICATION_ID}-dsn.algolia.net/1/indexes/*/queries"

twilio_account_sid = os.environ["TWILIO_ACCOUNT_SID"]
twilio_auth_token = os.environ["TWILIO_AUTH_TOKEN"]
twillio_whatsapp_from = os.environ["TWILLIO_FROM"]
twillio_whatsapp_to = os.environ["TWILLIO_TO"]

# Sandbox settings
sandbox_expiry = datetime.datetime.now() + datetime.timedelta(hours=70)
sandbox_rejoin_message = "join turquoise-dolphin"

ENABLED_TWILIO = (
    twilio_account_sid
    and twilio_auth_token
    and twillio_whatsapp_from
    and twillio_whatsapp_to
)
found = False

if ENABLED_TWILIO:
    from twilio.rest import Client

    twillio_whatsapp_to = twillio_whatsapp_to.split(",")

    # Find your Account SID and Auth Token at twilio.com/console
    # and set the environment variables. See http://twil.io/secure
    client = Client(twilio_account_sid, twilio_auth_token)


def main():
    global found
    print(f"We are searching for {SEARCH_ITEM} from {HACHI_SEARCH_PAGE_LINK}")

    link_page = requests.get(HACHI_SEARCH_PAGE_LINK)
    link_content = str(link_page.content)

    # Get JS location of script that contains Algoliasite keys

    js_location = link_content.find(HACHI_JS_LINK)

    js_location_end = js_location
    not_found = True
    while not_found:
        link_candidate = link_content[js_location:js_location_end]
        if link_candidate.endswith('"'):
            not_found = False
        js_location_end += 1

    js_link_with_id = link_candidate[:-1]

    # Get algoliaSite keys from js content

    js_content = str(requests.get(js_link_with_id).content)
    candidate_end = js_content.find("algoliaActiveSite:{type:String}}")
    candidate = js_content[:candidate_end]
    candidate_start = candidate.rfind("querySelector")

    algolia_query_function = js_content[candidate_start:candidate_end]
    algolia_keys_start = algolia_query_function.find("()") + len("()")
    algolia_keys_end = algolia_keys_start + 1

    while True:
        candidate = algolia_query_function[algolia_keys_start:algolia_keys_end]
        if candidate.endswith(")"):
            break
        algolia_keys_end += 1

    # Hack the Algolia API KEY and application id

    ALGOLIA_APPLICATION_ID, ALGOLIA_API_KEY = literal_eval(candidate)

    search_query = SEARCH_QUERY.format(
        ALGOLIA_APPLICATION_ID=ALGOLIA_APPLICATION_ID.lower()
    )

    # Derive Search Criteria

    candidate_start = link_content.find("search-criteria=") + len("search-criteria=")
    candidate_end = candidate_start + 1

    not_found = True

    while not_found:

        search_criteria = link_content[candidate_start:candidate_end]
        candidate_end += 1

        if search_criteria.count('"') == 2:
            not_found = False

    search_criteria = literal_eval(search_criteria)
    search_criterias = search_criteria.split("/")

    search_criteria = " > ".join(search_criterias)

    # % Search for the product

    SEARCH_QUERY_SEARCH_PARAMS = "filters=active_sites%3AHSG&maxValuesPerFacet=99&query=&hitsPerPage=48&highlightPreTag=__ais-highlight__&highlightPostTag=__%2Fais-highlight__&page=0&facets=%5B%22regular_price%22%2C%22brand_id%22%2C%22boutiquecates.boutique%22%2C%22boutiquecates.category%22%2C%22boutiquecates.subcategory%22%5D&tagFilters=&facetFilters=%5B%5B%22boutiquecates.subcategory%3A{search_criteria}%22%5D%5D"
    search_query_search_params = SEARCH_QUERY_SEARCH_PARAMS.format(
        search_criteria=urllib.parse.quote(search_criteria)
    )

    search_results = requests.post(
        search_query,
        params={
            "x-algolia-agent": "Algolia for JavaScript (4.10.5); Browser (lite); instantsearch.js (4.29.0); Vue (2.6.14); Vue InstantSearch (3.8.1); JS Helper (3.5.5)",
            "x-algolia-api-key": ALGOLIA_API_KEY,
            "x-algolia-application-id": ALGOLIA_APPLICATION_ID,
        },
        json={
            "requests": [
                {
                    "indexName": "hachisearchengine",
                    "params": search_query_search_params,
                },
            ]
        },
    )

    search_content = str(search_results.content)
    results = json.loads(literal_eval(search_content))["results"]

    found = []

    for result in results:
        for hit in result["hits"]:
            item_desc = hit["item_desc"]
            item_image = hit["image_url"].replace("_thumb", "")
            item_id = hit["item_id"]

            if SEARCH_ITEM.lower() in item_desc.lower():
                # Build the link
                item_description = item_desc.split(" ")
                item_description = [
                    "".join([i for i in item if i.isalnum()])
                    for item in item_description
                ]
                path = "--".join(["-".join(item_description), item_id]).lower()

                found.append(
                    dict(
                        item_description=item_desc,
                        item_image=item_image,
                        item_id=item_id,
                        path=path,
                        link=urllib.parse.urljoin(HACHI_PRODUCT_LINK, path),
                    )
                )

    if not found:
        message = f"Your {SEARCH_ITEM} is not available"
        print(message)
    else:
        message = f"""Congratulations, we found your item!
Your {SEARCH_ITEM} is available in {HACHI_SEARCH_PAGE_LINK}
here are the links: """
        print(message)

    message_pack = [message]

    for i, item in enumerate(found):
        message = f"""
Item No: {i + 1}
Description: {item['item_description']}
Link: {item['link']}
Searched from: {HACHI_SEARCH_PAGE_LINK}
Image: {item['item_image']}

    """

        print(message)
        message_pack.append(message)

    if ENABLED_TWILIO and found:
        message_pack.append("Will alert you again in 1 hour if its still there")
        print("Sending Whatsapp messages")

        for to in twillio_whatsapp_to:
            twilio_message = client.messages.create(
                from_=f"whatsapp:{twillio_whatsapp_from}",
                body="\n".join(message_pack),
                to=f"whatsapp:{to}",
            )
        print(twilio_message.sid)


def remind_renew_sandbox():
    time_now = datetime.datetime.now()
    global sandbox_expiry
    if time_now >= sandbox_expiry:

        for to in twillio_whatsapp_to:
            twilio_message = client.messages.create(
                from_=f"whatsapp:{twillio_whatsapp_from}",
                body=f"Reminder to rejoin sandbox via replying to this message with {sandbox_rejoin_message}",
                to=f"whatsapp:{to}",
            )
        # Remind in another 72 hours, But user not receive anymore reminders nor messages if they did not renew their lease
        sandbox_expiry = datetime.datetime.now() + datetime.timedelta(hours=72)


if __name__ == "__main__":
    while True:
        while not found:
            main()
            remind_renew_sandbox()
            time.sleep(1)  # We ping every 1 second until found

        # When found and user is alerted, we don't want to spam, so we set a longer timer of 1 hour
        # Then we reset the found into false so that it goes to the top loop
        print("Sleeping for 1 hour before alerting user again")
        found = False
        time.sleep(3600)
