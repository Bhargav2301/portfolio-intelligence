CREATE TABLE `account_holdings` (
	`id` text PRIMARY KEY NOT NULL,
	`connection_id` text NOT NULL,
	`owner_email` text NOT NULL,
	`provider` text NOT NULL,
	`instrument_key` text NOT NULL,
	`symbol` text NOT NULL,
	`instrument_name` text NOT NULL,
	`quantity` real NOT NULL,
	`average_price` real NOT NULL,
	`last_price` real NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`connection_id`) REFERENCES `broker_connections`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `account_holdings_connection_instrument_idx` ON `account_holdings` (`connection_id`,`instrument_key`);--> statement-breakpoint
CREATE INDEX `account_holdings_owner_idx` ON `account_holdings` (`owner_email`,`provider`,`symbol`);--> statement-breakpoint
CREATE TABLE `broker_connections` (
	`id` text PRIMARY KEY NOT NULL,
	`owner_email` text NOT NULL,
	`provider` text NOT NULL,
	`provider_user_id` text,
	`status` text NOT NULL,
	`access_token_ciphertext` text NOT NULL,
	`access_token_iv` text NOT NULL,
	`token_expires_at` text,
	`last_synced_at` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `broker_connections_owner_provider_idx` ON `broker_connections` (`owner_email`,`provider`);--> statement-breakpoint
CREATE TABLE `oauth_states` (
	`state_hash` text PRIMARY KEY NOT NULL,
	`owner_email` text NOT NULL,
	`provider` text NOT NULL,
	`expires_at` text NOT NULL,
	`created_at` text NOT NULL
);
