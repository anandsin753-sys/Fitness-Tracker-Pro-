CREATE TABLE IF NOT EXISTS payment_transaction (
    id INTEGER NOT NULL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    order_id VARCHAR(64) NOT NULL UNIQUE,
    payment_id VARCHAR(64) UNIQUE,
    amount_subunits INTEGER NOT NULL,
    currency VARCHAR(3) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL,
    paid_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES "user" (id)
);

CREATE INDEX IF NOT EXISTS ix_payment_transaction_user_id
    ON payment_transaction (user_id);
CREATE INDEX IF NOT EXISTS ix_payment_transaction_status
    ON payment_transaction (status);
