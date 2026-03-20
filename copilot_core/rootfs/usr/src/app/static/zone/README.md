# Zone Editor Component

Lit-based zone management interface for PilotSuite with full CRUD operations, drag & drop entity management, and real-time validation.

## 🎯 Features

- **Zone List Display** - View all zones with entity counts and metadata
- **Create/Edit/Delete** - Full CRUD operations for zones
- **Entity Drag & Drop** - Intuitive drag & drop interface for adding entities
- **Auto-Save** - Debounced auto-save on form changes (1 second)
- **Validation** - Real-time validation (name required, minimum 1 entity)
- **Loading States** - Skeleton loaders during API calls
- **Error Handling** - User-friendly error messages
- **Success Messages** - Auto-dismissing success notifications

## 📦 Files

```
static/zone/
├── zone_editor.ts          # Main Lit component (31KB)
├── zone_editor.styles.ts   # Component styles (12KB)
├── index.ts                # Module exports
├── demo.html               # Standalone demo page
└── README.md               # This file
```

## 🔌 API Endpoints

The component expects the following REST API endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/zone-editor/zones` | List all zones |
| `POST` | `/api/v1/zone-editor/zones` | Create new zone |
| `GET` | `/api/v1/zone-editor/zones/{id}` | Get zone details |
| `PUT` | `/api/v1/zone-editor/zones/{id}` | Update zone |
| `DELETE` | `/api/v1/zone-editor/zones/{id}` | Delete zone |
| `GET` | `/api/v1/zone-editor/rooms` | List assignable rooms |
| `POST` | `/api/v1/zone-editor/zones/{id}/rooms` | Add room to zone |

## 📝 Data Models

### Zone
```typescript
interface Zone {
  zone_id: string;
  name: string;
  floor?: number;
  area_sqm?: number;
  entities: ZoneEntity[];
  icon?: string;
  mode?: string;
  enabled?: boolean;
  priority?: number;
  status?: string;
  person_count?: number;
}
```

### ZoneEntity
```typescript
interface ZoneEntity {
  entity_id: string;
  name: string;
  domain: string;
  state?: string;
}
```

## 🚀 Usage

### Basic Usage

```html
<zone-editor></zone-editor>
```

### With Custom API URL

```html
<zone-editor api-base-url="/api/v1/zone-editor/zones"></zone-editor>
```

### With Authentication

```javascript
const editor = document.querySelector('zone-editor');
editor.authToken = 'your-bearer-token';
```

### Programmatic Usage

```javascript
import { ZoneEditor } from './static/zone/zone_editor.js';

const editor = new ZoneEditor();
editor.apiBaseUrl = '/api/v1/zone-editor/zones';
editor.authToken = 'token';
document.body.appendChild(editor);

// Load zones
await editor.loadZones();

// Create zone programmatically
editor.startCreateMode();

// Load specific zone
await editor.loadZoneDetails('zone:living_room');
```

## 🎨 Styling

The component uses Home Assistant Design System CSS variables:

- `--primary-color` - Primary action color
- `--primary-text-color` - Main text color
- `--secondary-text-color` - Secondary text color
- `--card-background-color` - Card background
- `--divider-color` - Border/divider color
- `--error-color` - Error state color
- `--success-color` - Success state color

## ✅ Validation Rules

1. **Name Required** - Zone name cannot be empty
2. **Zone ID Required** - Zone ID required for creation
3. **Minimum 1 Entity** - At least one entity must be added

## 🧪 Testing

Tests are located in: `tests/typescript/test_zone_editor.test.ts`

### Run Tests

```bash
# Install dependencies
npm install --save-dev @open-wc/testing sinon

# Run tests
npm test -- tests/typescript/test_zone_editor.test.ts
```

### Test Coverage

- ✅ Basic rendering (5 tests)
- ✅ Zone list rendering (5 tests)
- ✅ Loading states (4 tests)
- ✅ Form handling (5 tests)
- ✅ Validation (5 tests)
- ✅ Drag & drop (4 tests)
- ✅ Entity management (3 tests)
- ✅ Success/error messages (3 tests)
- ✅ Auto-save (2 tests)
- ✅ API configuration (2 tests)
- ✅ Zone detail rendering (2 tests)
- ✅ API integration (10 tests)

**Total: 50 tests**

## 🎯 User Interactions

### Creating a Zone

1. Click **"+ New Zone"** button
2. Fill in Zone ID and Name (required)
3. Optionally set Floor, Area, Icon
4. Drag entities from "Available Entities" panel
5. Click **"Create Zone"**

### Editing a Zone

1. Select a zone from the list
2. Click **"Edit"** button
3. Modify fields (auto-saves after 1 second)
4. Drag & drop entities to add/remove
5. Click **"Save Changes"** or **"Cancel"**

### Deleting a Zone

1. Select a zone from the list
2. Click **"Delete"** button
3. Confirm deletion in dialog

### Drag & Drop Entities

1. Open create/edit form
2. See "Available Entities" panel
3. Drag entity to "Entities" drop zone
4. Drop to add to zone
5. Click ✕ to remove entity

## 🔄 Auto-Save

When editing a zone, changes are automatically saved after 1 second of inactivity:

- Name changes
- Floor changes
- Area changes
- Icon changes
- Entity additions/removals

The auto-save timeout is cleared on each new change to prevent excessive API calls.

## ⚠️ Error Handling

The component handles errors gracefully:

- **Network errors** - Shows user-friendly error message
- **Validation errors** - Inline error messages per field
- **API errors** - Displays error response from backend
- **Duplicate zones** - 409 Conflict handled

## 📱 Responsive Design

The component is responsive and adapts to different screen sizes:

- **Desktop** - Side-by-side layout (zone list + detail panel)
- **Mobile** - Stacked layout with collapsible sections

## 🔧 Development

### Building

```bash
# Compile TypeScript
tsc --project tsconfig.json

# Watch mode
tsc --watch
```

### Demo Page

Open `demo.html` in a browser to test the component:

```bash
# Start a local server
python -m http.server 8000

# Open in browser
http://localhost:8000/static/zone/demo.html
```

## 📚 Dependencies

- **Lit** - Web component library
- **TypeScript** - Type safety
- **Home Assistant Design System** - CSS variables

## 📄 License

Part of PilotSuite Styx Core - MIT License

---

**Author:** Clawdya  
**Version:** 1.0.0  
**Created:** 2026-03-01
