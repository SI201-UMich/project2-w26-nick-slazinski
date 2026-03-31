# SI 201 HW4 (Library Checkout System)
# Your name: Nicholas Slazinski
# Your student id: 4426 2981
# Your email: nslazins@umich.edu
# Who or what you worked with on this homework (including generative AI like ChatGPT): ChatGPT
# If you worked with generative AI also add a statement for how you used it.
# e.g.: Used chat to help me debug my code by telling me where my code was failng. I then fixed the code on my own. All final code is mine.
# Asked ChatGPT for hints on debugging and for suggestions on overall code structure
#
# Did your use of GenAI on this assignment align with your goals and guidelines in your Gen AI contract? If not, why? Yes
#
# --- ARGUMENTS & EXPECTED RETURN VALUES PROVIDED --- #
# --- SEE INSTRUCTIONS FOR FULL DETAILS ON METHOD IMPLEMENTATION --- #

from bs4 import BeautifulSoup
import re
import os
import csv
import unittest
import requests  # kept for extra credit parity


# IMPORTANT NOTE:
"""
If you are getting "encoding errors" while trying to open, read, or write from a file, add the following argument to any of your open() functions:
    encoding="utf-8-sig"

"""

def load_listing_results(html_path) -> list[tuple]:
    """
    Load file data from html_path and parse through it to find listing titles and listing ids.

    Args:
        html_path (str): The path to the HTML file containing the search results

    Returns:
        list[tuple]: A list of tuples containing (listing_title, listing_id)
    """
    html = ""
    with open(html_path, "r", encoding="utf-8-sig") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    listings = []
    seen_ids = set()

    pattern = re.compile(
        r'"id":"(\d+)"(?:(?!\"id\":).){0,5000}?"title":"([^"]+)"',
        re.DOTALL
    )

    for match in pattern.finditer(html):
        listing_id = match.group(1)
        listing_title = re.sub(r"\s+", " ", match.group(2)).strip()

        if listing_id not in seen_ids and listing_title:
            listings.append((listing_title, listing_id))
            seen_ids.add(listing_id)

    if not listings:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            room_match = re.search(r"/rooms/(\d+)", href)
            if room_match:
                listing_id = room_match.group(1)
                if listing_id in seen_ids:
                    continue

                listing_title = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
                if listing_title:
                    listings.append((listing_title, listing_id))
                    seen_ids.add(listing_id)

    return listings


def get_listing_details(listing_id) -> dict:
    """
    Parse through listing_<id>.html to extract listing details.

    Args:
        listing_id (str): The listing id of the Airbnb listing

    Returns:
        dict: Nested dictionary in the format:
        {
            "<listing_id>": {
                "policy_number": str,
                "host_type": str,
                "host_name": str,
                "room_type": str,
                "location_rating": float
            }
        }
    """
    base_dir = os.path.abspath(os.path.dirname(__file__))
    html_path = os.path.join(base_dir, "html_files", f"listing_{listing_id}.html")

    with open(html_path, "r", encoding="utf-8-sig") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()

    # policy number
    exact_match = re.search(r"\b(20\d{2}-00\d{4}STR|STR-000\d{4})\b", text)
    if exact_match:
        policy_number = exact_match.group(1)
    else:
        loose_match = re.search(r"\b(20\d{2}-\d{5,7}STR|STR-\d{6,8})\b", text)
        if loose_match:
            policy_number = loose_match.group(1)
        elif "exempt" in text.lower():
            policy_number = "Exempt"
        elif "pending" in text.lower():
            policy_number = "Pending"
        else:
            policy_number = "Pending"

    # host type
    if "superhost" in text.lower():
        host_type = "Superhost"
    else:
        host_type = "regular"

    # host name
    host_name = ""
    host_patterns = [
        r"Hosted by ([A-Z][A-Za-z'&\- ]+)",
        r"([A-Z][A-Za-z'&\- ]+) is a Superhost",
        r"Meet your host,\s*([A-Z][A-Za-z'&\- ]+)"
    ]

    for pattern in host_patterns:
        match = re.search(pattern, text)
        if match:
            host_name = re.sub(r"\s+", " ", match.group(1)).strip()
            host_name = re.sub(r"\s+Reviews?.*$", "", host_name)
            host_name = re.sub(r"\s+Policy number:.*$", "", host_name)
            break

    if host_name == "":
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/users/show/" in href:
                aria = re.sub(r"\s+", " ", a.get("aria-label", "")).strip()
                visible = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()

                for candidate in [aria, visible]:
                    if candidate and re.fullmatch(r"[A-Z][A-Za-z'&\- ]{1,40}", candidate):
                        host_name = candidate
                        break
            if host_name != "":
                break

    # room type
    lowered = text.lower()
    title_tag = soup.find("title")
    title_text = title_tag.get_text(" ", strip=True).lower() if title_tag else ""

    meta_desc = ""
    meta = soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        meta_desc = meta["content"].lower()

    combined_text = lowered + " " + title_text + " " + meta_desc

    if "private room" in combined_text or re.search(r"\bprivate\b", combined_text):
        room_type = "Private Room"
    elif "shared room" in combined_text or re.search(r"\bshared\b", combined_text):
        room_type = "Shared Room"
    else:
        room_type = "Entire Room"

    # location rating
    location_rating = 0.0
    rating_patterns = [
        r"Rated\s+([0-5](?:\.\d)?)\s+out of 5 for location",
        r"Location[^0-9]{0,30}([0-5]\.\d)",
        r'"location[^"]*"\s*:\s*"([0-5]\.\d)"'
    ]

    for pattern in rating_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            location_rating = float(match.group(1))
            break

    return {
        listing_id: {
            "policy_number": policy_number,
            "host_type": host_type,
            "host_name": host_name,
            "room_type": room_type,
            "location_rating": location_rating
        }
    }


