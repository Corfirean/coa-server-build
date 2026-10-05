# Changelog

Everything that changed for players and server owners across the CoA server, bots, Content Scaling, the Manager and the renderer, newest first.
Written from the `changelog.d/` fragments of each repository (see `changelog/GUIDE.md`).

## 2026-10-05-pending-features - Server 0.261005.22 · Manager 0.6.4

### For players

**Companion bots**

- Fixed: Forming a party with real players no longer crashes the server when CoABotUI is enabled. Invalid or stale bot requests are safely rejected, including when bots are disabled.

**Content Scaling**

- Added: Small groups can enter Dungeon Finder without waiting for five players. With group scaling enabled, parties of one to five players can enter together. Server owners can retain standard matchmaking through configuration.

**Manager**

- Added: Download and update the game client without installing a server. Choose to host a server or connect to someone else's. Players joining a friend can download, update and launch the client, save the host's address and use the Manager without installing a local server.
- Added: Start your installed server or client without downloading an available update. Choose to update later and keep playing with your installed version. Interrupted server updates still require recovery before startup.

### For server owners

**Server**

- Fixed: Server updates no longer fail to start with the bundled Python runtime. The launcher and its supervisor can load their integration scripts with the repack's isolated Python runtime. This fixes startup failures after an update.
- Fixed: Server releases reject versions older than the current stable package. Release builds check the stable package version before publishing and require a Manager with the database update safeguards. Manual releases can specify an explicit version when the build date differs from the release date.

**Companion bots**

- Changed: Grouped bots leave corpse loot to players by default. Bots in parties and raids no longer automatically open corpses or take items and money. Server owners can enable the previous behavior in configuration. Solo looting and Need/Greed rolls are unchanged.

**Content Scaling**

- Added: Adjust dungeon and raid enemy damage from 25% to 200%. Choose an enemy damage multiplier on top of group scaling and solo assistance. The default preserves the existing balance. Reload the configuration to apply it without restarting.
- Added: Open-world life steal can be enabled with a configurable healing percentage. Enable passive healing from damage dealt to open-world creatures and choose a percentage from 0 to 100. Players, pets and instances are excluded.

**Server modules**

- Added: Auction bot filters listings using CoA item sources. Auction listings use loot, vendor and profession items by default. A master switch and smaller default auction targets make setup easier.

**Manager**

- Added: Configure partial dungeon parties and open-world life steal in module settings. Choose whether Dungeon Finder enters with the current party and enable open-world life steal with a healing percentage from 0 to 100. Available on server builds that support these options.
- Fixed: Finish a server update that was blocked by a startup failure. The Manager repairs the launcher import path and lets you retry startup for an already applied update. Successful validation finishes the update without replaying SQL or restoring old databases. Failure details are preserved and rollback remains available.

## 2026-10-05-database-fix - Server 0.261005.0 · Manager 0.6.2

### For server owners

**Server**

- Fixed: Updates restore missing Wildcard character tables without resetting existing data. A new corrective update creates only missing Wildcard card and specialization-cache tables. Existing tables and their data are preserved. Release builds now apply SQL on a disposable database before publishing its expected schema.

**Manager**

- Added: Choose which item types the auction bot sells. Switch 15 item categories on or off and adjust listing frequency by quality. Labels and descriptions are translated into all six languages. Changes affect new listings; existing auctions remain.
- Added: Configure SQUID Playerbots and prevent conflicting bot systems. The Bots tab shows translated settings for the active bot system. Bot module cards keep enable switches without duplicate settings. Enable one bot system at a time; the Manager checks manual config changes before starting the server. Recovery points also include the SQUID database when installed.
- Changed: Module settings now offer translated controls and an enemy damage slider. Configure scaling, auctions and enchantments with translated controls. Module switches no longer appear twice. Modules without settings hide their settings button; short lists need no search. New server builds support dungeon and raid damage from 25% to 200%.
- Fixed: Failed server updates restore databases and files together. Updates save a full backup and recover databases and files together. Interrupted SQL is not replayed. Checks cover Wildcard tables and every supported race/class pair, including existing characters. Unfinished updates block startup until recovered.
- Fixed: Server packages must include a complete database schema check. Release tools generate the expected database structure on an isolated copy of the signed base, verify all archive files and refuse packages without the schema check. Corrective SQL can restore missing Wildcard tables without replaying old updates.

## 2026-10-04-manager-0.6.1 - Manager 0.6.1

### For server owners

**Server**

- Fixed: Open remote-console connections no longer prevent server shutdown. The shutdown fix is merged in the server source. A server package containing it is required; updating the Manager alone does not update the server binaries.

**Manager**

