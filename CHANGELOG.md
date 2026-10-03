# Changelog

Everything that changed for players and server owners across the CoA server, bots, Content Scaling, the Manager and the renderer, newest first.
Written from the `changelog.d/` fragments of each repository (see `changelog/GUIDE.md`).

## 2026-10-03-manager-0.6.0 - Manager 0.6.0

### For players

**Manager**

- Fixed: The game client follows the realm selected in the Manager. Switching realms updates the closed client's saved realm automatically. Play checks it again before launch, preventing login attempts to the previous realm. If the client is running, the update waits until the next launch.

### For server owners

**Manager**

- Added: Experimental Linux startup and Docker server controls. The Manager can start on Linux and control manually prepared Docker servers. One-click installation, updates, backups and Wine or Proton client launch are not available yet.
- Added: Simplified Chinese is available in the Manager. The interface and server and bot settings are now available in Simplified Chinese. Choose Simplified Chinese in the language selector.
- Fixed: Configuration snapshots no longer overwrite each other. Snapshots created close together keep separate copies, so restoring a configuration reliably restores the selected snapshot.
- Fixed: Problem reports open in the default browser. GitHub reports open in the default browser instead of Windows Explorer. Long reports use the clipboard fallback.

## 2026-10-03-2 - Manager 0.5.0

### For players

**Bot UI addon**

- Fixed: Stock tab shows each item's limit. A gold limit line appears under the item and updates as soon as you set it.

### For server owners

**Server**

- Fixed: A missing config option is reported once, not on every world tick. Servers lacking some module config files logged two lines per tick and filled the logs.

**Manager**

- Added: Switch between CoA and Wildcard while keeping separate characters and module settings. Run one world at a time with shared accounts. Wildcard keeps its own progress; CoA companions are unavailable there, and other modules show experimental compatibility. Backups and server updates cover both realms.
- Changed: Updating the game client shows a progress bar on its button. No window covers the app while the client updates.
- Fixed: Imported servers get the module config files they lack. They are created at start and after an update; existing files are never changed.
- Fixed: Modules marked Soon stay greyed out
- Fixed: The Bots page is hidden when the module is not on the server

## 2026-10-03 - Server 0.261002.13

### For players

**Content Scaling**

- Added: Dungeons and raids scale to your group size, with solo modes. Content Scaling is on by default. Switch it off on the Manager's Modules page to keep stock difficulty.
- Added: TBC and WotLK content packs. Outland and Northrend dungeons and raids, scaled to your level range.

### For server owners

**Content Scaling**

- Fixed: Boss health scaling reads the real raid difficulty table. Fixes a start-up stop on servers built from the shipped SQL.

**Server modules**

- Known issue: NPC Enchanter may say an empty line on servers without its config file. Copy npc_enchanter.conf.dist to npc_enchanter.conf, or let the Manager create it.

## 2026-10-02 - Server 0.261002.12 · Manager 0.4.0 · Addon 2.1.1

### For players

**Server**

- Changed: Bots no longer take Realm First achievements. Set Achievement.RealmFirstBlockBots = 0 to allow it again.

**Companion bots**

- Added: Starter pack bots get 22-slot bags
- Added: Trade with your bots. Open a trade window and hand a bot items directly, no more mailing them.
- Changed: Dungeon fill picks bots by role more reliably

**Server modules**

- Added: NPC Enchanter in Orgrimmar and Stormwind. Beauregard Boneglitter stands next to the War Games organizer.

**Bot UI addon**

- Added: Browse tab lists every online bot. Filter by role, class, level, guildmates or name and invite to your group or guild. It replaces the /who workaround, which stays capped at 49 names.
- Added: Collect gold and Stock tabs for the bot economy
- Added: Invite one bot by role. Choose tank, healer or damage and a free bot of your faction joins your group.

### For server owners

**Companion bots**

- Added: Bot economy, experimental and off by default. Gold orders, stock limits, selling surplus on the auction house, a guild share and level-appropriate food. Enable with CoaBots.Economy.Enable = 1; it starts in dry-run mode.
- Added: Master switch for the companion bots. CoaBots.Enable = 0 stops all bot spawning. The Manager's Modules page switches it.
- Fixed: A huge .botcmd spawnrandom no longer floods the server. The count is clamped and bots spawn in small batches.

**Server modules**

- Added: Auction House Bot is built in but inactive until configured
- Added: Optional fee for the NPC Enchanter. Set Enchanter.CostCopper in copper; 0 keeps the enchantments free.

**Manager**

- Added: Collections tab with transmog, vanity, riding and companion switches
- Added: Delete an account from the Players page. You type the account name to confirm; online and system accounts are refused.
- Added: Modules page with cards, status badges and per-module settings. Switch the companion bots and NPC Enchanter on and off; a module's settings open under its card.
- Changed: Importing a server suggests the right folder when you pick the wrong one
- Changed: Report a problem collects more and ignores repeated config warnings
- Changed: Server settings in one panel with search, tabs and a single Save bar
- Fixed: Companion bots are recognised from their default config file
- Fixed: The update check says you are up to date instead of offering the same version
