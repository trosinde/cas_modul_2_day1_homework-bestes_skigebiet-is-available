import re
import unicodedata


def slugify(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def resort_id(country, name):
    return f"{country.lower()}-{slugify(name)}"


def restaurant_id(country, region, name):
    return f"{country.lower()}-{slugify(region)}-{slugify(name)}"
