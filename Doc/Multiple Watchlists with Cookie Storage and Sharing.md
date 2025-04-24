# Multiple Watchlists with Cookie Storage and Sharing

This update adds the ability for users to create and manage multiple watchlists, which are stored as cookies in the browser. Users can also share their watchlists with others.

## New Features

### Multiple Watchlists
- Create, rename, and delete watchlists
- Switch between watchlists via a dropdown menu
- Each watchlist can have its own set of stocks
- Add stocks from individual analysis to any watchlist

### Persistent Storage
- Watchlists are stored as cookies in the browser
- Watchlists persist between sessions and page refreshes
- No server-side storage required, making it more portable
- Automatic import of legacy watchlists from previous version

### Watchlist Sharing
- Generate shareable links for watchlists
- Export watchlists as JSON
- Import watchlists from links or JSON data
- Automatic detection and import of shared watchlists from URL parameters

## How It Works

### Cookie-Based Storage
The application uses a custom cookie management system that:
1. Encodes watchlist data as base64 for storage in the browser
2. Automatically loads saved watchlists when the app starts
3. Saves changes to watchlists in real-time

### Sharing Mechanism
1. When a user shares a watchlist, the data is encoded and converted to a URL parameter
2. The recipient can open the link, and the app automatically imports the shared watchlist
3. Alternatively, users can copy/paste JSON data for more direct sharing

### Implementation Details
- `MultiWatchlistManager` class replaces the original `WatchlistManager`
- `CookieManager` handles browser cookie storage
- Data structure includes multiple watchlists with IDs, names, and stock lists
- Backward compatibility with existing watchlist.json

## How to Use

### Managing Watchlists
1. **Select a watchlist** from the dropdown at the top of the watchlist panel
2. **Create a new watchlist** by clicking the "+ Ny" button
3. **Rename or delete** a watchlist using the "Hantera watchlist" expander
4. **Add stocks** to the current watchlist just like before

### Sharing Watchlists
1. Open the "Dela watchlist" section
2. Choose between:
   - **Sharing link**: Copy the URL parameter to share via messaging apps
   - **JSON Export**: Copy the JSON data for more technical users
3. Share the copied data with other users

### Importing Watchlists
1. Open the "Importera watchlist" section
2. Choose between:
   - **From link**: Paste a sharing link
   - **From JSON**: Paste JSON data
3. Click "Importera" to add the watchlist to your collection

### Adding Stocks from Analysis
When analyzing an individual stock, you can now choose which watchlist to add it to using the radio buttons under "Lägg till i watchlist".

## Technical Notes

- No external dependencies are required for cookie storage
- The system handles JSON serialization and base64 encoding automatically
- Shared watchlists include metadata like export date
- The UI is responsive and provides clear feedback for all operations
