$ cd "/c/Users/benny/OneDrive/Desktop/Projects/Versos Round 3" && echo "=== segment_metrics (the two seeded segments) ===" && docker compose exec -T postgres psql -U versos -d versos -c "select severity,category,total,reviewed,approved,accept_rate,reviewed_eligible,precision_eligible from segment_metrics where category in ('media_quality','billing') and severity in ('low','medium') order by severity,category;" && echo "=== promotion_readiness — the flip rule ===" && docker compose exec -T postgres psql -U versos -d versos -c "select severity,category,reviewed_eligible,accept_rate,precision_eligible,eligible_for_auto from promotion_readiness where eligible_for_auto is not null order by eligible_for_auto desc, severity;"

=== segment_metrics (the two seeded segments) ===
 severity |   category    | total | reviewed | approved | accept_rate | reviewed_eligible | precision_eligible 
----------+---------------+-------+----------+----------+-------------+-------------------+--------------------
 low      | billing       |     2 |        0 |        0 |             |                 0 |                   
 low      | media_quality |    41 |       40 |       39 |       0.975 |                40 |              0.975
 medium   | billing       |    35 |       25 |       18 |       0.720 |                25 |              0.720
 medium   | media_quality |     1 |        0 |        0 |             |                 0 |                   
(4 rows)

=== promotion_readiness — the flip rule ===
 severity |    category    | reviewed_eligible | accept_rate | precision_eligible | eligible_for_auto 
----------+----------------+-------------------+-------------+--------------------+-------------------
 low      | media_quality  |                40 |       0.975 |              0.975 | t
 high     | account_access |                 1 |       1.000 |              1.000 | f
 high     | other          |                 2 |       1.000 |              1.000 | f
 high     | billing        |                 0 |             |                    | f
 low      | other          |                 0 |       0.500 |                    | f
 low      | billing        |                 0 |             |                    | f
 medium   | account_access |                 0 |       1.000 |                    | f
 medium   | billing        |                25 |       0.720 |              0.720 | f
 medium   | media_quality  |                 0 |             |                    | f
 medium   | other          |                 0 |       1.000 |                    | f
(10 rows)