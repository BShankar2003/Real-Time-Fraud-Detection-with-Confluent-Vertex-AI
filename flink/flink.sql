CREATE TABLE raw_transactions (
    transaction_id STRING,
    user_id STRING,
    merchant_id STRING,
    amount DOUBLE,
    `timestamp` BIGINT
) WITH (
    'value.format' = 'json-registry'
);

CREATE TABLE enriched_transactions (
    transaction_id STRING,
    user_id STRING,
    merchant_id STRING,
    amount DOUBLE,
    `timestamp` BIGINT,
    amount_category STRING
) WITH (
    'value.format' = 'json-registry'
);

INSERT INTO enriched_transactions
SELECT
    transaction_id,
    user_id,
    merchant_id,
    amount,
    `timestamp`,
    CASE
        WHEN amount > 50000 THEN 'VERY_HIGH'
        WHEN amount > 30000 THEN 'HIGH'
        WHEN amount > 10000 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS amount_category
FROM raw_transactions;

CREATE TABLE fraud_predictions (
    transaction_id STRING,
    user_id STRING,
    amount DOUBLE,
    fraud_score DOUBLE,
    decision STRING,
    risk_level STRING,
    txn_count_1min INT,
    total_amount_1min DOUBLE,
    reasons STRING
) WITH (
    'value.format' = 'json-registry'
);
