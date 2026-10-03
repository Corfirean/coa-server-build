# Changelog

Everything that changed for players and server owners across the CoA server, bots, Content Scaling, the Manager and the renderer, newest first.
Written from the `changelog.d/` fragments of each repository (see `changelog/GUIDE.md`).

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