- Added: Check database structure and repair server files with a safety backup. Settings can check both realm databases and restore official files plus pending SQL. Installation and updates check character-save columns. Clean packages no longer keep old character migration records when rebuilding their database.
- Added: Start CoA and Wildcard together from Settings. Both worlds can run on separate ports with their own characters, settings and logs, sharing accounts. Stop saves both worlds before shutting down the shared database.
- Fixed: Server multipliers now accept decimals typed with a dot or comma. Talent settings now explain that the multiplier does not affect CoA talents. The rested experience setting now correctly describes bonus accumulation.
- Fixed: Play launches only the game client without starting your local server. Use the left button to start the server and PLAY to launch the client with your selected realmlist, including connections to other servers.

## 2026-10-03-server17 - Server 0.261003.17

### For players

**Server**

- Changed: Companions follow safer navigation paths. Companion movement uses validated paths and geometry checks, reducing unsafe movement and keeping recovery behavior consistent when a route fails.
- Fixed: Dungeon Finder respects scaled realm levels across enabled expansions. Dungeon access checks use the realm progression ranges, and Dungeon Finder defaults to the server expansion. Enabled Classic, Burning Crusade and Wrath content remains visible at a reduced level cap.

**Companion bots**

- Changed: Companions follow and recover movement more consistently. Updated movement handling coordinates following, mounting and route recovery so interrupted actions do not take over a newer movement request.
- Fixed: Companions fly from the opening of Burning Crusade content. Companions can mount for flight from the realm’s Burning Crusade unlock level instead of a fixed level 60, and switch from ground mounts when the leader flies.
- Fixed: Companions avoid helmets and shoulders with missing models. Equipment repair rejects display models missing from the audited client, preventing broken helmet and shoulder visuals.
- Fixed: Companion equipment repair continues with full bags. When a companion has full bags, equipment replaced by the gear filter is preserved in its mailbox. The gradual repair queue no longer stalls because old items cannot fit in the inventory.

**Content Scaling**

- Fixed: All dungeon difficulties and combat gear variants follow realm progression. Classic, BC and Wrath normal, heroic and mythic queues support bot-fill or current-party entry. Reference loot and combat gear variants, including Bloodforged, scale requirements and stats while retaining difficulty progression. Forge of Souls quests use their actual expansion.
- Fixed: Custom progression at level 80 now scales item requirements and rewards consistently. Custom era boundaries now apply to item budgets, quest XP, dungeon access and group finder rewards even when the maximum player level is 80.
- Fixed: Downscaled dungeon creatures keep their loot rewards. The damage needed to earn loot now follows a creature's scaled health, including encounter health changes. Player participation is still required.
- Fixed: Dungeon Finder shows all enabled expansions at a reduced level cap. Updated client addon support displays the server's effective dungeon level ranges. Earlier expansions stay available through the level cap; quest and equipment requirements still apply.
- Fixed: Items now scale correctly on servers with a reduced level cap. Equipment stats, item levels and required levels are adjusted after item data loads. Dungeon item-level requirements follow the same scaling.
- Fixed: Scaled encounters retain normal boss loot. Dungeon and raid encounters preserve their normal loot when scaled for smaller groups. Equipment is no longer randomly discarded in favor of currency.

### For server owners

**Server**

- Fixed: Remote console shutdown no longer blocks server management. Graceful shutdown through the remote console releases pending console requests so the manager can stop the worldserver and switch realms reliably.

**Companion bots**

- Fixed: Bots get level-appropriate gear without holiday, event or vanity items. Equipment checks required level, item level and PvE/PvP Power. Use .fixbotgear to repair existing bots gradually. Suitable gear stays; replaced items remain in bags or are mailed when bags are full. The repair queue survives server restarts.
- Fixed: Existing bots follow a lowered server level cap. Bots above the cap are lowered when they log in. Online bots are handled gradually outside combat, with experience reset and replacement gear queued.

**Content Scaling**

- Fixed: Destroyed instances release their saved scaling state. Encounter snapshots and group scaling settings are cleared when a map is destroyed, preventing stale state from reaching a later instance that reuses its ID.
- Fixed: Invalid progression settings stop scaling before items are changed. If the progression layout fails validation, scaling initialization stops before item templates are modified or combat hooks are enabled.
- Fixed: Disabling Content Scaling now stops item and group finder changes. After restarting the worldserver, disabled scaling preserves original items and group finder rules. Creature and quest levels, combat, rewards and encounter mechanics also retain their original behavior.
- Fixed: Explicit scaling overrides now take priority over generated content profiles. Map overrides apply to creatures on every map, area overrides take priority for quests, and item era overrides retain each item's safety protections.

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
