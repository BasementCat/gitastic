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
}