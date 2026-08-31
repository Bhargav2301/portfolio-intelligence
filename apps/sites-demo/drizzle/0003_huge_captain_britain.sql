CREATE TABLE `instrument_mappings` (
	`id` text PRIMARY KEY NOT NULL,
	`portfolio_id` text NOT NULL,
	`owner_email` text NOT NULL,
	`symbol` text NOT NULL,
	`exchange` text NOT NULL,
	`analysis_symbol` text,
	`status` text NOT NULL,
	`source` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`portfolio_id`) REFERENCES `portfolios`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `instrument_mappings_portfolio_symbol_idx` ON `instrument_mappings` (`portfolio_id`,`symbol`);--> statement-breakpoint
CREATE INDEX `instrument_mappings_owner_idx` ON `instrument_mappings` (`owner_email`,`portfolio_id`,`symbol`);