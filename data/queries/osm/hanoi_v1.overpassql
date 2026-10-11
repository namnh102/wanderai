[out:json][timeout:90];
(
  // Tourism
  node["tourism"~"^(attraction|viewpoint|museum|gallery|hotel|resort|guest_house|hostel|zoo|aquarium|theme_park)$"]["name"](20.95,105.75,21.15,105.95);
  way["tourism"~"^(attraction|viewpoint|museum|gallery|hotel|resort|guest_house|hostel|zoo|aquarium|theme_park)$"]["name"](20.95,105.75,21.15,105.95);
  relation["tourism"~"^(attraction|viewpoint|museum|gallery|hotel|resort|guest_house|hostel|zoo|aquarium|theme_park)$"]["name"](20.95,105.75,21.15,105.95);

  // Amenity
  node["amenity"~"^(restaurant|cafe|food_court|fast_food|place_of_worship|marketplace|ferry_terminal|bar|pub|nightclub)$"]["name"](20.95,105.75,21.15,105.95);
  way["amenity"~"^(restaurant|cafe|food_court|fast_food|place_of_worship|marketplace|ferry_terminal|bar|pub|nightclub)$"]["name"](20.95,105.75,21.15,105.95);
  relation["amenity"~"^(place_of_worship|marketplace|ferry_terminal)$"]["name"](20.95,105.75,21.15,105.95);

  // Historic
  node["historic"~"^(monument|memorial|castle|ruins|archaeological_site)$"]["name"](20.95,105.75,21.15,105.95);
  way["historic"~"^(monument|memorial|castle|ruins|archaeological_site)$"]["name"](20.95,105.75,21.15,105.95);
  relation["historic"~"^(monument|memorial|castle|ruins|archaeological_site)$"]["name"](20.95,105.75,21.15,105.95);

  // Natural
  node["natural"~"^(beach|cave_entrance)$"]["name"](20.95,105.75,21.15,105.95);
  way["natural"~"^(beach|cave_entrance)$"]["name"](20.95,105.75,21.15,105.95);

  // Leisure
  node["leisure"~"^(park|beach_resort)$"]["name"](20.95,105.75,21.15,105.95);
  way["leisure"~"^(park|beach_resort)$"]["name"](20.95,105.75,21.15,105.95);
  relation["leisure"="park"]["name"](20.95,105.75,21.15,105.95);

  // Shop
  node["shop"="mall"]["name"](20.95,105.75,21.15,105.95);
  way["shop"="mall"]["name"](20.95,105.75,21.15,105.95);

  // Place island
  node["place"="island"]["name"](20.95,105.75,21.15,105.95);
  way["place"="island"]["name"](20.95,105.75,21.15,105.95);
);
out center meta;
