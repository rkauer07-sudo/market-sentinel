-- Execute uma vez no SQL Editor do Supabase. O navegador nunca acessa estas
-- tabelas diretamente; somente a API do Market Sentinel usa a service role.
create table if not exists public.sentinel_users (
  wallet_address text primary key check (wallet_address ~ '^0x[0-9a-f]{40}$'),
  display_name text,
  plan text not null default 'free',
  subscription_status text not null default 'inactive',
  subscription_provider text,
  external_customer_id text,
  current_period_end bigint,
  created_at bigint not null default extract(epoch from now())::bigint,
  last_login_at bigint not null default extract(epoch from now())::bigint
);

create table if not exists public.sentinel_auth_nonces (
  nonce_hash text primary key,
  wallet_address text not null,
  message text not null,
  expires_at bigint not null,
  used_at bigint
);
create index if not exists sentinel_auth_nonces_wallet_idx
  on public.sentinel_auth_nonces(wallet_address, expires_at desc);

create table if not exists public.sentinel_chat_messages (
  id bigint generated always as identity primary key,
  wallet_address text not null references public.sentinel_users(wallet_address),
  body text not null check (char_length(body) between 1 and 500),
  created_at bigint not null default extract(epoch from now())::bigint,
  deleted_at bigint
);
create index if not exists sentinel_chat_messages_id_idx
  on public.sentinel_chat_messages(id desc) where deleted_at is null;

alter table public.sentinel_users enable row level security;
alter table public.sentinel_auth_nonces enable row level security;
alter table public.sentinel_chat_messages enable row level security;

-- Sem políticas públicas: anon/authenticated não leem nem escrevem. A service
-- role utilizada somente no backend ignora RLS.
