-- Schema pronto pra quando conectar o Supabase (hoje os mesmos dados vivem
-- em data/*.json e cada postagem gera um commit automático no repositório).
-- Rodar isso no SQL Editor do Supabase (plano gratuito) cria as tabelas;
-- a migração dos scripts Python pra gravar aqui em vez de nos JSON é o
-- próximo passo, feito com calma, sem pressa de trocar tudo de uma vez.

create table if not exists products (
  item_id         bigint primary key,
  niche           text not null,
  product_name    text,
  price_min       numeric,
  price_max       numeric,
  discount_rate   integer,
  commission_rate numeric,
  sales           integer,
  rating_star     numeric,
  image_url       text,
  offer_link      text,
  updated_at      timestamptz not null default now()
);

create index if not exists products_niche_idx on products (niche);
create index if not exists products_discount_idx on products (discount_rate desc);

-- um registro por post enviado (Telegram ou WhatsApp), substitui
-- data/posted_ids.json + data/whatsapp_posted_ids.json + data/log_postagens.json
create table if not exists post_log (
  id         bigint generated always as identity primary key,
  channel    text not null check (channel in ('telegram', 'whatsapp')),
  item_id    bigint references products (item_id),
  ok         boolean not null default true,
  posted_at  timestamptz not null default now()
);

create index if not exists post_log_channel_idx on post_log (channel, posted_at desc);
create index if not exists post_log_item_idx on post_log (item_id);

-- snapshot do relatório de vendas, um por execução do fetch_sales_report.py
create table if not exists sales_snapshots (
  id            bigint generated always as identity primary key,
  period_days   integer not null,
  conversions   integer not null default 0,
  orders        integer not null default 0,
  qty           integer not null default 0,
  commission    numeric not null default 0,
  generated_at  timestamptz not null default now()
);

-- detalhe por produto de cada snapshot (só populado quando tiver venda)
create table if not exists sales_by_product (
  id            bigint generated always as identity primary key,
  snapshot_id   bigint not null references sales_snapshots (id) on delete cascade,
  item_id       bigint references products (item_id),
  conversions   integer not null default 0,
  orders        integer not null default 0,
  qty           integer not null default 0,
  commission    numeric not null default 0
);

-- saúde do robô, substitui data/telegram_status.json
create table if not exists bot_health (
  id                    bigint generated always as identity primary key,
  status                text not null check (status in ('ok', 'alerta')),
  minutes_since_last    numeric,
  threshold_minutes     numeric,
  checked_at            timestamptz not null default now()
);

-- view pronta pro painel: total de posts e comissão dos últimos 30 dias
create or replace view dashboard_last_30_days as
select
  (select count(*) from post_log where channel = 'telegram' and posted_at > now() - interval '30 days') as telegram_posts,
  (select count(*) from post_log where channel = 'whatsapp' and posted_at > now() - interval '30 days') as whatsapp_posts,
  (select coalesce(sum(commission), 0) from sales_snapshots where generated_at > now() - interval '30 days') as commission_30d,
  (select status from bot_health order by checked_at desc limit 1) as bot_status;

-- Row Level Security: deixado desligado por padrão (uso pessoal, só vocês
-- dois acessam via chave de serviço). Se um dia ligar Supabase Auth com
-- login próprio pra cada um, é só habilitar RLS em cada tabela e criar as
-- policies -- não precisa fazer isso agora.
