CREATE TABLE `portfolio_prices` (
	`id` text PRIMARY KEY NOT NULL,
	`portfolio_id` text NOT NULL,
	`owner_email` text NOT NULL,
	`symbol` text NOT NULL,
	`instrument_name` text NOT NULL,
	`price` real NOT NULL,
	`previous_close` real NOT NULL,
	`source_label` text NOT NULL,
	`source_uri` text NOT NULL,
	`as_of` text NOT NULL,
	`currency` text NOT NULL,
	FOREIGN KEY (`portfolio_id`) REFERENCES `portfolios`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `portfolio_prices_portfolio_symbol_idx` ON `portfolio_prices` (`portfolio_id`,`symbol`);--> statement-breakpoint
CREATE INDEX `portfolio_prices_owner_idx` ON `portfolio_prices` (`owner_email`,`portfolio_id`,`symbol`);