import streamlit as st
import requests
import pandas as pd
import re
from urllib.parse import urljoin


# =========================================================
# 🔐 LOGIN CREDENTIALS
# =========================================================
# ضع الإيميلات والباسوردات هنا
#
# مثال:
# "myemail@gmail.com": "MyPassword123"
#
# يمكنك إضافة أكثر من مستخدم.

USERS = {
    "beso_*@gmail.com": "beso_*",
    "second-email@gmail.com": "SECOND_PASSWORD",
}


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Business Data Scraper",
    page_icon="🔎",
    layout="wide"
)


# =========================================================
# LOGIN SYSTEM
# =========================================================

def check_login(email, password):

    email = email.strip().lower()

    return (
        email in USERS
        and USERS[email] == password
    )


def login_page():

    st.markdown(
        """
        <style>

        .login-box {
            max-width: 500px;
            margin: 100px auto;
            padding: 35px;
            border-radius: 15px;
            border: 1px solid #ddd;
        }

        </style>
        """,
        unsafe_allow_html=True
    )

    st.title("🔐 Business Data Scraper")

    st.write(
        "Please login to continue."
    )

    with st.form("login_form"):

        email = st.text_input(
            "📧 Email",
            placeholder="Enter your email"
        )

        password = st.text_input(
            "🔑 Password",
            type="password",
            placeholder="Enter your password"
        )

        login = st.form_submit_button(
            "Login",
            use_container_width=True
        )

        if login:

            if not email or not password:

                st.error(
                    "Please enter your email and password."
                )

            elif check_login(
                email,
                password
            ):

                st.session_state[
                    "authenticated"
                ] = True

                st.rerun()

            else:

                st.error(
                    "❌ Invalid email or password."
                )


# =========================================================
# AUTHENTICATION
# =========================================================

if "authenticated" not in st.session_state:

    st.session_state[
        "authenticated"
    ] = False


if not st.session_state["authenticated"]:

    login_page()

    st.stop()


# =========================================================
# LOGOUT
# =========================================================

with st.sidebar:

    st.success("🟢 Logged in")

    if st.button(
        "🚪 Logout",
        use_container_width=True
    ):

        st.session_state[
            "authenticated"
        ] = False

        st.session_state.pop(
            "results",
            None
        )

        st.rerun()


# =========================================================
# API SETTINGS
# =========================================================

NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/search"
)


OVERPASS_SERVERS = [

    "https://overpass-api.de/api/interpreter",

    "https://overpass.kumi.systems/api/interpreter",

    "https://overpass.private.coffee/api/interpreter"

]


HEADERS = {

    "User-Agent":
        "BusinessDataScraper/1.0",

    "Accept":
        "application/json"

}


# =========================================================
# LOCATION SEARCH
# =========================================================

def get_location_coordinates(location):

    params = {

        "q": location,

        "format": "json",

        "limit": 1

    }

    response = requests.get(

        NOMINATIM_URL,

        params=params,

        headers={
            "User-Agent":
            "BusinessDataScraper/1.0"
        },

        timeout=30

    )

    response.raise_for_status()

    data = response.json()

    if not data:

        return None

    return {

        "lat":
            float(data[0]["lat"]),

        "lon":
            float(data[0]["lon"]),

        "name":
            data[0]["display_name"]

    }


# =========================================================
# CATEGORY MAPPING
# =========================================================

def get_category_filter(category):

    category = (
        category
        .lower()
        .strip()
    )

    categories = {

        "restaurant":
            '["amenity"="restaurant"]',

        "restaurants":
            '["amenity"="restaurant"]',

        "cafe":
            '["amenity"="cafe"]',

        "cafes":
            '["amenity"="cafe"]',

        "hotel":
            '["tourism"="hotel"]',

        "hotels":
            '["tourism"="hotel"]',

        "pharmacy":
            '["amenity"="pharmacy"]',

        "pharmacies":
            '["amenity"="pharmacy"]',

        "hospital":
            '["amenity"="hospital"]',

        "hospitals":
            '["amenity"="hospital"]',

        "school":
            '["amenity"="school"]',

        "schools":
            '["amenity"="school"]',

        "bank":
            '["amenity"="bank"]',

        "banks":
            '["amenity"="bank"]',

        "bakery":
            '["shop"="bakery"]',

        "bakeries":
            '["shop"="bakery"]',

        "supermarket":
            '["shop"="supermarket"]',

        "supermarkets":
            '["shop"="supermarket"]',

        "gym":
            '["leisure"="fitness_centre"]',

        "gyms":
            '["leisure"="fitness_centre"]',

        "dentist":
            '["amenity"="dentist"]',

        "dentists":
            '["amenity"="dentist"]',

        "salon":
            '["shop"="beauty"]',

        "beauty salon":
            '["shop"="beauty"]',

        "car wash":
            '["amenity"="car_wash"]',

        "carwash":
            '["amenity"="car_wash"]',

    }

    if category in categories:

        return categories[category]

    # Generic category/name search

    safe_category = (
        category
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )

    return (
        f'[name~"{safe_category}",i]'
    )


