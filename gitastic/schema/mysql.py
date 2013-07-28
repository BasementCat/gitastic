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

}