-- Table structure for character_coa_lfg_settings
CREATE TABLE IF NOT EXISTS `character_coa_lfg_settings` (
  `guid` INT UNSIGNED NOT NULL,
  `composition_mode` TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '0=MATCHMAKING, 1=BOT_FILL, 2=CURRENT_PARTY',
  `challenge_size` TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '0=Adaptive, 1..40=Virtual player count',
  PRIMARY KEY (`guid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
