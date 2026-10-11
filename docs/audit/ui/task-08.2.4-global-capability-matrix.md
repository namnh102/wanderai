# GoMate Global Capability Matrix: TASK 08.2.4
## Comprehensive 14-Module Capability Audit & Two-Tier Classification

- **Document Reference:** `docs/audit/ui/task-08.2.4-global-capability-matrix.md`
- **Scope:** Complete Capability Audit of all 14 Modules in GoMate
- **Status:** **CAPABILITY AUDIT LOCKED**
- **Date:** October 7, 2026
- **Vocabulary:** `CURRENT` | `PARTIAL` | `MISSING` | `PRODUCT TARGET` | `FUTURE` | `EXCLUDED`

---

## 1. Executive Summary & Vocabulary Governance

This matrix serves as the unified capability registry across the entire GoMate application. It establishes strict truthfulness by separating what is verified to run in the current repository code from the required production targets.

### Six-State Vocabulary Definitions
- **`CURRENT`:** Đã được xác minh có runtime code hoạt động trong repository.
- **`PARTIAL`:** Đã tồn tại một phần nhưng chưa hoàn chỉnh end-to-end.
- **`MISSING`:** Chưa có implementation trong current runtime.
- **`PRODUCT TARGET`:** Bắt buộc phải triển khai trước production-ready release.
- **`FUTURE`:** Để sau MVP / post-launch.
- **`EXCLUDED`:** Cố ý không nằm trong phạm vi sản phẩm hiện tại.

### Module-Level Status Disclaimer & Authority Hierarchy
> [!IMPORTANT]
> **Authoritative Implementation Source:**
> Module-level summaries (such as "RUNTIME BASELINE EXISTS") only indicate that an initial code foundation exists in the repository. They must NEVER be interpreted as implying that all capabilities within that module are complete.
> This **Capability-Level Matrix is the sole authoritative implementation source of truth**. Every feature work package in the Master Implementation Roadmap (`TASK 08.3`) must be derived from capability-level rows, not module summary labels.

### Master Roadmap Source-of-Truth Hierarchy (Invariant for TASK 08.3)
When planning and implementing tasks in `TASK 08.3`, all work items must strictly follow this authority priority:
$$\text{Repository Evidence} > \text{Capability Matrix (Capability Level)} > \text{Dependency Register} > \text{Module Summary Prose}$$

1. **Repository Evidence (Supreme Truth):** Code running in `apps/backend/` and `apps/mobile/` takes precedence over any documentation claim.
2. **Capability-Level Matrix:** Authoritative registry of functional and architectural scope per capability ID.
3. **Dependency Register (14 Subsystems):** Authoritative registry of system preconditions, schema models, and service interfaces.
4. **Module Summary Prose:** Informational overview only; carries zero implementation authority.

---

## 2. Global Module Capability Matrix

### Module 1: Home / Discover (`/home`)
| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Reality & Target Requirement |
| :-: | :--- | :---: | :---: | :--- |
| 1.1 | Destination Cards Carousel | **CURRENT** | **CURRENT** | Verified in Flutter; reads `destinations.json` via backend API. |
| 1.2 | Personalized Greeting | **CURRENT** | **CURRENT** | Renders "Xin chào bạn 👋" or user name if authenticated. |
| 1.3 | Wandy AI Copilot Entry Card | **CURRENT** | **CURRENT** | Prominent card navigating to `/wandy` with suggestion prompt. |
| 1.4 | Search Bar Entry | **PARTIAL** | **PRODUCT TARGET** | Basic search exists; needs cross-destination global search query. |
| 1.5 | Personalized Recommendations | **MISSING** | **FUTURE** | Machine-learning personalized ranking deferred post-launch. |

