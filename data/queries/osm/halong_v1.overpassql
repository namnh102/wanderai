[out:json][timeout:90];
(
  // Tourism
  node["tourism"~"^(attraction|viewpoint|museum|gallery|hotel|resort|guest_house|hostel|zoo|aquarium|theme_park)$"]["name"](20.85,106.95,21.05,107.25);
  way["tourism"~"^(attraction|viewpoint|museum|gallery|hotel|resort|guest_house|hostel|zoo|aquarium|theme_park)$"]["name"](20.85,106.95,21.05,107.25);
  relation["tourism"~"^(attraction|viewpoint|museum|gallery|hotel|resort|guest_house|hostel|zoo|aquarium|theme_park)$"]["name"](20.85,106.95,21.05,107.25);

  // Amenity
  node["amenity"~"^(restaurant|cafe|food_court|fast_food|place_of_worship|marketplace|ferry_terminal|bar|pub|nightclub)$"]["name"](20.85,106.95,21.05,107.25);
  way["amenity"~"^(restaurant|cafe|food_court|fast_food|place_of_worship|marketplace|ferry_terminal|bar|pub|nightclub)$"]["name"](20.85,106.95,21.05,107.25);

  // Historic
  node["historic"~"^(monument|memorial|castle|ruins|archaeological_site)$"]["name"](20.85,106.95,21.05,107.25);
  way["historic"~"^(monument|memorial|castle|ruins|archaeological_site)$"]["name"](20.85,106.95,21.05,107.25);
  relation["historic"~"^(monument|memorial|castle|ruins|archaeological_site)$"]["name"](20.85,106.95,21.05,107.25);

  // Natural (beaches, cave entrances)
  node["natural"~"^(beach|cave_entrance)$"]["name"](20.85,106.95,21.05,107.25);
  way["natural"~"^(beach|cave_entrance)$"]["name"](20.85,106.95,21.05,107.25);

  // Leisure
  node["leisure"~"^(park|beach_resort)$"]["name"](20.85,106.95,21.05,107.25);
  way["leisure"~"^(park|beach_resort)$"]["name"](20.85,106.95,21.05,107.25);

  // Shop
  node["shop"="mall"]["name"](20.85,106.95,21.05,107.25);
  way["shop"="mall"]["name"](20.85,106.95,21.05,107.25);

  // Place island (requires name)
  node["place"="island"]["name"](20.85,106.95,21.05,107.25);
  way["place"="island"]["name"](20.85,106.95,21.05,107.25);
);
out center meta;