# =========================================================
# OVERPASS REQUEST
# =========================================================

def query_overpass(query):

    last_error = None

    for server in OVERPASS_SERVERS:

        try:

            response = requests.post(

                server,

                data={
                    "data": query
                },

                headers={
                    **HEADERS,
                    "Content-Type":
                    "application/x-www-form-urlencoded"
                },

                timeout=120

            )

            if response.status_code == 200:

                return response.json()

            last_error = (
                f"HTTP {response.status_code}"
            )

        except requests.RequestException as e:

            last_error = str(e)

    raise Exception(
        "All search servers failed. "
        f"Last error: {last_error}"
    )


# =========================================================
# BUSINESS SCRAPER
# =========================================================

def scrape_businesses(
    location,
    category,
    radius
):

    coordinates = (
        get_location_coordinates(
            location
        )
    )

    if not coordinates:

        return pd.DataFrame()

    lat = coordinates["lat"]

    lon = coordinates["lon"]

    category_filter = (
        get_category_filter(
            category
        )
    )

    query = f"""
[out:json][timeout:120];

(
    node{category_filter}
    (around:{radius},{lat},{lon});

    way{category_filter}
    (around:{radius},{lat},{lon});

    relation{category_filter}
    (around:{radius},{lat},{lon});
);

out center tags;
"""

    data = query_overpass(
        query
    )

    elements = data.get(
        "elements",
        []
    )

    results = []

    for element in elements:

        tags = element.get(
            "tags",
            {}
        )

        # -------------------------------------
        # Coordinates
        # -------------------------------------

        if element.get("type") == "node":

            latitude = element.get(
                "lat"
            )

            longitude = element.get(
                "lon"
            )

        else:

            center = element.get(
                "center",
                {}
            )

            latitude = center.get(
                "lat"
            )

            longitude = center.get(
                "lon"
            )

        # -------------------------------------
        # Business name
        # -------------------------------------

        name = tags.get(
            "name",
            ""
        )

        if not name:

            continue

        # -------------------------------------
        # Address
        # -------------------------------------

        address_parts = [

            tags.get(
                "addr:housenumber",
                ""
            ),

            tags.get(
                "addr:street",
                ""
            ),

            tags.get(
                "addr:city",
                ""
            ),

            tags.get(
                "addr:postcode",
                ""
            )

        ]

        address = ", ".join(

            part

            for part in address_parts

            if part

        )

        # -------------------------------------
        # Phone
        # -------------------------------------

        phone = (

            tags.get("phone")

            or tags.get(
                "contact:phone"
            )

            or tags.get(
                "contact:mobile"
            )

            or ""

        )

        # -------------------------------------
        # Website
        # -------------------------------------

        website = (

            tags.get("website")

            or tags.get(
                "contact:website"
            )

            or tags.get("url")

            or ""

        )

        # -------------------------------------
        # Email
        # -------------------------------------

        email = (

            tags.get("email")

            or tags.get(
                "contact:email"
            )

            or ""

        )

        # -------------------------------------
        # Category
        # -------------------------------------

        business_type = (

            tags.get("amenity")

            or tags.get("shop")

            or tags.get("tourism")

            or tags.get("leisure")

            or ""

        )

        # -------------------------------------
        # Save
        # -------------------------------------

        results.append({

            "Name":
                name,

            "Phone":
                phone,

            "Email":
                email,

            "Website":
                website,

            "Address":
                address,

            "City":
                tags.get(
                    "addr:city",
                    ""
                ),

            "Country":
                tags.get(
                    "addr:country",
                    ""
                ),

            "Category":
                business_type,

            "Cuisine":
                tags.get(
                    "cuisine",
                    ""
                ),

            "Opening Hours":
                tags.get(
                    "opening_hours",
                    ""
                ),

            "Latitude":
                latitude,

            "Longitude":
                longitude,

            "Social Media":
                ""

        })

    df = pd.DataFrame(
        results
    )

    if df.empty:

        return df

    # Remove duplicates

    df = df.drop_duplicates(
        subset=[
            "Name",
            "Latitude",
            "Longitude"
        ]
    )

    return df.reset_index(
        drop=True
    )


# =========================================================
# EMAIL EXTRACTION
# =========================================================