def create_listing_database(html_path) -> list[tuple]:
    """
    Use prior functions to gather all necessary information and create a database of listings.

    Args:
        html_path (str): The path to the HTML file containing the search results

    Returns:
        list[tuple]: A list of tuples. Each tuple contains:
        (listing_title, listing_id, policy_number, host_type, host_name, room_type, location_rating)
    """
    listing_results = load_listing_results(html_path)
    database = []

    for listing_title, listing_id in listing_results:
        details = get_listing_details(listing_id)[listing_id]

        database.append((
            listing_title,
            listing_id,
            details["policy_number"],
            details["host_type"],
            details["host_name"],
            details["room_type"],
            details["location_rating"]
        ))

    return database


def output_csv(data, filename) -> None:
    """
    Write data to a CSV file with the provided filename.

    Sort by Location Rating (descending).

    Args:
        data (list[tuple]): A list of tuples containing listing information
        filename (str): The name of the CSV file to be created and saved to

    Returns:
        None
    """
    sorted_data = sorted(data, key=lambda row: row[6], reverse=True)

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Listing Title",
            "Listing ID",
            "Policy Number",
            "Host Type",
            "Host Name",
            "Room Type",
            "Location Rating"
        ])

        for row in sorted_data:
            writer.writerow(row)


def avg_location_rating_by_room_type(data) -> dict:
    """
    Calculate the average location_rating for each room_type.

    Excludes rows where location_rating == 0.0 (meaning the rating
    could not be found in the HTML).

    Args:
        data (list[tuple]): The list returned by create_listing_database()

    Returns:
        dict: {room_type: average_location_rating}
    """
    # TODO: Implement checkout logic following the instructions
    # ==============================
    # YOUR CODE STARTS HERE
    # ==============================
    pass
    # ==============================
    # YOUR CODE ENDS HERE
    # ==============================


def validate_policy_numbers(data) -> list[str]:
    """
    Validate policy_number format for each listing in data.
    Ignore "Pending" and "Exempt" listings.

    Args:
        data (list[tuple]): A list of tuples returned by create_listing_database()

    Returns:
        list[str]: A list of listing_id values whose policy numbers do NOT match the valid format
    """
    # TODO: Implement checkout logic following the instructions
    # ==============================
    # YOUR CODE STARTS HERE
    # ==============================
    pass
    # ==============================
    # YOUR CODE ENDS HERE
    # ==============================


# EXTRA CREDIT
def google_scholar_searcher(query):
    """
    EXTRA CREDIT

    Args:
        query (str): The search query to be used on Google Scholar
    Returns:
        List of titles on the first page (list)
    """
    # TODO: Implement checkout logic following the instructions
    # ==============================
    # YOUR CODE STARTS HERE
    # ==============================
    pass
    # ==============================
    # YOUR CODE ENDS HERE
    # ==============================


class TestCases(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.abspath(os.path.dirname(__file__))
        self.search_results_path = os.path.join(self.base_dir, "html_files", "search_results.html")

        self.listings = load_listing_results(self.search_results_path)
        self.detailed_data = create_listing_database(self.search_results_path)

    def test_load_listing_results(self):
        # TODO: Check that the number of listings extracted is 18.
        # TODO: Check that the FIRST (title, id) tuple is  ("Loft in Mission District", "1944564").
        pass

    def test_get_listing_details(self):
        html_list = ["467507", "1550913", "1944564", "4614763", "6092596"]

        # TODO: Call get_listing_details() on each listing id above and save results in a list.

        # TODO: Spot-check a few known values by opening the corresponding listing_<id>.html files.
        # 1) Check that listing 467507 has the correct policy number "STR-0005349".
        # 2) Check that listing 1944564 has the correct host type "Superhost" and room type "Entire Room".
        # 3) Check that listing 1944564 has the correct location rating 4.9.
        pass

    def test_create_listing_database(self):
        # TODO: Check that each tuple in detailed_data has exactly 7 elements:
        # (listing_title, listing_id, policy_number, host_type, host_name, room_type, location_rating)

        # TODO: Spot-check the LAST tuple is ("Guest suite in Mission District", "467507", "STR-0005349", "Superhost", "Jennifer", "Entire Room", 4.8).
        pass

    def test_output_csv(self):
        out_path = os.path.join(self.base_dir, "test.csv")

        # TODO: Call output_csv() to write the detailed_data to a CSV file.
        # TODO: Read the CSV back in and store rows in a list.
        # TODO: Check that the first data row matches ["Guesthouse in San Francisco", "49591060", "STR-0000253", "Superhost", "Ingrid", "Entire Room", "5.0"].

        os.remove(out_path)

    def test_avg_location_rating_by_room_type(self):
        # TODO: Call avg_location_rating_by_room_type() and save the output.
        # TODO: Check that the average for "Private Room" is 4.9.
        pass

    def test_validate_policy_numbers(self):
        # TODO: Call validate_policy_numbers() on detailed_data and save the result into a variable invalid_listings.
        # TODO: Check that the list contains exactly "16204265" for this dataset.
        pass


def main():
    detailed_data = create_listing_database(os.path.join("html_files", "search_results.html"))
    output_csv(detailed_data, "airbnb_dataset.csv")


if __name__ == "__main__":
    main()
    unittest.main(verbosity=2)