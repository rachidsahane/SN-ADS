-- Token lifetime visible to the database (official Supabase self-hosting step), read from JWT_EXP
\set jwt_exp `echo "$JWT_EXP"`

ALTER DATABASE postgres SET "app.settings.jwt_exp" TO :'jwt_exp';
