[out:json][timeout:90];
(
  // Tourism
  node["tourism"~"^(attraction|viewpoint|museum|gallery|hotel|resort|guest_house|hostel|zoo|aquarium|theme_park)$"]["name"](15.95,107.95,16.20,108.35);
  way["tourism"~"^(attraction|viewpoint|museum|gallery|hotel|resort|guest_house|hostel|zoo|aquarium|theme_park)$"]["name"](15.95,107.95,16.20,108.35);
  relation["tourism"~"^(attraction|viewpoint|museum|gallery|hotel|resort|guest_house|hostel|zoo|aquarium|theme_park)$"]["name"](15.95,107.95,16.20,108.35);

  // Amenity
  node["amenity"~"^(restaurant|cafe|food_court|fast_food|place_of_worship|marketplace|ferry_terminal|bar|pub|nightclub)$"]["name"](15.95,107.95,16.20,108.35);
  way["amenity"~"^(restaurant|cafe|food_court|fast_food|place_of_worship|marketplace|ferry_terminal|bar|pub|nightclub)$"]["name"](15.95,107.95,16.20,108.35);
  relation["amenity"~"^(place_of_worship|marketplace|ferry_terminal)$"]["name"](15.95,107.95,16.20,108.35);

  // Historic
  node["historic"~"^(monument|memorial|castle|ruins|archaeological_site)$"]["name"](15.95,107.95,16.20,108.35);
  way["historic"~"^(monument|memorial|castle|ruins|archaeological_site)$"]["name"](15.95,107.95,16.20,108.35);
  relation["historic"~"^(monument|memorial|castle|ruins|archaeological_site)$"]["name"](15.95,107.95,16.20,108.35);

  // Natural (beaches, cave entrances)
  node["natural"~"^(beach|cave_entrance)$"]["name"](15.95,107.95,16.20,108.35);
  way["natural"~"^(beach|cave_entrance)$"]["name"](15.95,107.95,16.20,108.35);

  // Leisure
  node["leisure"~"^(park|beach_resort)$"]["name"](15.95,107.95,16.20,108.35);
  way["leisure"~"^(park|beach_resort)$"]["name"](15.95,107.95,16.20,108.35);
  relation["leisure"="park"]["name"](15.95,107.95,16.20,108.35);

  // Shop
  node["shop"="mall"]["name"](15.95,107.95,16.20,108.35);
  way["shop"="mall"]["name"](15.95,107.95,16.20,108.35);

  // Place island
  node["place"="island"]["name"](15.95,107.95,16.20,108.35);
  way["place"="island"]["name"](15.95,107.95,16.20,108.35);
);
out center meta;
