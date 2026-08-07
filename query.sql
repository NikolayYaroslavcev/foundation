SELECT u.id, u.email
FROM users u
JOIN subscriptions s ON s.user_id = u.id
WHERE s.status = 'active'
  AND NOT EXISTS (
    SELECT 1
    FROM meetings_attendance ma
    WHERE ma.user_id = u.id
      AND ma.date >= CURRENT_DATE - INTERVAL '30 days'
  );
