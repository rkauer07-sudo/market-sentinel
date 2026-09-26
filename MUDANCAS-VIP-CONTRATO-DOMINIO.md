# Contrato de pagamento, códigos de desconto, feedback e domínio novo

## 1. Contrato inteligente (Solana, nativo, mínimo)

Código: `contracts/vip-payment/src/lib.rs` — ~130 linhas, sem Anchor e sem contas
de estado, para o deploy sair o mais barato possível (tipicamente 0,1–0,3 SOL de
aluguel do programa; o valor volta se você fechar o programa um dia).

O que ele faz: a instrução `pay` confere que o destino é a conta **USDC** da
**tesouraria gravada no código** e repassa o valor na hora (`TransferChecked`).
Nada fica preso no contrato. O backend só libera o VIP se a transação passou
pelo contrato **e** a tesouraria recebeu o valor do pedido (com desconto).

### Antes do deploy — obrigatório
Em `lib.rs`, troque o placeholder pela sua carteira de tesouraria (a mesma do
`VIP_TREASURY_WALLET` no Vercel):

```rust
pub const TREASURY: Pubkey = pubkey!("SUA_CARTEIRA_AQUI");
```
Com o placeholder (`1111…1111`) todo pagamento **falha** — de propósito, para
nunca mandar USDC para o lugar errado.

### Deploy pelo Solana Playground (sem instalar nada no Windows)
1. Abra https://beta.solpg.io → **Create a new project** → framework **Native (Rust)**.
2. Substitua o `lib.rs` pelo conteúdo de `contracts/vip-payment/src/lib.rs` (já com a tesouraria trocada).
3. Canto inferior esquerdo: conecte a carteira do Playground, mude o cluster para **mainnet-beta**
   (Settings → Endpoint) e mande ~0,3 SOL para ela.
4. **Build** → **Deploy**. Copie o **Program ID** mostrado.
5. (Opcional, economiza SOL) Depois do deploy, em Settings dá para tornar o programa
   imutável ou manter a upgrade authority para futuras mudanças — recomendo manter.

Alternativa CLI: `cargo build-sbf` + `solana program deploy target/deploy/market_sentinel_vip.so`.

### Variáveis no Vercel
- `VIP_PROGRAM_ID` = Program ID do passo 4 (sem ele, o site continua aceitando transferência direta — modo antigo).
- `VIP_TREASURY_WALLET` = a mesma carteira do `TREASURY` do contrato.
- Redeploy.

## 2. Códigos de desconto (criados por você no Turso)

Tabelas criadas automaticamente no primeiro acesso: `discount_codes` e
`discount_redemptions`. No painel do Turso (ou `turso db shell <db>`):

```sql
-- 20% de desconto, ilimitado (cada carteira usa 1x)
INSERT INTO discount_codes (code, percent) VALUES ('AMIGO20', 20);

-- 100% (VIP grátis), no máximo 10 carteiras, expira em 31/12/2026
INSERT INTO discount_codes (code, percent, max_uses, expires_at, note)
VALUES ('PARCEIRO100', 100, 10, strftime('%s','2026-12-31 23:59:59'), 'parceiros');

-- desativar / ver usos
UPDATE discount_codes SET active = 0 WHERE code = 'AMIGO20';
SELECT code, COUNT(*) FROM discount_redemptions GROUP BY code;
```
Regras: percentual de 5 a 100 (o banco recusa fora disso), código sem diferenciar
maiúsculas, **1 uso por carteira**, `max_uses` e `expires_at` opcionais.
Com 100% o VIP é liberado na hora, sem transação.

## 3. Feedback / Contato
Menu novo “Feedback / Contato”. Qualquer visitante envia (anti-spam: 5/hora por IP,
campo isca para bots). A caixa de entrada aparece na mesma seção **só** quando a
carteira `GVMPqSU3KZTKa58cKLZreZx46rTWVLhEWXJ7DdebDKH8` está logada
(`FEEDBACK_ADMIN_WALLETS` muda isso). Tabela: `feedback_messages`.

## 4. Domínio marketsentinel.xyz (GoDaddy → Vercel)
1. Vercel → projeto → **Settings → Domains** → adicione `marketsentinel.xyz` e
   `www.marketsentinel.xyz` (www redirecionando para o raiz). Deixe
   `market-sentinel-sable.vercel.app` como está.
2. GoDaddy → **Meus produtos → DNS** de marketsentinel.xyz:
   - apague o registro **A** `@` que aponta para o "Parked" da GoDaddy;
   - **A** `@` → `76.76.21.21`;
   - **CNAME** `www` → `cname.vercel-dns.com`
   (se o Vercel mostrar valores específicos do projeto na tela de Domains, use os dele).
3. Espere o Vercel marcar “Valid Configuration” (minutos a poucas horas) — o SSL sai sozinho.
4. Só então defina no Vercel `CANONICAL_HOST=marketsentinel.xyz` e
   `REDIRECT_HOSTS=market-sentinel-sable.vercel.app,www.marketsentinel.xyz` e faça redeploy:
   o endereço antigo passa a redirecionar (308) para o novo.
5. Atualize links externos: `HELIUS_WEBHOOK_URL` (o webhook continua funcionando
   no domínio antigo, mas prefira o novo), bio/Telegram/X.

Observação: o login é por domínio — usuários precisam conectar a carteira de novo no
domínio novo (o VIP fica salvo na carteira, nada se perde).
