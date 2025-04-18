-- transformation/models/staging/stg_votes.sql
{{
  config(
    materialized = 'view'
  )
}}

SELECT
  vote_id,
  voter_id,
  candidate,
  timestamp as recorded_timestamp,
  voted_at,
  precinct
FROM {{ source('voting_data', 'votes') }}