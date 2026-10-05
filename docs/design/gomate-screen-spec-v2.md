# GoMate — Screen Specification v2.0

## UI-01 App Shell

Purpose: establish one consistent application frame for mobile, tablet and desktop.

### Mobile
- Top app area: contextual title or compact brand mark.
- Body: scrollable content region.
- Bottom navigation: Khám phá / Bản đồ / Wandy / Chuyến đi / An toàn.
- Primary floating actions only when contextually useful.

### Tablet
- Navigation rail on the left.
- Main content centered.

### Desktop
- Sidebar 232–256px.
- Main content constrained to 720–900px.
- Supporting pane allowed on Map, Place and Trip workflows.

### Global shell rules
- Persistent GoRouter instance.
- No duplicated navigator keys.
- Respect safe areas.
- No full-height Center widgets inside bottom navigation.

## UI-02 Home / Discover

Primary goal: immediately get the user to a useful travel action.

Hierarchy:
1. Greeting / context.
2. Search.
3. Wandy action card.
4. Nearby or personalized places.
5. Destination discovery.

Primary CTA: search or ask Wandy.

Cards must expose only supported facts. Ratings are hidden when unavailable rather than fabricated.

Suggested home copy:
- “Xin chào 👋”
- “Hôm nay bạn muốn khám phá gì?”
- “Tìm địa điểm, món ăn, khách sạn...”

Wandy card:
- “✦ Wandy có thể giúp bạn”
- “Lên lịch chuyến đi”
- “Tìm địa điểm gần bạn”
- “Gợi ý nơi ăn uống”

## UI-03 Search

Search modes:
- place
- restaurant
- hotel
- culture
- nature
- destination

States:
- empty query
- typing suggestions
- recent searches
- results
- no result
- error

Interaction:
- Search field pinned near top.
- Filter chips horizontally scrollable.
- Search results preserve context and do not unexpectedly move the map.

## UI-04 Map

Layers:
- HOT basemap
- category bar
- search bar
- result count
- current location control
- radius control
- POI markers
- optional accuracy circle
- preview sheet

Rules:
- Opening map does not request permission.
- User location action requests permission.
- Current location does not delete or reload POIs.
- Map camera changes only on explicit user action.
- Marker selection does not force camera jumps.

## UI-05 Place Preview

Purpose: fast decision without leaving the map.

Show:
- place name
- category
- verified badge if verified
- user distance if available
- honest rating state
- factual address if available
- primary CTA “Xem chi tiết”

Do not show:
- made-up rating
- guessed address
- unsupported phone/website

## UI-06 Place Detail

Sections:
- hero
- verification
- rating
- key facts
- opening hours
- contact
- location
- provenance
- navigation CTA

Missing data must use explicit unavailable copy.

## UI-07 Wandy

Landing state:
- greeting
- capabilities
- prompt suggestions

Conversation state:
- answer
- sources
- tool result cards
- next actions

Agent state:
- plan
- confirmation
- progress
- result
- undo when possible

## UI-08 Trips

Trip list:
- destination
- dates
- travelers
- status
- upcoming indicator

Trip overview:
- trip header
- summary
- AI planner CTA
- day-by-day itinerary
- budget
- actions

## UI-09 AI Planner Preview

Never write to trip itinerary during preview.

Show:
- days
- items
- estimated cost
- budget status
- warnings
- edit/apply controls

## UI-10 Scheduling

Reminder list:
- time
- task title
- linked trip/place
- active state

Create flow:
- what
- when
- repeat
- location/trip link
- confirmation

## UI-11 Safety

Show:
- sharing status
- location quality
- trusted contacts
- share trip
- emergency actions

## UI-12 Profile / Settings

Sections:
- account
- saved places
- trips
- notifications
- location permissions
- privacy
- appearance

## Common states

Every screen includes defined Loading, Empty, Error, Offline and Permission states where relevant.
