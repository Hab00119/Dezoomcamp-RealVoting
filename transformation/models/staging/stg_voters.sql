-- transformation/models/staging/stg_voters.sql
{{
  config(
    materialized = 'view'
  )
}}

SELECT
  voter_id,
  first_name,
  last_name,
  date_of_birth,
  gender,
  address,
  city,
  state,
  zipcode,
  registration_date,
  party_affiliation,
  CASE 
    WHEN DATEDIFF(YEAR, date_of_birth, CURRENT_DATE) < 25 THEN '18-24'
    WHEN DATEDIFF(YEAR, date_of_birth, CURRENT_DATE) < 35 THEN '25-34'
    WHEN DATEDIFF(YEAR, date_of_birth, CURRENT_DATE) < 50 THEN '35-49'
    WHEN DATEDIFF(YEAR, date_of_birth, CURRENT_DATE) < 65 THEN '50-64'
    ELSE '65+'
  END AS age_group,
  state AS region
FROM {{ source('voting_data', 'voters') }}