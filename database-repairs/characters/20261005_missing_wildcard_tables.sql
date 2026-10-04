CREATE TABLE IF NOT EXISTS `coa_wildcard_skill_card` (
  `account` INT UNSIGNED NOT NULL,
  `card` INT UNSIGNED NOT NULL,
  `progress` INT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (`account`, `card`)
);

CREATE TABLE IF NOT EXISTS `coa_wildcard_skill_card_pending` (
  `account` INT UNSIGNED NOT NULL,
  `id` INT UNSIGNED NOT NULL,
  `card` INT UNSIGNED NOT NULL,
  PRIMARY KEY (`account`, `id`)
);

CREATE TABLE IF NOT EXISTS `coa_wildcard_skill_card_account` (
  `account` INT UNSIGNED NOT NULL,
  `bonus_progress` INT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (`account`)
);

CREATE TABLE IF NOT EXISTS `coa_wildcard_skill_card_purchase` (
  `account` INT UNSIGNED NOT NULL,
  `type` TINYINT UNSIGNED NOT NULL,
  `count` INT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (`account`, `type`)
);

CREATE TABLE IF NOT EXISTS `coa_wildcard_specialization_cache` (
  `account` INT UNSIGNED NOT NULL,
  `claimed_at` INT UNSIGNED NOT NULL,
  PRIMARY KEY (`account`)
);
