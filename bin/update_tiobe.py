#!/usr/bin/env python3
"""Update docs/data/tiobe-perl.csv with the latest Perl entry from the TIOBE index.

Logic
-----
1. If the CSV already has a git commit this calendar month, exit (nothing to do).
2. Fetch https://www.tiobe.com/tiobe-index/
3. Parse the page header to find the month/year the data is for.
4. If that month/year is not the current calendar month, exit (TIOBE hasn't
   updated yet).
5. Find Perl in one of the two language tables on the page:
   - Table 0 (top-20): position, ratings, and change are all available.
   - Table 1 (21-50): only position and ratings are shown; the change value is
     calculated by comparing with the same month one year ago in the CSV.
6. Append a new row to the CSV.
"""

import csv
import re
import subprocess
import sys
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

CSV_PATH = "docs/data/tiobe-perl.csv"
TIOBE_URL = "https://www.tiobe.com/tiobe-index/"

MONTH_NAMES = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}

# Matches a percentage value with an optional leading sign, e.g. "1.97%", "+0.63%", "-0.12%"
PERCENT_RE = re.compile(r"^[+-]?\d+\.?\d*%$")


def check_already_updated():
    """Return True if the CSV has a git commit in the current calendar month."""
    now = date.today()
    result = subprocess.run(
        ["git", "log", "--format=%ci", "--", CSV_PATH],
        capture_output=True, text=True, check=True,
    )
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        commit_date = datetime.fromisoformat(line.strip().split()[0]).date()
        if commit_date.year == now.year and commit_date.month == now.month:
            return True
    return False


def fetch_page(url):
    """Fetch *url* and return a BeautifulSoup object."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) "
            "Gecko/20100101 Firefox/120.0"
        )
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def parse_tiobe_month(soup):
    """Extract (year, month_number) from 'TIOBE Index for Month Year' text.

    Returns ``(None, None)`` if the heading cannot be found.
    """
    pattern = (
        r"TIOBE Index for\s+(" + "|".join(MONTH_NAMES.keys()) + r")\s+(\d{4})"
    )
    m = re.search(pattern, soup.get_text(" ", strip=True))
    if m:
        return int(m.group(2)), MONTH_NAMES[m.group(1)]
    return None, None


def parse_percent(s):
    """Convert a percentage string like '1.97%' or '+0.63%' to a float fraction."""
    return float(s.strip().rstrip("%").replace("+", "")) / 100


def find_perl_in_tables(soup):
    """Search all ``<table>`` elements for a row that contains exactly 'Perl'.

    Returns ``(position, ratings, change, table_index)`` where *change* may be
    ``None`` if the table does not provide it.  Returns ``(None, None, None,
    None)`` if Perl cannot be found.
    """
    for table_idx, table in enumerate(soup.find_all("table")):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            cell_texts = [c.get_text(strip=True) for c in cells]

            if "Perl" not in cell_texts:
                continue

            # Collect all plain integers (candidate positions) and all
            # percentage values in the row.
            integers = []
            percents = []
            for text in cell_texts:
                if re.match(r"^\d+$", text):
                    integers.append(int(text))
                elif PERCENT_RE.match(text):
                    percents.append(parse_percent(text))

            position = integers[0] if integers else None
            ratings = percents[0] if percents else None
            change = percents[1] if len(percents) > 1 else None

            return position, ratings, change, table_idx

    return None, None, None, None


def read_csv_rows():
    """Read and return all rows from the CSV as a list of dicts."""
    rows = []
    with open(CSV_PATH, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def get_rating_for_month(rows, year, month):
    """Return the *Ratings* float for the given *year*/*month*, or ``None``."""
    for row in rows:
        try:
            if int(row["Year"]) == year and int(row["Month"]) == month:
                raw = row.get("Ratings", "")
                return float(raw) if raw else None
        except (ValueError, KeyError):
            pass
    return None


def append_csv_row(year, month, position, ratings, change):
    """Append a new data row to the CSV file."""
    ratings_str = f"{ratings:.4f}" if ratings is not None else ""
    change_str = f"{change:.4f}" if change is not None else ""
    with open(CSV_PATH, "a", newline="") as f:
        f.write(f"{year},{month},{position},{ratings_str},{change_str}\n")


def main():
    # Step 1: skip if the CSV was already committed this month.
    if check_already_updated():
        print("CSV already has a commit this calendar month — nothing to do.")
        return

    now = date.today()

    # Step 2: fetch the TIOBE index page.
    print(f"Fetching {TIOBE_URL} …")
    soup = fetch_page(TIOBE_URL)

    # Step 3: check which month the page covers.
    tiobe_year, tiobe_month = parse_tiobe_month(soup)
    if tiobe_year is None:
        print("ERROR: Could not parse TIOBE month/year from page.", file=sys.stderr)
        sys.exit(1)

    print(f"TIOBE page reports data for {tiobe_month}/{tiobe_year}.")

    # Step 4: exit if TIOBE hasn't updated for the current month yet.
    if tiobe_year != now.year or tiobe_month != now.month:
        print(
            f"TIOBE data is for {tiobe_month}/{tiobe_year}, "
            f"but today is {now} — nothing to do."
        )
        return

    # Step 5: find Perl in one of the tables.
    position, ratings, change, table_idx = find_perl_in_tables(soup)
    if position is None:
        print("ERROR: Could not find Perl in any TIOBE table.", file=sys.stderr)
        sys.exit(1)

    in_top20 = table_idx == 0
    print(
        f"Perl found in table {table_idx} (top-20={in_top20}): "
        f"position={position}, ratings={ratings}, change={change}"
    )

    # If Perl is in the 21-50 table, calculate the change from one year ago.
    if not in_top20:
        rows = read_csv_rows()
        prev_rating = get_rating_for_month(rows, tiobe_year - 1, tiobe_month)
        if prev_rating is not None and ratings is not None:
            change = ratings - prev_rating
            print(
                f"Calculated change vs {tiobe_month}/{tiobe_year - 1}: {change:.4f}"
            )
        else:
            change = None
            print("No previous-year rating found; change will be empty.")

    # Step 6: append the new row.
    append_csv_row(tiobe_year, tiobe_month, position, ratings, change)
    print(
        f"Appended: {tiobe_year},{tiobe_month},{position},"
        f"{ratings},{change}"
    )


if __name__ == "__main__":
    main()
