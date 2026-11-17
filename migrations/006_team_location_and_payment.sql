BEGIN IMMEDIATE;
ALTER TABLE teams ADD COLUMN city TEXT;
ALTER TABLE teams ADD COLUMN state TEXT;
ALTER TABLE teams ADD COLUMN payment_received_date DATE;
ALTER TABLE teams ADD COLUMN payment_channel TEXT CHECK (payment_channel IN ('PayPal','Venmo','Zelle','Check'));
ALTER TABLE teams ADD COLUMN payment_amount NUMERIC CHECK (payment_amount IS NULL OR payment_amount >= 0);
COMMIT;