### Module 2: Map & Nearby Places (`/map`)
| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Reality & Target Requirement |
| :-: | :--- | :---: | :---: | :--- |
| 2.1 | OpenStreetMap Basemap Tiles | **CURRENT** | **CURRENT** | Verified; Humanitarian OSM tiles rendered without API watermarks. |
| 2.2 | Category Filtering Chips | **CURRENT** | **CURRENT** | 8 categories (Tham quan, Nhà hàng, Khách sạn, Văn hóa, Biển, v.v.). |
| 2.3 | Place Markers & Cluster | **CURRENT** | **CURRENT** | Color-coded POI markers rendered at exact PostGIS coordinates. |
| 2.4 | Bottom Place Preview Sheet | **CURRENT** | **CURRENT** | Slides up on marker tap; shows honest rating and distance. |
| 2.5 | Foreground Geolocation Button | **CURRENT** | **CURRENT** | On-demand GPS fix with visual blue dot and accuracy pill. |
| 2.6 | Distance Calculation | **CURRENT** | **CURRENT** | Client-side Haversine formula based on active GPS fix. |
| 2.7 | Offline Basemap Caching | **MISSING** | **PRODUCT TARGET** | Pre-caching tile packages for offline travel situations. |
| 2.8 | Realtime GPS Navigation Track | **MISSING** | **EXCLUDED** | Turn-by-turn navigation is delegated to Google Maps / Apple Maps. |

### Module 3: Place Detail (`/places/:id`)
| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Reality & Target Requirement |
| :-: | :--- | :---: | :---: | :--- |
| 3.1 | Place Detail Header & Layout | **CURRENT** | **CURRENT** | Verified in Flutter UI; displays place name, category, verified badge, and fallback hero image. |
| 3.2 | Honest Rating Line | **CURRENT** | **CURRENT** | Displays "Chưa có đánh giá" when ratings are absent in DB. |
| 3.3 | Address Information Section | **CURRENT** | **CURRENT** | Honest address row or "Chưa có thông tin địa chỉ." fallback. |
| 3.4 | Opening Hours Section | **CURRENT** | **CURRENT** | Structured opening hours or "Chưa có thông tin giờ mở cửa." |
| 3.5 | Contact Information | **CURRENT** | **CURRENT** | Website and phone displayed only if present; hidden otherwise. |
| 3.6 | Mini Map & Coordinates | **CURRENT** | **CURRENT** | Embedded static mini-map centered at place coordinates. |
| 3.7 | Source Provenance Attribution| **CURRENT** | **CURRENT** | Clickable link to OpenStreetMap source entry. |
| 3.8 | Directions Intent Button | **CURRENT** | **CURRENT** | Dispatches external Google Maps navigation URL with destination. |
| 3.9 | User Reviews & Photo Upload | **MISSING** | **FUTURE** | Community photo/review submission pipeline deferred post-launch. |
| 3.10| Production Place Media Pipeline | **PARTIAL** | **PRODUCT TARGET** | Dynamic image ingestion, license provenance, thumbnail generation, CDN storage; partial placeholder in client. |

### Module 4: Wandy AI Copilot (`/wandy`)
| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Reality & Target Requirement |
| :-: | :--- | :---: | :---: | :--- |
| 4.1 | Conversational Travel Advice | **CURRENT** | **CURRENT** | Gemini 2.5 streaming chat via NestJS backend. |
| 4.2 | Grounded Place Citations | **CURRENT** | **CURRENT** | pgvector RAG retrieves real places; renders source chips. |
| 4.3 | Suggested Prompt Starters | **CURRENT** | **CURRENT** | Quick prompt chips on empty state. |
| 4.4 | Action Preview & Confirmation| **MISSING** | **PRODUCT TARGET** | Guarded execution pattern for side-effect operations. |
| 4.5 | Voice Input & Speech Output | **MISSING** | **FUTURE** | Speech-to-text / Text-to-speech integration deferred. |
| 4.6 | Autonomous Tool Execution | **MISSING** | **EXCLUDED** | Autonomous booking/mutations without user consent prohibited. |

### Module 5: Trip Management (`/trips`)
| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Reality & Target Requirement |
| :-: | :--- | :---: | :---: | :--- |
| 5.1 | Trip Listing & Creation | **CURRENT** | **CURRENT** | PostgreSQL `Trip` CRUD via NestJS endpoints. |
| 5.2 | Multi-Day Itinerary Structure| **CURRENT** | **CURRENT** | Day-by-day item timeline with time slots and POIs. |
| 5.3 | Budget Tracking & Cost Calc | **CURRENT** | **CURRENT** | Calculates total budget vs estimated expense variance. |
| 5.4 | Drag-and-Drop Item Reordering| **PARTIAL** | **PRODUCT TARGET** | UI exists; needs persistent drag-and-drop index ordering. |
| 5.5 | Trip Archiving & PDF Export | **MISSING** | **FUTURE** | Offline PDF itinerary export deferred post-launch. |

