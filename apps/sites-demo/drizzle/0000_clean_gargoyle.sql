CREATE TABLE `evidence_items` (
	`id` text PRIMARY KEY NOT NULL,
	`symbol` text NOT NULL,
	`title` text NOT NULL,
	`publisher` text NOT NULL,
	`source_tier` integer NOT NULL,
	`source_uri` text NOT NULL,
	`published_at` text NOT NULL,
	`retrieved_at` text NOT NULL,
	`content_hash` text NOT NULL,
	`summary` text NOT NULL,
	`status` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `evidence_source_hash_idx` ON `evidence_items` (`source_uri`,`content_hash`);--> statement-breakpoint
CREATE TABLE `portfolios` (
	`id` text PRIMARY KEY NOT NULL,
	`owner_email` text NOT NULL,
	`name` text NOT NULL,
	`base_currency` text DEFAULT 'INR' NOT NULL,
	`is_demo` integer DEFAULT 1 NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `portfolios_owner_name_idx` ON `portfolios` (`owner_email`,`name`);--> statement-breakpoint
CREATE TABLE `prices` (
	`symbol` text PRIMARY KEY NOT NULL,
	`instrument_name` text NOT NULL,
	`price` real NOT NULL,
	`previous_close` real NOT NULL,
	`source_label` text NOT NULL,
	`source_uri` text NOT NULL,
	`as_of` text NOT NULL,
	`currency` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `transactions` (
	`id` text PRIMARY KEY NOT NULL,
	`portfolio_id` text NOT NULL,
	`owner_email` text NOT NULL,
	`symbol` text NOT NULL,
	`instrument_name` text NOT NULL,
	`transaction_type` text NOT NULL,
	`quantity` real NOT NULL,
	`unit_price` real NOT NULL,
	`fees` real DEFAULT 0 NOT NULL,
	`occurred_at` text NOT NULL,
	`reverses_transaction_id` text,
	`idempotency_key` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`portfolio_id`) REFERENCES `portfolios`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `transactions_idempotency_idx` ON `transactions` (`idempotency_key`);--> statement-breakpoint
CREATE INDEX `transactions_owner_portfolio_time_idx` ON `transactions` (`owner_email`,`portfolio_id`,`occurred_at`);