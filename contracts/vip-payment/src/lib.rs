//! Market Sentinel — contrato de pagamento VIP (Solana, nativo, sem Anchor).
//!
//! Mínimo de propósito: sem contas de estado, sem cofre, nada fica preso aqui.
//! A instrução `pay` valida que o destino é a conta USDC da TESOURARIA gravada
//! abaixo e repassa o valor na hora (CPI `TransferChecked` do SPL Token).
//! O backend confere a transação on-chain (programa invocado + valor recebido
//! pela tesouraria + referência/memo do pedido) antes de liberar o VIP.
//!
//! Instrução (único formato):
//!   dados:  [0u8] ++ amount:u64 LE ++ memo (0..=32 bytes UTF-8, ex. "MS-VIP-1A2B3C4D")
//!   contas: 0 pagador (signer)
//!           1 conta USDC do pagador (writable)
//!           2 mint USDC
//!           3 conta USDC da tesouraria (writable)
//!           4 SPL Token program
//!           5 referência do pedido (read-only, opcional — só para busca on-chain)

use solana_program::{
    account_info::AccountInfo,
    instruction::{AccountMeta, Instruction},
    log::sol_log,
    program::invoke,
    program_error::ProgramError,
    pubkey,
    pubkey::Pubkey,
};

/// >>> TROQUE PELA SUA CARTEIRA DE TESOURARIA (a mesma do VIP_TREASURY_WALLET) <<<
/// O placeholder (System Program) faz TODO pagamento falhar — nunca manda USDC pro lugar errado.
pub const TREASURY: Pubkey = pubkey!("99TWGuBvk7XtQ72d4xNfPoFK9aJKN9MFpoWLKAQz1BrD");
/// USDC (mainnet).
pub const USDC_MINT: Pubkey = pubkey!("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v");
pub const TOKEN_PROGRAM: Pubkey = pubkey!("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA");
pub const USDC_DECIMALS: u8 = 6;
pub const MAX_MEMO: usize = 32;

#[repr(u32)]
pub enum VipError {
    BadInstruction = 1,
    NotSigner = 2,
    WrongMint = 3,
    WrongTreasury = 4,
    WrongTokenProgram = 5,
    ZeroAmount = 6,
}

impl From<VipError> for ProgramError {
    fn from(e: VipError) -> Self {
        ProgramError::Custom(e as u32)
    }
}

#[cfg(not(feature = "no-entrypoint"))]
solana_program::entrypoint!(process_instruction);

/// Lê `amount` e `memo` do payload.
pub fn parse(data: &[u8]) -> Result<(u64, &[u8]), ProgramError> {
    if data.len() < 9 || data[0] != 0 || data.len() > 9 + MAX_MEMO {
        return Err(VipError::BadInstruction.into());
    }
    let amount = u64::from_le_bytes(data[1..9].try_into().unwrap());
    if amount == 0 {
        return Err(VipError::ZeroAmount.into());
    }
    Ok((amount, &data[9..]))
}

/// Conta SPL Token: bytes 0..32 = mint, 32..64 = dono.
pub fn check_treasury_account(data: &[u8]) -> Result<(), ProgramError> {
    if data.len() < 64 || data[0..32] != USDC_MINT.to_bytes() {
        return Err(VipError::WrongMint.into());
    }
    if data[32..64] != TREASURY.to_bytes() {
        return Err(VipError::WrongTreasury.into());
    }
    Ok(())
}

pub fn process_instruction(
    _program_id: &Pubkey,
    accounts: &[AccountInfo],
    data: &[u8],
) -> Result<(), ProgramError> {
    let (amount, _memo) = parse(data)?;
    let [payer, source, mint, dest, token_program, ..] = accounts else {
        return Err(ProgramError::NotEnoughAccountKeys);
    };
    if !payer.is_signer {
        return Err(VipError::NotSigner.into());
    }
    if *mint.key != USDC_MINT {
        return Err(VipError::WrongMint.into());
    }
    if *token_program.key != TOKEN_PROGRAM || *dest.owner != TOKEN_PROGRAM {
        return Err(VipError::WrongTokenProgram.into());
    }
    check_treasury_account(&dest.try_borrow_data()?)?;

    // SPL Token TransferChecked = tag 12 ++ amount u64 LE ++ decimals
    let mut ix_data = [0u8; 10];
    ix_data[0] = 12;
    ix_data[1..9].copy_from_slice(&amount.to_le_bytes());
    ix_data[9] = USDC_DECIMALS;
    let ix = Instruction {
        program_id: TOKEN_PROGRAM,
        accounts: vec![
            AccountMeta::new(*source.key, false),
            AccountMeta::new_readonly(*mint.key, false),
            AccountMeta::new(*dest.key, false),
            AccountMeta::new_readonly(*payer.key, true),
        ],
        data: ix_data.to_vec(),
    };
    invoke(&ix, &[source.clone(), mint.clone(), dest.clone(), payer.clone(), token_program.clone()])?;
    // O memo já está nos dados da instrução; o log deixa a leitura trivial no explorer.
    sol_log("MS-VIP pago");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn payload(amount: u64, memo: &[u8]) -> Vec<u8> {
        let mut v = vec![0u8];
        v.extend_from_slice(&amount.to_le_bytes());
        v.extend_from_slice(memo);
        v
    }

    #[test]
    fn parses_amount_and_memo() {
        let data = payload(9_500_000, b"MS-VIP-ABCD1234");
        let (amount, memo) = parse(&data).unwrap();
        assert_eq!(amount, 9_500_000);
        assert_eq!(memo, b"MS-VIP-ABCD1234");
    }

    #[test]
    fn rejects_zero_bad_tag_and_long_memo() {
        assert!(parse(&payload(0, b"x")).is_err());
        let mut bad = payload(1, b"");
        bad[0] = 1;
        assert!(parse(&bad).is_err());
        assert!(parse(&payload(1, &[b'a'; 33])).is_err());
        assert!(parse(&[0u8; 5]).is_err());
    }

    #[test]
    fn treasury_account_must_be_usdc_owned_by_treasury() {
        let mut acc = vec![0u8; 165];
        acc[0..32].copy_from_slice(&USDC_MINT.to_bytes());
        acc[32..64].copy_from_slice(&TREASURY.to_bytes());
        assert!(check_treasury_account(&acc).is_ok());
        let mut other_owner = acc.clone();
        other_owner[40] ^= 1;
        assert!(check_treasury_account(&other_owner).is_err());
        let mut other_mint = acc.clone();
        other_mint[3] ^= 1;
        assert!(check_treasury_account(&other_mint).is_err());
    }
}
