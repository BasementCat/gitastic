schema={
	0: """
		CREATE  TABLE `schema_change` (
		`schema_change_id` BIGINT NOT NULL AUTO_INCREMENT ,
		`applied_date` DATETIME NOT NULL ,
		`schema_version` BIGINT NOT NULL ,
		PRIMARY KEY (`schema_change_id`) ,
		UNIQUE INDEX `schema_version_UNIQUE` (`schema_version` ASC) ,
		INDEX `applied_date` (`applied_date` ASC) )
		ENGINE = InnoDB;""",
	1: """
		CREATE  TABLE `user` (
		`user_id` BIGINT NOT NULL AUTO_INCREMENT ,
		`username` VARCHAR(128) NOT NULL ,
		`email` TEXT NOT NULL ,
		`password` TEXT NOT NULL ,
		PRIMARY KEY (`user_id`) ,
		UNIQUE INDEX `username_UNIQUE` (`username` ASC) )
		ENGINE = InnoDB;""",
	2: """
		CREATE  TABLE `user_ssh_key` (
		`user_ssh_key_id` BIGINT NOT NULL AUTO_INCREMENT ,
		`user_id` BIGINT NOT NULL ,
		`name` TEXT NOT NULL ,
		`key` TEXT NOT NULL ,
		PRIMARY KEY (`user_ssh_key_id`) ,
		INDEX `fk_user_ssh_key_user` (`user_id` ASC) ,
		CONSTRAINT `fk_user_ssh_key_user`
		FOREIGN KEY (`user_id` )
		REFERENCES `user` (`user_id` )
		ON DELETE CASCADE
		ON UPDATE CASCADE)
		ENGINE = InnoDB;""",
	3: """
		CREATE  TABLE `repository` (
		`repository_id` BIGINT NOT NULL AUTO_INCREMENT ,
		`name` VARCHAR(128) NOT NULL ,
		`description` TEXT NOT NULL ,
		`owner_user_id` BIGINT NOT NULL ,
		PRIMARY KEY (`repository_id`) ,
		UNIQUE INDEX `name_UNIQUE` (`name` ASC) )
		ENGINE = InnoDB
		COMMENT = 'owner_user_id should be fk to user.user_id';""",
	4: """ALTER TABLE `repository` ADD COLUMN `public` TINYINT(1) NOT NULL DEFAULT 1  AFTER `description` ;""",
	5: """
		ALTER TABLE `repository` ADD COLUMN `path` VARCHAR(128) NOT NULL  AFTER `name` 
		, ADD UNIQUE INDEX `path_UNIQUE` (`path` ASC) ;""",
	6: """ALTER TABLE `repository` DROP INDEX `name_UNIQUE` ;""",
	7: """
		ALTER TABLE `repository`
		DROP INDEX `path_UNIQUE`
		, ADD UNIQUE INDEX `path_UNIQUE` (`name` ASC, `owner_user_id` ASC) ;""",
	8: """
		ALTER TABLE `user_ssh_key`
			ADD COLUMN `timestamp` DATETIME NOT NULL  AFTER `key` ,
			ADD COLUMN `added_from_ip` VARCHAR(64) NOT NULL DEFAULT '0.0.0.0'  AFTER `timestamp` ;""",
	9: """
		CREATE  TABLE `repository_access` (
		`repository_id` BIGINT NOT NULL ,
		`user_id` BIGINT NOT NULL ,
		`access` INT NOT NULL DEFAULT 0 ,
		PRIMARY KEY (`repository_id`, `user_id`) ,
		INDEX `fk_repository_access_repo` (`repository_id` ASC) ,
		INDEX `fk_repository_access_user` (`user_id` ASC) ,
		CONSTRAINT `fk_repository_access_repo`
		FOREIGN KEY (`repository_id` )
		REFERENCES `repository` (`repository_id` )
		ON DELETE CASCADE
		ON UPDATE CASCADE,
		CONSTRAINT `fk_repository_access_user`
		FOREIGN KEY (`user_id` )
		REFERENCES `user` (`user_id` )
		ON DELETE CASCADE
		ON UPDATE CASCADE)
		ENGINE = InnoDB;""",
}