### Module 6: AI Itinerary Planner (`/trips/:id/plan`)
| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Reality & Target Requirement |
| :-: | :--- | :---: | :---: | :--- |
| 6.1 | One-Tap AI Plan Generation | **CURRENT** | **CURRENT** | Real Gemini LLM plans full multi-day itinerary in ~30s. |
| 6.2 | Itinerary Preview Sheet | **CURRENT** | **CURRENT** | Structured bottom sheet reviewing days, items, and cost. |
| 6.3 | Overwrite Confirmation Dialog | **CURRENT** | **CURRENT** | Safeguard modal before overwriting existing draft items. |
| 6.4 | Budget Constraint Adaptation | **CURRENT** | **CURRENT** | Flags over-budget scenarios and balances POI admissions. |
| 6.5 | Multi-City Route Optimization | **MISSING** | **FUTURE** | Complex multi-destination TSP routing deferred. |

### Module 7: Buddy Matching (`/buddies`)
| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Reality & Target Requirement |
| :-: | :--- | :---: | :---: | :--- |
| 7.1 | Traveler Discovery Grid | **MISSING** | **PRODUCT TARGET** | Grid showing compatible travelers by destination & dates. |
| 7.2 | Travel Style Matching Score | **MISSING** | **PRODUCT TARGET** | Vector compatibility algorithm matching preferences. |
| 7.3 | Masked Traveler Profile View | **MISSING** | **PRODUCT TARGET** | Public traveler profile with masked phone and private data. |
| 7.4 | Double Opt-In Match Handshake | **MISSING** | **PRODUCT TARGET** | Request $\rightarrow$ Notification $\rightarrow$ Mutual Acceptance. |
| 7.5 | Realtime Geolocation Proximity| **MISSING** | **EXCLUDED** | Live location radar tracking prohibited for privacy/safety. |

### Module 8: Group & Group Chat (`/groups/:id`)
| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Reality & Target Requirement |
| :-: | :--- | :---: | :---: | :--- |
| 8.1 | Group Space Creation | **MISSING** | **PRODUCT TARGET** | Created from mutual buddy matches or trip invite codes. |
| 8.2 | Membership Roles (Leader/Mem) | **MISSING** | **PRODUCT TARGET** | Role-based permissions for itinerary and expense controls. |
| 8.3 | Real-Time Group Chat Timeline | **MISSING** | **PRODUCT TARGET** | WebSocket messaging with sender identity and timestamps. |
| 8.4 | Phantom Online Presence | **MISSING** | **EXCLUDED** | Fabricated "Đang hoạt động" labels strictly prohibited. |
| 8.5 | Media & Voice Message Sharing | **MISSING** | **FUTURE** | Audio clips and photo sharing inside chat deferred. |

### Module 9: Shared Itinerary (`/groups/:id/itinerary`)
| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Reality & Target Requirement |
| :-: | :--- | :---: | :---: | :--- |
| 9.1 | Collaborative Itinerary Board | **MISSING** | **PRODUCT TARGET** | Multi-user view of group itinerary activities. |
| 9.2 | Activity Proposal & Voting | **MISSING** | **PRODUCT TARGET** | Members vote (thumbs up/down) on proposed POIs. |
| 9.3 | Realtime Conflict Resolution | **MISSING** | **PRODUCT TARGET** | Last-write-wins or leader lock to avoid race edits. |

### Module 10: Shared Expense (`/groups/:id/expenses`)
| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Reality & Target Requirement |
| :-: | :--- | :---: | :---: | :--- |
| 10.1| Group Expense Ledger | **MISSING** | **PRODUCT TARGET** | Record shared bills (payer, amount, category, date). |
| 10.2| Split Logic (Equal / Custom) | **MISSING** | **PRODUCT TARGET** | Automatic split calculation across selected group members. |
| 10.3| Debt Simplification Matrix | **MISSING** | **PRODUCT TARGET** | Minimizes total settlement transactions between peers. |
| 10.4| Peer Settlement Recording | **MISSING** | **PRODUCT TARGET** | Mark debt as settled with date and optional note. |
| 10.5| In-App Payment Gateway | **MISSING** | **EXCLUDED** | GoMate does NOT process banking or monetary transactions. |

