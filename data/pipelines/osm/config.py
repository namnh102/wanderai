"""Configuration and taxonomy mapping for OpenStreetMap ingestion."""

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Vietnam Geographic Bounding Box
VIETNAM_BBOX = {
    "min_lat": 8.18,
    "max_lat": 23.39,
    "min_lon": 102.14,
    "max_lon": 109.46,
}

# Key Pilot Tourism Destinations in Vietnam with bounding boxes
PILOT_REGIONS = {
    "da_nang": {"min_lat": 15.90, "min_lon": 108.05, "max_lat": 16.20, "max_lon": 108.35},
    "hanoi": {"min_lat": 20.95, "min_lon": 105.75, "max_lat": 21.15, "max_lon": 105.95},
    "hoi_an": {"min_lat": 15.85, "min_lon": 108.30, "max_lat": 15.92, "max_lon": 108.40},
    "nha_trang": {"min_lat": 12.18, "min_lon": 109.15, "max_lat": 12.32, "max_lon": 109.25},
    "hue": {"min_lat": 16.42, "min_lon": 107.54, "max_lat": 16.50, "max_lon": 107.65},
}

# GoMate category mapping from OSM tags
OSM_TAG_CATEGORY_MAP = {
    # Tourism
    ("tourism", "attraction"): "attraction",
    ("tourism", "viewpoint"): "nature",
    ("tourism", "museum"): "culture",
    ("tourism", "artwork"): "culture",
    ("tourism", "hotel"): "hotel",
    ("tourism", "guest_house"): "hotel",
    ("tourism", "hostel"): "hotel",
    ("tourism", "resort"): "hotel",
    ("tourism", "theme_park"): "entertainment",
    ("tourism", "zoo"): "nature",
    
    # Historic
    ("historic", "monument"): "culture",
    ("historic", "memorial"): "culture",
    ("historic", "castle"): "culture",
    ("historic", "ruins"): "culture",
    ("historic", "archaeological_site"): "culture",
    ("historic", "building"): "culture",

    # Amenity
    ("amenity", "restaurant"): "restaurant",
    ("amenity", "cafe"): "cafe",
    ("amenity", "fast_food"): "restaurant",
    ("amenity", "food_court"): "restaurant",
    ("amenity", "place_of_worship"): "culture",

    # Leisure
    ("leisure", "park"): "nature",
    ("leisure", "beach_resort"): "beach",
    ("natural", "beach"): "beach",
}
