CREATE TABLE `email_import_items` (
	`id` text PRIMARY KEY NOT NULL,
	`owner_email` text NOT NULL,
	`portfolio_id` text,
	`message_id` text NOT NULL,
	`attachment_id` text NOT NULL,
	`sender_email` text NOT NULL,
	`subject` text NOT NULL,
	`filename` text NOT NULL,
	`mime_type` text NOT NULL,
	`source_hash` text NOT NULL,
	`storage_key` text NOT NULL,
	`message_at` text,
	`status` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`portfolio_id`) REFERENCES `portfolios`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `email_import_items_owner_attachment_idx` ON `email_import_items` (`owner_email`,`message_id`,`attachment_id`);--> statement-breakpoint
CREATE INDEX `email_import_items_owner_status_idx` ON `email_import_items` (`owner_email`,`status`);--> statement-breakpoint
CREATE TABLE `email_import_preferences` (
	`owner_email` text PRIMARY KEY NOT NULL,
	`wealth_manager_email` text,
	`prompt_status` text DEFAULT 'pending' NOT NULL,
	`consented_at` text,
	`last_synced_at` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `mailbox_connections` (
	`id` text PRIMARY KEY NOT NULL,
	`owner_email` text NOT NULL,
	`provider` text NOT NULL,
	`status` text NOT NULL,
	`access_token_ciphertext` text NOT NULL,
	`access_token_iv` text NOT NULL,
	`refresh_token_ciphertext` text,
	`refresh_token_iv` text,
	`token_expires_at` text,
	`granted_scope` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `mailbox_connections_owner_provider_idx` ON `mailbox_connections` (`owner_email`,`provider`);--> statement-breakpoint
CREATE TABLE `portfolio_value_snapshots` (
	`id` text PRIMARY KEY NOT NULL,
	`portfolio_id` text NOT NULL,
	`owner_email` text NOT NULL,
	`observed_at` text NOT NULL,
	`total_value` real NOT NULL,
	`total_cost` real NOT NULL,
	`source_mode` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`portfolio_id`) REFERENCES `portfolios`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `portfolio_value_snapshots_owner_observed_idx` ON `portfolio_value_snapshots` (`owner_email`,`portfolio_id`,`observed_at`);--> statement-breakpoint
CREATE INDEX `portfolio_value_snapshots_owner_time_idx` ON `portfolio_value_snapshots` (`owner_email`,`portfolio_id`,`observed_at`);