### Module 11: Scheduling & Reminders
| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Reality & Target Requirement |
| :-: | :--- | :---: | :---: | :--- |
| 11.1| Itinerary Item Reminder Alert| **MISSING** | **PRODUCT TARGET** | Local notification for upcoming tour/flight events. |
| 11.2| Lead-Time Offset Selector | **MISSING** | **PRODUCT TARGET** | User chooses 15m, 1h, or 1d prior to activity start. |
| 11.3| Packing Checklist Reminder | **MISSING** | **PRODUCT TARGET** | Pre-departure checklist reminder trigger. |
| 11.4| Calendar Sync (Google/iCal) | **MISSING** | **FUTURE** | External calendar sync export deferred post-launch. |

### Module 12: Safety & Emergency (`/safety`)
| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Reality & Target Requirement |
| :-: | :--- | :---: | :---: | :--- |
| 12.1| National Hotlines Directory | **CURRENT** | **CURRENT** | 112 (Disaster/Rescue), 113 (Police), 114 (Fire), 115 (Medical). |
| 12.2| Legal Basis Citations | **CURRENT** | **CURRENT** | NĐ 200/2025/NĐ-CP & QĐ 2023/2024 cited for 112 authority. |
| 12.3| Da Nang Visitor Support *8899| **CURRENT** | **CURRENT** | Official hotline *8899 with address 18 Hùng Vương. |
| 12.4| Emergency Confirmation Modal | **PARTIAL** | **PRODUCT TARGET** | Mandatory confirmation before opening native dialer. |
| 12.5| Native Dialer Dispatch (`tel:`) | **CURRENT** | **CURRENT** | Launches phone dialer with emergency number pre-filled. |
| 12.6| Autonomous Emergency Calling | **MISSING** | **EXCLUDED** | Autonomous phone dialing strictly forbidden. |
| 12.7| Offline Emergency Cache | **MISSING** | **PRODUCT TARGET** | Hardcoded asset storage guaranteeing access without internet. |

### Module 13: Profile & Settings (`/profile`)
| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Reality & Target Requirement |
| :-: | :--- | :---: | :---: | :--- |
| 13.1| Public Traveler Identity | **CURRENT** | **CURRENT** | View avatar, name, bio, and verification status. |
| 13.2| Responsive Edit Profile Form | **CURRENT** | **CURRENT** | Clean 390px mobile layout; zero horizontal overflow. |
| 13.3| Travel Preferences Viewing | **CURRENT** | **CURRENT** | Reads `TravelPreference` from Prisma database. |
| 13.4| Travel Preferences Editing | **MISSING** | **PRODUCT TARGET** | Requires backend `PUT /users/me/preferences` endpoint. |
| 13.5| Privacy & Visibility Controls| **MISSING** | **PRODUCT TARGET** | Opt-out of buddy discovery and profile searchability. |
| 13.6| Presence Status Indicator | **MISSING** | **EXCLUDED** | Fake "Đang hoạt động" labels completely removed. |

