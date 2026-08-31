-- Reset the owner pilot without touching any real portfolio. Child rows must be
-- removed explicitly because the original D1 foreign keys do not cascade.
DELETE FROM `instrument_mappings` WHERE `portfolio_id` IN (SELECT `id` FROM `portfolios` WHERE `is_demo` = 1);
--> statement-breakpoint
DELETE FROM `portfolio_prices` WHERE `portfolio_id` IN (SELECT `id` FROM `portfolios` WHERE `is_demo` = 1);
--> statement-breakpoint
DELETE FROM `transactions` WHERE `portfolio_id` IN (SELECT `id` FROM `portfolios` WHERE `is_demo` = 1);
--> statement-breakpoint
DELETE FROM `portfolios` WHERE `is_demo` = 1;
--> statement-breakpoint
DELETE FROM `prices` WHERE `source_label` = 'Demo exchange snapshot' OR `source_uri` LIKE 'https://example.com/demo/%';
--> statement-breakpoint
DELETE FROM `evidence_items` WHERE `publisher` = 'Demo Exchange' OR `source_uri` LIKE 'https://example.com/demo/%';
--> statement-breakpoint
CREATE TABLE `evidence_documents` (
	`id` text PRIMARY KEY NOT NULL,
	`owner_email` text NOT NULL,
	`portfolio_id` text,
	`import_batch_id` text,
	`source_filename` text NOT NULL,
	`mime_type` text NOT NULL,
	`source_hash` text NOT NULL,
	`title` text NOT NULL,
	`publisher` text,
	`published_at` text,
	`storage_key` text,
	`status` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`portfolio_id`) REFERENCES `portfolios`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`import_batch_id`) REFERENCES `import_batches`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `evidence_documents_owner_hash_idx` ON `evidence_documents` (`owner_email`,`source_hash`);--> statement-breakpoint
CREATE INDEX `evidence_documents_owner_portfolio_idx` ON `evidence_documents` (`owner_email`,`portfolio_id`);--> statement-breakpoint
CREATE TABLE `import_batches` (
	`id` text PRIMARY KEY NOT NULL,
	`owner_email` text NOT NULL,
	`portfolio_id` text,
	`source_kind` text NOT NULL,
	`source_filename` text,
	`source_hash` text NOT NULL,
	`status` text NOT NULL,
	`row_count` integer NOT NULL,
	`valid_row_count` integer NOT NULL,
	`warning_count` integer DEFAULT 0 NOT NULL,
	`error_count` integer DEFAULT 0 NOT NULL,
	`raw_retained` integer DEFAULT 0 NOT NULL,
	`created_at` text NOT NULL,
	`committed_at` text,
	FOREIGN KEY (`portfolio_id`) REFERENCES `portfolios`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `import_batches_owner_hash_idx` ON `import_batches` (`owner_email`,`source_hash`);--> statement-breakpoint
CREATE INDEX `import_batches_owner_created_idx` ON `import_batches` (`owner_email`,`created_at`);--> statement-breakpoint
CREATE TABLE `import_rows` (
	`id` text PRIMARY KEY NOT NULL,
	`batch_id` text NOT NULL,
	`row_number` integer NOT NULL,
	`row_kind` text NOT NULL,
	`raw_json` text,
	`normalized_json` text,
	`validation_status` text NOT NULL,
	`validation_message` text,
	FOREIGN KEY (`batch_id`) REFERENCES `import_batches`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `import_rows_batch_row_idx` ON `import_rows` (`batch_id`,`row_number`);--> statement-breakpoint
CREATE INDEX `import_rows_batch_status_idx` ON `import_rows` (`batch_id`,`validation_status`);--> statement-breakpoint
CREATE TABLE `portfolio_lots` (
	`id` text PRIMARY KEY NOT NULL,
	`portfolio_id` text NOT NULL,
	`owner_email` text NOT NULL,
	`import_batch_id` text,
	`symbol` text NOT NULL,
	`exchange` text NOT NULL,
	`instrument_name` text NOT NULL,
	`quantity` real NOT NULL,
	`unit_cost` real NOT NULL,
	`acquired_at` text,
	`source_row_number` integer,
	`created_at` text NOT NULL,
	FOREIGN KEY (`portfolio_id`) REFERENCES `portfolios`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`import_batch_id`) REFERENCES `import_batches`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `portfolio_lots_owner_portfolio_symbol_idx` ON `portfolio_lots` (`owner_email`,`portfolio_id`,`symbol`);--> statement-breakpoint
CREATE INDEX `portfolio_lots_import_batch_idx` ON `portfolio_lots` (`import_batch_id`);
