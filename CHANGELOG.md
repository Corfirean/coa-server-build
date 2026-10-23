# CoA Server changelog

Server packages, companions and server modules only. Manager releases have their own changelog.

[Manager changelog](https://github.com/Corfirean/coa-server-manager/blob/master/CHANGELOG.md)

Published releases and previews. Pre-release entries do not change the stable update channel.

Dates follow GitHub publication (UTC); legacy records retain their archived dates. Newest releases first.

## 0.261023.76 — 2026-10-23

**Portable Characters are experimental and may contain bugs.**

- Guardian Tower Formation no longer blocks shield abilities.
- The Auction House Bot has one switch.
- Content Scaling takes over dungeon and raid health and damage when it is enabled.
- Dungeon trash no longer has several health boosts stacked on top of each other.
- Updated the reviewed CoA upstream snapshot.

[Release](https://github.com/Corfirean/coa-server-build/releases/tag/server-0.261023.76) · [Source changes](https://github.com/Corfirean/coa-server-build/compare/server-0.261022.75...server-0.261023.76)

## 0.261022.75 — 2026-10-22

**Portable Characters are experimental and may contain bugs.**

- Added experimental server support for Portable Characters, used with Manager 0.7.0 on compatible realms.
- Integrated the latest reviewed CoA upstream changes.
- Updated SQUID Playerbots to 2.6.
- Improved combat and healing behavior for multiple classes and specializations.
- Bots choose equipment for the stats their specialization uses.
- Improved party following and dungeon pathfinding.
- Tanks wait for the group to catch up and recover.
- Damage dealers and healers bring attacking enemies back to the tank.
- Bots recover from dungeon deaths and stay behind when the leader is a ghost.
- Improved battleground participation and matching bots to the correct level bracket.
- Added separate creature health settings for the open world, dungeons, raids, ordinary enemies and bosses.

[Release](https://github.com/Corfirean/coa-server-build/releases/tag/server-0.261022.75) · [Source changes](https://github.com/Corfirean/coa-server-build/compare/server-0.261018.70...server-0.261022.75)

## 0.261018.70 — 2026-10-19

- Restored Manastorm Endless integration and database updates for existing servers.
- Included optional matching Manastorm client UI fixes.
- Updated the reviewed CoA upstream snapshot.
- Updated Custom Races to 1.8 and SQUID Playerbots to 2.5.

[Release](https://github.com/Corfirean/coa-server-build/releases/tag/server-0.261018.70)

## 0.261015.58 — 2026-10-15

- Added complete installation packages for the current server build.
- Servers can stop even when startup configuration templates are damaged.
- Startup configuration errors identify the affected template.
- Updated the reviewed CoA upstream snapshot.
- Updated Custom Races to 1.7 and SQUID Playerbots to 2.3.1.

[Release](https://github.com/Corfirean/coa-server-build/releases/tag/server-0.261015.58)

## 0.261013.54 — 2026-10-13

- Custom races bot support and dedicated lore naming.
- Random bot spawning and auto-fill no longer leak accounts or freeze the server.
- Bot account cleanup preserves accounts used by other realms.
- Companion race selection respects module switches and excluded races.
- Allow removing class requirements from equipment and tier sets.
- Fix LFG bot fill and party queues, battleground access, and Manastorm entry.
- Configure parallel and global level scaling progression modes.
- Private dungeon access no longer bypasses restrictions on unrelated maps.
- Content Scaling preserves your creature health settings.
- Updated the reviewed CoA upstream snapshot.
- Updated Custom Races to 1.6 and SQUID Playerbots to 2.1.

[Release](https://github.com/Corfirean/coa-server-build/releases/tag/server-0.261013.54)

## 0.261012.800008 — 2026-10-12

- Refreshed terrain, collision and navigation data, including the Cain Estate area.
- Requires Manager 0.6.15 or newer for large server updates.

[Release](https://github.com/Corfirean/coa-server-build/releases/tag/server-0.261012.800008)

## 0.261012.800007 (Pre-release) — 2026-10-11

Superseded by server-0.261012.800008: the minimum Manager metadata needs correction. The navigation payload passed all three Manager upgrade scenarios, but this release must not be installed with Managers older than 0.6.15.

- Withdrawn preview with incorrect minimum Manager version metadata.

[Release](https://github.com/Corfirean/coa-server-build/releases/tag/server-0.261012.800007)

## 0.261011.800006 — 2026-10-11

- Updated the reviewed CoA upstream snapshot.
- Updated SQUID Playerbots to 2.0 and Custom Races to 1.5.1.
- Included persistent armor hiding and relaxed name restrictions with custom races enabled.
- Updated raid boss initialization and applied targeted Retreat and Northshire database fixes.

[Release](https://github.com/Corfirean/coa-server-build/releases/tag/server-0.261011.800006)

## 0.261010.32 — 2026-10-10

- Custom races gain Jinyu, Sethrak, Gnoll and Saberon with updated appearances.
- Optional custom races support extended character appearances.
- Optional custom playable races support (mod-coa-custom-races).
- Server packages include the optional custom race module and its game data.
- The experimental Linux server build matches the Windows release contents.
- Server packages include the updated custom race game data.

[Archived release record](https://github.com/Corfirean/coa-server-build/blob/main/changelog/archive/releases/2026-10-10.json)

## 0.261008.27 — 2026-10-08

- Random dungeons pay Dungeon Spoils, and the final boss a Mark of Triumph.
- You can queue for arenas from the PvP frame.
- Class fixes for Necromancer, Venomancer, Bloodmage, Pyromancer, Tinker and Guardian.
- Quest markers and quest givers repaired in Westfall, Northshire, Mulgore and more.
- SQUID bots 1.9.1: PvP bots, rated arenas and a chat language setting.

[Archived release record](https://github.com/Corfirean/coa-server-build/blob/main/changelog/archive/releases/2026-10-08-2.json)

## 0.261007.24 — 2026-10-07

- The world server no longer crashes with many units close together.
- Experimental Linux server build.
- SquidBots builds follow the latest stable module release.
- Interrupted SquidBots database imports require recovery before restarting.
- SquidBots preserves imported bot databases and skips SQL when disabled.
- Disabled SquidBots no longer require their database to start the server.
- Large SQUID database imports no longer use the short query timeout.
- First SQUID startup has time to create its initial bot pool.
- The Auction House Bot creates its own character when enabled.

[Archived release record](https://github.com/Corfirean/coa-server-build/blob/main/changelog/archive/releases/2026-10-07.json)

## 0.261006.1 — 2026-10-06

- Restored missing Wildcard tables through corrective migrations while preserving existing data.
- Fixed launcher integration with the bundled Python runtime.
- Updated SQUID Playerbots to 1.8.1.
- Improved incomplete SQUID database import detection and initialization handling.

[Release](https://github.com/Corfirean/coa-server-build/releases/tag/server-0.261006.1)

## 0.261005.22 — 2026-10-05

- Fixed startup with the bundled Python runtime.
- Included grouped bot looting defaults, partial Dungeon Finder parties and optional open-world life steal.
- Added dungeon damage controls, auction source filtering and cumulative database repairs.

[Release](https://github.com/Corfirean/coa-server-build/releases/tag/server-0.261005.22)

## 0.261005.0 — 2026-10-04

- Restored missing Wildcard character tables while preserving existing rows.
- Server packages now include the expected database structure for update validation.

[Release](https://github.com/Corfirean/coa-server-build/releases/tag/server-0.261005.0)

## 0.261003.17 — 2026-10-03

- Companions follow safer navigation paths.
- Dungeon Finder respects scaled realm levels across enabled expansions.
- Companions follow and recover movement more consistently.
- Companions fly from the opening of Burning Crusade content.
- Companions avoid helmets and shoulders with missing models.
- Companion equipment repair continues with full bags.
- All dungeon difficulties and combat gear variants follow realm progression.
- Custom progression at level 80 now scales item requirements and rewards consistently.
- Downscaled dungeon creatures keep their loot rewards.
- Dungeon Finder shows all enabled expansions at a reduced level cap.
- Items now scale correctly on servers with a reduced level cap.
- Scaled encounters retain normal boss loot.
- Remote console shutdown no longer blocks server management.
- Bots get level-appropriate gear without holiday, event or vanity items.
- Existing bots follow a lowered server level cap.
- Destroyed instances release their saved scaling state.
- Invalid progression settings stop scaling before items are changed.
- Disabling Content Scaling now stops item and group finder changes.
- Explicit scaling overrides now take priority over generated content profiles.

[Archived release record](https://github.com/Corfirean/coa-server-build/blob/main/changelog/archive/releases/2026-10-03-server17.json)

## 0.261002.13 — 2026-10-03

- Dungeons and raids scale to your group size, with solo modes.
- TBC and WotLK content packs.
- Boss health scaling reads the real raid difficulty table.
- NPC Enchanter may say an empty line on servers without its config file.

[Archived release record](https://github.com/Corfirean/coa-server-build/blob/main/changelog/archive/releases/2026-10-03.json)

## 0.261002.12 — 2026-10-02

- Bots no longer take Realm First achievements.
- Starter pack bots get 22-slot bags.
- Trade with your bots.
- Dungeon fill picks bots by role more reliably.
- NPC Enchanter in Orgrimmar and Stormwind.
- Browse tab lists every online bot.
- Collect gold and Stock tabs for the bot economy.
- Invite one bot by role.
- Bot economy, experimental and off by default.
- Master switch for the companion bots.
- A huge .botcmd spawnrandom no longer floods the server.
- Auction House Bot is built in but inactive until configured.
- Optional fee for the NPC Enchanter.

[Archived release record](https://github.com/Corfirean/coa-server-build/blob/main/changelog/archive/releases/2026-10-02.json)

## 0.2.0 — 2026-09-30

- Initial signed base package for installing a clean server through CoA Server Manager.

[Archived release record](https://github.com/Corfirean/coa-server-build/releases/tag/base)