### Module 14: Authentication & Session Lifecycle (`/login`, `/register`)
| # | Capability Dimension | Tier 1 (Current Runtime) | Tier 2 (Product Target) | Technical Reality & Target Requirement |
| :-: | :--- | :---: | :---: | :--- |
| 14.1| Email/Password Registration | **CURRENT** | **CURRENT** | Verified; bcrypt hashing in PostgreSQL `User`. |
| 14.2| Email/Password Login | **CURRENT** | **CURRENT** | Verified; issues 15m access token & 7d refresh token. |
| 14.3| Secure Token Storage (Mobile)| **PARTIAL** | **PRODUCT TARGET** | Migrate from SharedPreferences to `flutter_secure_storage`. |
| 14.4| Silent Refresh & Queue Lock | **PARTIAL** | **PRODUCT TARGET** | Dio 401 retry interceptor with concurrency queue lock. |
| 14.5| Anti-Enumeration Password Recov| **MISSING** | **PRODUCT TARGET** | Generic 200 response + 15m one-time reset token. |
| 14.6| Authenticated Password Change | **MISSING** | **PRODUCT TARGET** | Settings endpoint with canonical complexity validation. |
| 14.7| Email Verification Pipeline | **MISSING** | **PRODUCT TARGET** | Transactional email verification link + unverified banner. |
| 14.8| Google Social OAuth | **MISSING** | **PRODUCT TARGET** | Google Sign-In SDK + `POST /auth/oauth/google`. |
| 14.9| Apple Social OAuth | **MISSING** | **PRODUCT TARGET** | Sign in with Apple SDK + `POST /auth/oauth/apple`. |
| 14.10| Account Linking & Collision | **MISSING** | **PRODUCT TARGET** | Prevents duplicate user; prompts pass via `/auth/link-account`. |
| 14.11| Rate Limiting & Throttling | **MISSING** | **PRODUCT TARGET** | `@nestjs/throttler` on login and recovery endpoints. |
| 14.12| Facebook Social Login | **MISSING** | **EXCLUDED** | Deprioritized for GoMate travel MVP. |
| 14.13| Guest / Anonymous Browse | **MISSING** | **EXCLUDED** | Mandatory authenticated traveler profile. |
| 14.14| Remember Me Checkbox | **MISSING** | **EXCLUDED** | Continuous session via hardware secure storage. |
| 14.15| Server Token Blacklist | **MISSING** | **FUTURE** | Stateless JWT preserved; Redis blacklist deferred. |
| 14.16| Biometric Login (`local_auth`)| **MISSING** | **FUTURE** | Hardware biometric unlock deferred post-MVP. |

---

## 3. Summary Statistics

```
Total Audited Capabilities Across 14 Modules: 90 Dimensions (85 Baseline + Subsystem Expansion)

┌─────────────────────────────────────────────────────────────┐
│               TIER 1: CURRENT RUNTIME BREAKDOWN             │
├───────────────────────────────────┬──────────────┬──────────┤
│ Status                            │ Count        │ Percent  │
├───────────────────────────────────┼──────────────┼──────────┤
│ CURRENT (Operational Code)        │ 36           │ 40.0%    │
│ PARTIAL (Incomplete / Fragmented) │ 6            │ 6.7%     │
│ MISSING (Zero Runtime Code)       │ 48           │ 53.3%    │
├───────────────────────────────────┼──────────────┼──────────┤
│ TOTAL AUDITED DIMENSIONS          │ 90           │ 100.0%   │
└───────────────────────────────────┴──────────────┴──────────┘

┌─────────────────────────────────────────────────────────────┐
│               TIER 2: ARCHITECTURAL TARGET BREAKDOWN        │
├───────────────────────────────────┬──────────────┬──────────┤
│ Status                            │ Count        │ Percent  │
├───────────────────────────────────┼──────────────┼──────────┤
│ CURRENT (Retained in Target)      │ 36           │ 40.0%    │
│ PRODUCT TARGET (Mandatory Launch) │ 35           │ 38.9%    │
│ FUTURE (Post-MVP Deferred)        │ 9            │ 10.0%    │
│ EXCLUDED (Intentionally Omitted)  │ 10           │ 11.1%    │
├───────────────────────────────────┼──────────────┼──────────┤
│ TOTAL AUDITED DIMENSIONS          │ 90           │ 100.0%   │
└───────────────────────────────────┴──────────────┴──────────┘
```

### Reconciliation Note: 85 Canonical Baseline vs. 90 Audited Line Items
- **85 Core Baseline:** The canonical feature set prior to Module 14 scope delineation (14.13–14.16) and Place Media separation (3.10).
- **90 Audited Line Items:** Reflects the complete, granular capability registry including:
  1. Separation of **Place Media Pipeline** (`3.10`: `PARTIAL` $\rightarrow$ `PRODUCT TARGET`) from **Place Detail Header Layout** (`3.1`: `CURRENT`).
  2. Granular tracking of Module 14 Auth boundary capabilities (`14.13` Guest, `14.14` Remember Me, `14.15` Server Blacklist, `14.16` Biometric Login).
- **Zero Inconsistency:** Every single row in the matrix is verified and accounted for without artificial fabrication or rounding.

**Verdict:** The GoMate architecture exhibits **100% classification clarity**. Every capability is mapped to an unambiguous status with zero contradictions between current runtime reality and design target specifications.