def extract_emails(text):

    pattern = (
        r"[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    )

    emails = re.findall(
        pattern,
        text
    )

    return list(
        dict.fromkeys(
            emails
        )
    )


# =========================================================
# WEBSITE SCRAPER
# =========================================================

def scrape_website(url):

    if not url:

        return "", ""

    if not url.startswith(
        (
            "http://",
            "https://"
        )
    ):

        url = (
            "https://" +
            url
        )

    try:

        response = requests.get(

            url,

            headers={
                "User-Agent":
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/120 Safari/537.36"
            },

            timeout=15

        )

        if response.status_code != 200:

            return "", ""

        html = response.text

        # -------------------------------------
        # Emails
        # -------------------------------------

        emails = extract_emails(
            html
        )

        email = (
            emails[0]
            if emails
            else ""
        )

        # -------------------------------------
        # Social Media
        # -------------------------------------

        social_domains = [

            "facebook.com",

            "instagram.com",

            "linkedin.com",

            "twitter.com",

            "x.com",

            "tiktok.com"

        ]

        links = re.findall(

            r'href=["\'](.*?)["\']',

            html,

            re.IGNORECASE

        )

        socials = []

        for link in links:

            full_url = urljoin(
                url,
                link
            )

            if any(
                domain
                in full_url.lower()
                for domain in social_domains
            ):

                if full_url not in socials:

                    socials.append(
                        full_url
                    )

        return (

            email,

            " | ".join(
                socials
            )

        )

    except Exception:

        return "", ""


# =========================================================
# WEBSITE ENRICHMENT
# =========================================================

def enrich_websites(df):

    total = len(df)

    progress = st.progress(
        0
    )

    for i in range(total):

        website = df.at[
            i,
            "Website"
        ]

        if website:

            email, socials = (
                scrape_website(
                    website
                )
            )

            # Only fill empty email

            if not df.at[
                i,
                "Email"
            ]:

                df.at[
                    i,
                    "Email"
                ] = email

            df.at[
                i,
                "Social Media"
            ] = socials

        progress.progress(
            (i + 1) / total
        )

    progress.empty()

    return df


# =========================================================
# MAIN APP
# =========================================================

st.title(
    "🔎 Business Data Scraper"
)

st.caption(
    "Find businesses by location and service."
)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header(
        "⚙️ Search Settings"
    )

    location = st.text_input(
        "📍 Location",
        placeholder="Cairo"
    )

    category = st.text_input(
        "🏷️ Service / Category",
        placeholder="Restaurant"
    )

    radius = st.slider(
        "📏 Search Radius",
        min_value=1000,
        max_value=50000,
        value=10000,
        step=1000
    )

    st.caption(
        "Radius is measured in meters."
    )

    scrape_button = st.button(
        "🚀 Start Scraping",
        use_container_width=True
    )


# =========================================================
# START SCRAPING
# =========================================================

if scrape_button:

    if not location.strip():

        st.error(
            "Please enter a location."
        )

    elif not category.strip():

        st.error(
            "Please enter a service/category."
        )

    else:

        with st.spinner(
            "🔎 Searching for businesses..."
        ):

            try:

                df = scrape_businesses(
                    location,
                    category,
                    radius
                )

                if df.empty:

                    st.warning(
                        "No businesses were found."
                    )

                else:

                    st.session_state[
                        "results"
                    ] = df

                    st.success(
                        f"Found {len(df):,} businesses."
                    )

            except Exception as error:

                st.error(
                    f"Scraping error: {error}"
                )


# =========================================================
# RESULTS
# =========================================================

if "results" in st.session_state:

    df = st.session_state[
        "results"
    ]

    st.subheader(
        "📊 Business Results"
    )

    # -------------------------------------
    # Statistics
    # -------------------------------------

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    col1.metric(
        "🏢 Businesses",
        f"{len(df):,}"
    )

    col2.metric(
        "📞 Phones",
        df["Phone"]
        .replace("", pd.NA)
        .count()
    )

    col3.metric(
        "📧 Emails",
        df["Email"]
        .replace("", pd.NA)
        .count()
    )

    col4.metric(
        "🌐 Websites",
        df["Website"]
        .replace("", pd.NA)
        .count()
    )

    st.divider()

    # -------------------------------------
    # Website Scan
    # -------------------------------------

    if st.button(
        "🌐 Scan Websites for Emails & Social Media",
        use_container_width=True
    ):

        with st.spinner(
            "Scanning websites..."
        ):

            enriched_df = (
                enrich_websites(
                    df.copy()
                )
            )

            st.session_state[
                "results"
            ] = enriched_df

            st.success(
                "Website scanning completed."
            )

            st.rerun()

    # -------------------------------------
    # Search results
    # -------------------------------------

    search = st.text_input(
        "🔍 Filter Results",
        placeholder=(
            "Search by name, phone, email, "
            "website or address..."
        )
    )

    filtered_df = df.copy()

    if search.strip():

        search_lower = (
            search.lower()
        )

        mask = (
            filtered_df
            .astype(str)
            .apply(

                lambda row:

                row.str
                .lower()
                .str.contains(
                    search_lower,
                    na=False
                )
                .any(),

                axis=1

            )
        )

        filtered_df = (
            filtered_df[mask]
        )

    st.write(
        f"Showing **{len(filtered_df):,}** results"
    )

    # -------------------------------------
    # Data table
    # -------------------------------------

    st.dataframe(

        filtered_df,

        use_container_width=True,

        height=600,

        hide_index=True

    )

    # -------------------------------------
    # CSV
    # -------------------------------------

    csv = (
        filtered_df
        .to_csv(
            index=False
        )
        .encode("utf-8-sig")
    )

    st.download_button(

        "⬇️ Download CSV",

        data=csv,

        file_name="business_data.csv",

        mime="text/csv",

        use_container_width=True

    )

else:

    st.info(
        "👈 Enter a location and service "
        "from the sidebar, then click "
        "'Start Scraping'."
    )
