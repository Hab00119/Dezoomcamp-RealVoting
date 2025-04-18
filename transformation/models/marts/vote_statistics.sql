-- transformation/models/marts/vote_statistics.sql
{{
  config(
    materialized = 'table'
  )
}}

SELECT
  v.candidate,
  COUNT(*) as vote_count,
  v.precinct,
  vr.age_group,
  vr.gender,
  vr.region,
  DATE_TRUNC('hour', v.voted_at) as hour_voted
FROM {{ ref('stg_votes') }} v
JOIN {{ ref('stg_voters') }} vr ON v.voter_id = vr.voter_id
GROUP BY
  v.candidate,
  v.precinct,
  vr.age_group,
  vr.gender,
  vr.region,
  DATE_TRUNC('hour', v.voted_at)