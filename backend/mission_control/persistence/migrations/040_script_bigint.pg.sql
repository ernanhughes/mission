-- MC-POSTGRES-01: SQLite INTEGER is 64-bit; SQLAlchemy Integer maps to PG INT4.
-- script_records.mtime_ns holds nanosecond timestamps (~1.8e18) and file_size
-- can exceed INT4. ORM models.py now declares BigInteger for both columns.
ALTER TABLE "script_records" ALTER COLUMN "mtime_ns" TYPE BIGINT;
ALTER TABLE "script_records" ALTER COLUMN "file_size" TYPE BIGINT;
-- process_instances.exit_code can hold Windows unsigned 32-bit termination
-- codes (up to 4294967295), which exceed INT4. ORM declares BigInteger.
ALTER TABLE "process_instances" ALTER COLUMN "exit_code" TYPE BIGINT;
