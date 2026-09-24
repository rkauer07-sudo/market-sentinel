/* Market Sentinel — client-side localization (pt → en / es).
 *
 * Every visible text node, option, SVG label, tooltip and placeholder keeps its
 * original Portuguese source and is re-translated whenever the language changes
 * or the page renders new content. Lookup order:
 *   1. EXACT   — whole string (trimmed) matches;
 *   2. PATTERNS — anchored regexes for dynamic strings (numbers, symbols, dates);
 *   3. PHRASES — word-boundary-safe fragment replacement for API-generated text.
 * Fragments never replace pieces of other words (the old "DE" → "OF" bug that
 * turned "COMUNIDADE" into "COMUNIDAOF").
 */
(() => {
  const LOCALES = {pt: 'pt-BR', en: 'en-US', es: 'es-ES'};
  const IDX = {en: 0, es: 1};

  // ---------------------------------------------------------------- exact
  const EXACT = {
    // Header / hero / metrics
    'READ-ONLY SIGNAL INTELLIGENCE': ['READ-ONLY SIGNAL INTELLIGENCE', 'INTELIGENCIA DE SEÑALES DE SOLO LECTURA'],
    'VIGILÂNCIA DE MERCADO,': ['MARKET SURVEILLANCE,', 'VIGILANCIA DE MERCADO,'],
    'SEM RUÍDO.': ['WITHOUT NOISE.', 'SIN RUIDO.'],
    'Melhor agente do mercado web3. Analisa 24h as melhores oportunidades com o que tem de mais efetivo no mercado pra você não perder nada. Cada oportunidade selecionada é exibida detalhada. Nenhuma ordem é executada.': [
      'The best agent in the web3 market. It scans the best opportunities 24/7 with the most effective tools available, so you never miss a thing. Every selected opportunity is shown in full detail. No orders are executed.',
      'El mejor agente del mercado web3. Analiza las 24 h las mejores oportunidades con lo más efectivo del mercado para que no te pierdas nada. Cada oportunidad seleccionada se muestra en detalle. No se ejecuta ninguna orden.'],
    'Conectar carteira': ['Connect wallet', 'Conectar billetera'],
    'Idioma': ['Language', 'Idioma'],
    'Mercados': ['Markets', 'Mercados'], 'Cripto': ['Crypto', 'Cripto'], 'Commodities': ['Commodities', 'Materias primas'],
    'Stocks EUA': ['US stocks', 'Acciones EE. UU.'], 'Índices': ['Indices', 'Índices'], 'Telegram': ['Telegram', 'Telegram'],
    'CONECTADO': ['CONNECTED', 'CONECTADO'], 'NÃO CONFIGURADO': ['NOT CONFIGURED', 'NO CONFIGURADO'],
    'AINDA NÃO DEFINIDO': ['NOT CONFIGURED YET', 'AÚN NO CONFIGURADO'],
    'ATUALIZADO AGORA': ['UPDATED NOW', 'ACTUALIZADO AHORA'], 'VARRENDO AGORA': ['SCANNING NOW', 'ESCANEANDO AHORA'],
    'INICIANDO MONITOR': ['STARTING MONITOR', 'INICIANDO MONITOR'], 'EM ESPERA': ['STANDBY', 'EN ESPERA'],
    'AGUARDANDO 1ª VARREDURA': ['WAITING FOR 1ST SCAN', 'ESPERANDO 1.ER ESCANEO'], 'API OFFLINE': ['API OFFLINE', 'API SIN CONEXIÓN'],
    'OFFLINE': ['OFFLINE', 'SIN CONEXIÓN'],
    // Navigation
    'Navegação principal': ['Main navigation', 'Navegación principal'],
    'COMMAND CENTER': ['COMMAND CENTER', 'CENTRO DE MANDO'],
    'Radar ao vivo': ['Live radar', 'Radar en vivo'], 'Radar': ['Radar', 'Radar'], 'Cenários': ['Scenarios', 'Escenarios'],
    'Desempenho': ['Performance', 'Rendimiento'], 'Histórico': ['History', 'Historial'], 'Chat Web3': ['Web3 chat', 'Chat Web3'],
    'Chat': ['Chat', 'Chat'], 'Sistema e logs': ['System & logs', 'Sistema y registros'], 'Sistema': ['System', 'Sistema'],
    'em breve': ['soon', 'pronto'], 'EM BREVE': ['COMING SOON', 'PRÓXIMAMENTE'],
    'Memecoins Analyser: estamos finalizando o módulo de lançamentos e carteiras da Solana.': [
      'Memecoins Analyser: we are finishing the Solana launches and wallets module.',
      'Memecoins Analyser: estamos terminando el módulo de lanzamientos y billeteras de Solana.'],
    // Opportunities panel
    'Oportunidades qualificadas': ['Qualified opportunities', 'Oportunidades calificadas'],
    'Todas as plataformas': ['All venues', 'Todas las plataformas'], 'Filtrar por plataforma': ['Filter by venue', 'Filtrar por plataforma'],
    'Aguardando a próxima varredura automática.': ['Waiting for the next automatic scan.', 'Esperando el próximo escaneo automático.'],
    'Nenhuma oportunidade passou pelos filtros agora.': ['No opportunity passed the filters right now.', 'Ninguna oportunidad pasó los filtros ahora.'],
    'O radar continua acompanhando o mercado.': ['The radar keeps watching the market.', 'El radar sigue vigilando el mercado.'],
    'Oportunidade qualificada aberta agora': ['Qualified opportunity open right now', 'Oportunidad calificada abierta ahora'],
    'Oportunidades qualificadas abertas agora': ['Qualified opportunities open right now', 'Oportunidades calificadas abiertas ahora'],
    'Ativo, direção, entrada, stop estrutural, alvos Fibonacci e o gráfico completo ficam visíveis somente para membros VIP.': [
      'Asset, direction, entry, structural stop, Fibonacci targets and the full chart are visible to VIP members only.',
      'Activo, dirección, entrada, stop estructural, objetivos Fibonacci y el gráfico completo solo son visibles para miembros VIP.'],
    'Pagamento único em USDC na rede Solana. Sem renovação automática.': [
      'One-time payment in USDC on the Solana network. No automatic renewal.',
      'Pago único en USDC en la red Solana. Sin renovación automática.'],
    'Preço agora': ['Price now', 'Precio ahora'], 'Entrada': ['Entry', 'Entrada'], 'Invalidação': ['Invalidation', 'Invalidación'],
    'Primeiro alvo': ['First target', 'Primer objetivo'], 'Abrir leitura completa →': ['Open full reading →', 'Abrir lectura completa →'],
    'Abrir gráfico e análise completa': ['Open chart and full analysis', 'Abrir gráfico y análisis completo'],
    // Operations console
    'Console operacional': ['Operations console', 'Consola operativa'], 'AO VIVO': ['LIVE', 'EN VIVO'],
    'Aguardando eventos…': ['Waiting for events…', 'Esperando eventos…'], 'AGORA': ['NOW', 'AHORA'],
    'Aguardando o primeiro ciclo operacional.': ['Waiting for the first operating cycle.', 'Esperando el primer ciclo operativo.'],
    // Scenarios
    'Cenários em preparação': ['Scenarios in preparation', 'Escenarios en preparación'],
    'PODE ACONTECER — NÃO É ENTRADA.': ['MAY HAPPEN — NOT AN ENTRY.', 'PUEDE OCURRIR — NO ES ENTRADA.'],
    'A probabilidade exibida é uma estimativa de prontidão técnica, não chance comprovada de lucro.': [
      'The displayed probability estimates technical readiness; it is not a proven chance of profit.',
      'La probabilidad mostrada estima la preparación técnica; no es una probabilidad comprobada de ganancia.'],
    'AINDA NÃO É ENTRADA.': ['NOT AN ENTRY YET.', 'AÚN NO ES ENTRADA.'],
    'A porcentagem mostra prontidão técnica, não chance garantida de lucro.': [
      'The percentage shows technical readiness, not a guaranteed chance of profit.',
      'El porcentaje muestra preparación técnica, no una probabilidad garantizada de ganancia.'],
    'APRENDIZADO · AGUARDANDO HISTÓRICO': ['LEARNING · WAITING FOR HISTORY', 'APRENDIZAJE · ESPERANDO HISTORIAL'],
    'APRENDIZADO · INDISPONÍVEL': ['LEARNING · UNAVAILABLE', 'APRENDIZAJE · NO DISPONIBLE'],
    'APRENDIZADO · MODELO MANTIDO · SEM EVIDÊNCIA NOVA': ['LEARNING · MODEL KEPT · NO NEW EVIDENCE', 'APRENDIZAJE · MODELO MANTENIDO · SIN EVIDENCIA NUEVA'],
    'Probabilidade mínima': ['Minimum probability', 'Probabilidad mínima'], 'Qualquer %': ['Any %', 'Cualquier %'],
    'R:R mínimo': ['Minimum R:R', 'R:R mínimo'], 'Qualquer R:R': ['Any R:R', 'Cualquier R:R'],
    'Plataforma': ['Venue', 'Plataforma'], 'Todas': ['All', 'Todas'], 'Tempo gráfico': ['Timeframe', 'Temporalidad'],
    'Todos': ['All', 'Todos'], '1 hora': ['1 hour', '1 hora'], '4 horas': ['4 hours', '4 horas'], 'Diário': ['Daily', 'Diario'],
    'Direção': ['Direction', 'Dirección'], 'Long e short': ['Long and short', 'Long y short'],
    'Aguardando a próxima varredura para montar cenários.': ['Waiting for the next scan to build scenarios.', 'Esperando el próximo escaneo para armar escenarios.'],
    'Nenhum cenário corresponde aos filtros.': ['No scenario matches the filters.', 'Ningún escenario coincide con los filtros.'],
    'Isso também é uma leitura: não há motivo para antecipar.': ['That is also a reading: there is no reason to jump ahead.', 'Eso también es una lectura: no hay motivo para anticiparse.'],
    'EM OBSERVAÇÃO': ['WATCHING', 'EN OBSERVACIÓN'], 'PRONTIDÃO': ['READINESS', 'PREPARACIÓN'],
    'Em poucas palavras': ['In a nutshell', 'En pocas palabras'], 'Gatilho': ['Trigger', 'Disparador'],
    'Alvo projetado': ['Projected target', 'Objetivo proyectado'], 'O que esperar': ['What to wait for', 'Qué esperar'],
    'Quando descartar': ['When to discard', 'Cuándo descartar'],
    'Ver leitura técnica ampliada': ['See expanded technical reading', 'Ver lectura técnica ampliada'],
    'Leitura técnica ampliada': ['Expanded technical reading', 'Lectura técnica ampliada'],
    'A leitura avançada chega na próxima varredura.': ['The advanced reading arrives with the next scan.', 'La lectura avanzada llega en el próximo escaneo.'],
    'AGUARDANDO O PREÇO TOCAR O GATILHO': ['WAITING FOR PRICE TO TOUCH THE TRIGGER', 'ESPERANDO QUE EL PRECIO TOQUE EL DISPARADOR'],
    'O preço está encostando numa barreira importante.': ['Price is pressing against an important barrier.', 'El precio está tocando una barrera importante.'],
    'O suporte está sendo pressionado, mas ainda pode segurar.': ['Support is under pressure but may still hold.', 'El soporte está bajo presión, pero aún puede aguantar.'],
    'O preço está perto de uma região onde compradores podem reagir.': ['Price is near an area where buyers may react.', 'El precio está cerca de una zona donde los compradores pueden reaccionar.'],
    'Perto da confirmação, mas ainda não confirmado.': ['Close to confirmation, but not confirmed yet.', 'Cerca de la confirmación, pero aún no confirmado.'],
    'Em formação; faltam sinais objetivos.': ['Forming; objective signals still missing.', 'En formación; faltan señales objetivas.'],
    'Inicial; apenas para acompanhamento.': ['Early; for monitoring only.', 'Inicial; solo para seguimiento.'],
    'O cenário ainda precisa confirmar o gatilho antes de virar oportunidade.': ['The scenario still needs to confirm the trigger before becoming an opportunity.', 'El escenario aún debe confirmar el disparador antes de convertirse en oportunidad.'],
    'Em observação.': ['Under observation.', 'En observación.'], 'Aguardar confirmação.': ['Wait for confirmation.', 'Esperar confirmación.'],
    'Não antecipar a entrada.': ['Do not enter early.', 'No anticipar la entrada.'],
    'Sustentar o nível rompido no reteste': ['Hold the broken level on the retest', 'Sostener el nivel roto en el retesteo'],
    'Rejeição na resistência': ['Rejection at resistance', 'Rechazo en la resistencia'],
    'Rompimento sem volume pode ser falso': ['A breakout without volume may be false', 'Una ruptura sin volumen puede ser falsa'],
    'BTC enfraquecer antes da confirmação': ['BTC weakening before confirmation', 'BTC debilitándose antes de la confirmación'],
    'Pavio de rejeição ou candle de força': ['Rejection wick or strong candle', 'Mecha de rechazo o vela de fuerza'],
    'Volume crescente na defesa': ['Rising volume on the defense', 'Volumen creciente en la defensa'],
    'Volume do candle de confirmação ≥ 1,5x da média': ['Confirmation candle volume ≥ 1.5x the average', 'Volumen de la vela de confirmación ≥ 1,5x el promedio'],
    'Volume ≥ 1,5x da média': ['Volume ≥ 1.5x the average', 'Volumen ≥ 1,5x el promedio'],
    'Reteste do suporte perdido sem recuperação': ['Retest of the lost support without recovery', 'Retesteo del soporte perdido sin recuperación'],
    'O nível pode não confirmar': ['The level may not confirm', 'El nivel puede no confirmarse'],
    'Movimento antecipado aumenta o risco': ['Entering early increases risk', 'Anticiparse aumenta el riesgo'],
    'Mudança brusca no BTC invalida o contexto da cripto': ['A sharp BTC move invalidates the crypto context', 'Un movimiento brusco de BTC invalida el contexto de la cripto'],
    'Preço acima das SMA 20/50/200; tendência compradora alinhada': ['Price above the 20/50/200 SMAs; bullish trend aligned', 'Precio sobre las SMA 20/50/200; tendencia alcista alineada'],
    'Preço abaixo das SMA 20/50/200; tendência vendedora alinhada': ['Price below the 20/50/200 SMAs; bearish trend aligned', 'Precio bajo las SMA 20/50/200; tendencia bajista alineada'],
    'Médias 20/50/200 sem alinhamento completo; mercado em transição': ['20/50/200 averages not fully aligned; market in transition', 'Medias 20/50/200 sin alineación completa; mercado en transición'],
    'BTC em regime diário de alta': ['BTC in a bullish daily regime', 'BTC en régimen diario alcista'],
    'BTC em regime diário defensivo/baixista': ['BTC in a defensive/bearish daily regime', 'BTC en régimen diario defensivo/bajista'],
    // Lifecycle
    'Ciclo de vida das oportunidades': ['Opportunity lifecycle', 'Ciclo de vida de las oportunidades'],
    'AUDITORIA PERSISTENTE': ['PERSISTENT AUDIT', 'AUDITORÍA PERSISTENTE'], 'Ativas': ['Active', 'Activas'],
    'Concretizadas': ['Successful', 'Concretadas'], 'Falhas': ['Failures', 'Fallos'],
    'Taxa de concretização': ['Success rate', 'Tasa de éxito'],
    'Os eventos de criação, alvos e stop aparecerão aqui.': ['Creation, target and stop events will appear here.', 'Los eventos de creación, objetivos y stop aparecerán aquí.'],
    'ABERTA': ['OPENED', 'ABIERTA'], 'REATIVADA': ['REACTIVATED', 'REACTIVADA'], 'STOP': ['STOP', 'STOP'],
    'PREÇO AO VIVO': ['LIVE PRICE', 'PRECIO EN VIVO'],
    'Contabilizado em tempo real · persistência central em até 2min30s': ['Counted in real time · central persistence within 2min30s', 'Contabilizado en tiempo real · persistencia central en hasta 2min30s'],
    'Oportunidade qualificada exclusiva para membros VIP': ['Qualified opportunity exclusive to VIP members', 'Oportunidad calificada exclusiva para miembros VIP'],
    'Stop/invalidação atingido sem nenhum alvo alcançado': ['Stop/invalidation hit without reaching any target', 'Stop/invalidación alcanzado sin llegar a ningún objetivo'],
    // Community / chat
    'COMUNIDADE · WEB3': ['COMMUNITY · WEB3', 'COMUNIDAD · WEB3'],
    'Converse com quem está lendo o mesmo mercado.': ['Talk with people reading the same market.', 'Conversa con quien está leyendo el mismo mercado.'],
    'O acesso usa uma assinatura de mensagem. Nenhuma transação é criada e a aplicação nunca solicita sua chave privada.': [
      'Access uses a message signature. No transaction is created and the app never asks for your private key.',
      'El acceso usa una firma de mensaje. No se crea ninguna transacción y la aplicación nunca solicita tu clave privada.'],
    'IDENTIDADE ATUAL': ['CURRENT IDENTITY', 'IDENTIDAD ACTUAL'], 'NÃO CONECTADA': ['NOT CONNECTED', 'NO CONECTADA'],
    'Chat dos usuários': ['Users chat', 'Chat de usuarios'], 'LOGIN NECESSÁRIO': ['LOGIN REQUIRED', 'INICIO DE SESIÓN NECESARIO'],
    'CONECTADO · ATUALIZAÇÃO AO VIVO': ['CONNECTED · LIVE UPDATES', 'CONECTADO · ACTUALIZACIÓN EN VIVO'],
    'CHAT INDISPONÍVEL': ['CHAT UNAVAILABLE', 'CHAT NO DISPONIBLE'],
    'Entre com sua carteira Solana': ['Sign in with your Solana wallet', 'Entra con tu billetera Solana'],
    'Assine uma mensagem gratuita para provar que a carteira é sua e liberar o chat.': [
      'Sign a free message to prove the wallet is yours and unlock the chat.',
      'Firma un mensaje gratuito para demostrar que la billetera es tuya y desbloquear el chat.'],
    'Enviar': ['Send', 'Enviar'], 'Mensagem': ['Message', 'Mensaje'],
    'Compartilhe uma leitura do mercado…': ['Share a market reading…', 'Comparte una lectura del mercado…'],
    'VIP ATIVO': ['VIP ACTIVE', 'VIP ACTIVO'],
    // Footer
    'Informativo — não é recomendação financeira': ['For information only — not financial advice', 'Informativo — no es asesoramiento financiero'],
    // Chart modal
    'ANÁLISE DA OPORTUNIDADE': ['OPPORTUNITY ANALYSIS', 'ANÁLISIS DE LA OPORTUNIDAD'],
    'CARREGANDO ANÁLISE…': ['LOADING ANALYSIS…', 'CARGANDO ANÁLISIS…'],
    'Gráfico técnico da oportunidade': ['Opportunity technical chart', 'Gráfico técnico de la oportunidad'],
    'Alvos': ['Targets', 'Objetivos'], 'Stop': ['Stop', 'Stop'],
    'Composição da nota': ['Score breakdown', 'Composición de la puntuación'],
    'O que esperar para aceitar': ['What to wait for before accepting', 'Qué esperar antes de aceptar'],
    'O que pode dar errado': ['What could go wrong', 'Qué puede salir mal'],
    'Por que o agente abriu': ['Why the agent opened it', 'Por qué la abrió el agente'],
    'Sinal anterior ao novo modelo': ['Signal predates the new model', 'Señal anterior al nuevo modelo'],
    'ENTRADA': ['ENTRY', 'ENTRADA'], 'STOP / INVALIDAÇÃO': ['STOP / INVALIDATION', 'STOP / INVALIDACIÓN'],
    'Preferir volume igual ou superior à média de 20 candles na confirmação.': [
      'Prefer confirmation volume at or above the 20-candle average.',
      'Preferir volumen igual o superior al promedio de 20 velas en la confirmación.'],
    'Evitar perseguir o preço quando mais de 80% do caminho até o primeiro alvo já foi percorrido.': [
      'Avoid chasing price once more than 80% of the way to the first target is done.',
      'Evitar perseguir el precio cuando ya se recorrió más del 80% del camino al primer objetivo.'],
    'Rompimento sem volume pode ser falso e retornar rapidamente à faixa anterior.': [
      'A breakout without volume may be false and quickly return to the previous range.',
      'Una ruptura sin volumen puede ser falsa y volver rápidamente al rango anterior.'],
    'Slippage, spread e baixa liquidez podem piorar a entrada e o stop executável.': [
      'Slippage, spread and low liquidity can worsen the entry and the executable stop.',
      'El slippage, el spread y la baja liquidez pueden empeorar la entrada y el stop ejecutable.'],
    'Mudança no regime diário do BTC pode invalidar o contexto desta cripto.': [
      'A change in the BTC daily regime can invalidate this crypto’s context.',
      'Un cambio en el régimen diario de BTC puede invalidar el contexto de esta cripto.'],
    'Tendência alinhada em 20/50/200 períodos': ['Trend aligned on 20/50/200 periods', 'Tendencia alineada en 20/50/200 períodos'],
    'Regime diário do BTC alinhado à direção da cripto': ['BTC daily regime aligned with the crypto direction', 'Régimen diario de BTC alineado con la dirección de la cripto'],
    'Regime diário do BTC contrário à direção da cripto': ['BTC daily regime against the crypto direction', 'Régimen diario de BTC contrario a la dirección de la cripto'],
    'Sinal não está plenamente alinhado à tendência principal': ['Signal is not fully aligned with the main trend', 'La señal no está totalmente alineada con la tendencia principal'],
    'Liquidez diária abaixo do filtro preferencial': ['Daily liquidity below the preferred filter', 'Liquidez diaria por debajo del filtro preferido'],
    'Rompimento sem volume pode ser falso e retornar rapidamente à faixa anterior': ['A breakout without volume may be false and quickly return to the previous range', 'Una ruptura sin volumen puede ser falsa y volver rápidamente al rango anterior'],
    // Score breakdown keys
    'Estrutura': ['Structure', 'Estructura'], 'Tendência': ['Trend', 'Tendencia'], 'Volume': ['Volume', 'Volumen'],
    'Regime diário do BTC': ['BTC daily regime', 'Régimen diario de BTC'], 'Estrutura do próprio ativo': ['Asset’s own structure', 'Estructura del propio activo'],
    'Risco/retorno': ['Risk/reward', 'Riesgo/beneficio'], 'Liquidez': ['Liquidity', 'Liquidez'],
    'Precisão da entrada': ['Entry precision', 'Precisión de la entrada'], 'Vibe-Trading': ['Vibe-Trading', 'Vibe-Trading'],
    // VIP
    'Acesso VIP': ['VIP access', 'Acceso VIP'], 'Fechar': ['Close', 'Cerrar'],
    'OPORTUNIDADES QUALIFICADAS · PAGAMENTO EM USDC NA SOLANA': ['QUALIFIED OPPORTUNITIES · PAYMENT IN USDC ON SOLANA', 'OPORTUNIDADES CALIFICADAS · PAGO EN USDC EN SOLANA'],
    'Todas as oportunidades qualificadas abertas, em tempo real': ['Every open qualified opportunity, in real time', 'Todas las oportunidades calificadas abiertas, en tiempo real'],
    'Entrada, stop estrutural abaixo do suporte e 5 alvos Fibonacci': ['Entry, structural stop below support and 5 Fibonacci targets', 'Entrada, stop estructural bajo el soporte y 5 objetivos Fibonacci'],
    'Gráfico completo com a leitura do agente': ['Full chart with the agent’s reading', 'Gráfico completo con la lectura del agente'],
    'Primeiro entre com sua carteira (assinatura gratuita, sem transação). O VIP fica vinculado a essa identidade. Depois, pague os USDC com a mesma carteira ou qualquer outra carteira Solana.': [
      'First sign in with your wallet (free signature, no transaction). VIP is tied to that identity. Then pay the USDC from the same wallet or any other Solana wallet.',
      'Primero entra con tu billetera (firma gratuita, sin transacción). El VIP queda vinculado a esa identidad. Luego paga los USDC con la misma billetera o cualquier otra billetera Solana.'],
    'Gerar pagamento': ['Create payment', 'Generar pago'],
    'GERANDO PEDIDO DE PAGAMENTO…': ['CREATING PAYMENT REQUEST…', 'GENERANDO SOLICITUD DE PAGO…'],
    'Pagamentos VIP ainda não foram ativados neste servidor.': ['VIP payments are not enabled on this server yet.', 'Los pagos VIP aún no están activados en este servidor.'],
    'A variável VIP_TREASURY_WALLET não chegou ao servidor (ausente ou sem redeploy).': ['The VIP_TREASURY_WALLET variable did not reach the server (missing or not redeployed).', 'La variable VIP_TREASURY_WALLET no llegó al servidor (ausente o sin redeploy).'],
    'VIP_TREASURY_WALLET contém um endereço EVM (0x…); use um endereço Solana.': ['VIP_TREASURY_WALLET holds an EVM address (0x…); use a Solana address.', 'VIP_TREASURY_WALLET contiene una dirección EVM (0x…); usa una dirección Solana.'],
    'VIP_TREASURY_WALLET não é um endereço Solana válido.': ['VIP_TREASURY_WALLET is not a valid Solana address.', 'VIP_TREASURY_WALLET no es una dirección Solana válida.'],
    'Envie exatamente': ['Send exactly', 'Envía exactamente'], 'na rede': ['on the', 'en la red'],
    '. O VIP é liberado automaticamente assim que a transação confirmar (geralmente em segundos).': [
      ' network. VIP unlocks automatically as soon as the transaction confirms (usually within seconds).',
      '. El VIP se libera automáticamente en cuanto la transacción se confirme (normalmente en segundos).'],
    'Carteira de destino (USDC · Solana)': ['Destination wallet (USDC · Solana)', 'Billetera de destino (USDC · Solana)'],
    'Memo do pedido': ['Order memo', 'Memo del pedido'], 'Copiar': ['Copy', 'Copiar'], 'Copiado': ['Copied', 'Copiado'],
    'Pagar com Phantom / Solflare': ['Pay with Phantom / Solflare', 'Pagar con Phantom / Solflare'],
    'Abrir no app da carteira': ['Open in wallet app', 'Abrir en la app de la billetera'],
    'AGUARDANDO PAGAMENTO…': ['WAITING FOR PAYMENT…', 'ESPERANDO EL PAGO…'],
    'Paguei de outra forma — verificar pela assinatura da transação': ['I paid another way — verify by transaction signature', 'Pagué de otra forma — verificar por la firma de la transacción'],
    'Assinatura (hash) da transação': ['Transaction signature (hash)', 'Firma (hash) de la transacción'],
    'Verificar': ['Verify', 'Verificar'], 'QR indisponível': ['QR unavailable', 'QR no disponible'],
    'PREPARANDO TRANSAÇÃO…': ['PREPARING TRANSACTION…', 'PREPARANDO TRANSACCIÓN…'],
    'CONFIRME NA SUA CARTEIRA…': ['CONFIRM IN YOUR WALLET…', 'CONFIRMA EN TU BILLETERA…'],
    'TRANSAÇÃO ENVIADA · AGUARDANDO CONFIRMAÇÃO…': ['TRANSACTION SENT · WAITING FOR CONFIRMATION…', 'TRANSACCIÓN ENVIADA · ESPERANDO CONFIRMACIÓN…'],
    'PAGAMENTO CONFIRMADO · VIP LIBERADO': ['PAYMENT CONFIRMED · VIP UNLOCKED', 'PAGO CONFIRMADO · VIP LIBERADO'],
    'Ainda não detectamos o pagamento. Se já pagou, verifique pela assinatura abaixo.': ['We have not detected the payment yet. If you already paid, verify with the signature below.', 'Aún no detectamos el pago. Si ya pagaste, verifica con la firma de abajo.'],
    'Pagamento cancelado': ['Payment cancelled', 'Pago cancelado'],
    'Pagamento ainda não detectado na rede': ['Payment not detected on the network yet', 'Pago aún no detectado en la red'],
    'Transação ainda não encontrada/confirmada': ['Transaction not found/confirmed yet', 'Transacción aún no encontrada/confirmada'],
    'A transação falhou na rede Solana': ['The transaction failed on the Solana network', 'La transacción falló en la red Solana'],
    'A transação não contém a referência/memo deste pagamento': ['The transaction does not contain this payment’s reference/memo', 'La transacción no contiene la referencia/memo de este pago'],
    'A transação é anterior a este pedido de pagamento': ['The transaction predates this payment request', 'La transacción es anterior a esta solicitud de pago'],
    'Esta transação já foi utilizada para liberar um VIP': ['This transaction was already used to unlock a VIP', 'Esta transacción ya se usó para liberar un VIP'],
    'Pedido expirado; gere um novo pagamento': ['Request expired; create a new payment', 'Solicitud vencida; genera un nuevo pago'],
    'Assinatura de transação inválida': ['Invalid transaction signature', 'Firma de transacción inválida'],
    'Não foi possível gerar o pagamento': ['Could not create the payment', 'No fue posible generar el pago'],
    'Pedido de pagamento não encontrado para esta carteira': ['Payment request not found for this wallet', 'Solicitud de pago no encontrada para esta billetera'],
    'VIP liberado. Bons trades!': ['VIP unlocked. Good trades!', 'VIP liberado. ¡Buenos trades!'],
    // Wallet / toasts / API errors
    'Carteira conectada com segurança': ['Wallet connected securely', 'Billetera conectada de forma segura'],
    'Sessão encerrada': ['Signed out', 'Sesión cerrada'],
    'Carteira alterada. Conecte novamente para assinar com a nova conta.': ['Wallet changed. Connect again to sign with the new account.', 'Billetera cambiada. Conéctate de nuevo para firmar con la nueva cuenta.'],
    'Instale uma carteira Solana, como Phantom, Solflare ou Backpack.': ['Install a Solana wallet such as Phantom, Solflare or Backpack.', 'Instala una billetera Solana, como Phantom, Solflare o Backpack.'],
    'Nenhuma carteira Solana encontrada. Use o QR code ou instale Phantom/Solflare.': ['No Solana wallet found. Use the QR code or install Phantom/Solflare.', 'No se encontró ninguna billetera Solana. Usa el código QR o instala Phantom/Solflare.'],
    'Não foi possível conectar a carteira': ['Could not connect the wallet', 'No fue posible conectar la billetera'],
    'Nenhuma carteira selecionada': ['No wallet selected', 'Ninguna billetera seleccionada'],
    'Conecte e assine com sua carteira para acessar o chat': ['Connect and sign with your wallet to access the chat', 'Conecta y firma con tu billetera para acceder al chat'],
    'Desafio expirado ou já utilizado': ['Challenge expired or already used', 'Desafío vencido o ya utilizado'],
    'A assinatura não corresponde à carteira informada': ['The signature does not match the given wallet', 'La firma no corresponde a la billetera informada'],
    'Endereço de carteira Solana inválido': ['Invalid Solana wallet address', 'Dirección de billetera Solana inválida'],
    'Aguarde dois segundos antes de enviar outra mensagem': ['Wait two seconds before sending another message', 'Espera dos segundos antes de enviar otro mensaje'],
    'A mensagem deve ter entre 1 e 500 caracteres': ['The message must be 1 to 500 characters long', 'El mensaje debe tener entre 1 y 500 caracteres'],
    'Sessão não corresponde a um usuário ativo': ['Session does not match an active user', 'La sesión no corresponde a un usuario activo'],
    'Mercado não está mais disponível na venue': ['Market is no longer available on this venue', 'El mercado ya no está disponible en la plataforma'],
    'Oportunidade não encontrada': ['Opportunity not found', 'Oportunidad no encontrada'],
  };

  // ------------------------------------------------------------- patterns
  const P = (re, en, es) => ({re, t: [en, es]});
  const num = '([-+]?[\\d.,]+(?:e[-+]?\\d+)?)';
  const PATTERNS = [
    P(new RegExp(`^ATUALIZADO HÁ (\\d+) MIN$`), 'UPDATED $1 MIN AGO', 'ACTUALIZADO HACE $1 MIN'),
    P(/^ATRASADO · (\d+) MIN$/, 'DELAYED · $1 MIN', 'RETRASADO · $1 MIN'),
    P(/^CICLO OK · (\d+)$/, 'CYCLE OK · $1', 'CICLO OK · $1'),
    P(/^PARCIAL · (\d+) FALHAS$/, 'PARTIAL · $1 FAILURES', 'PARCIAL · $1 FALLOS'),
    P(/^1 SINAL$/, '1 SIGNAL', '1 SEÑAL'),
    P(/^(\d+) SINAIS$/, '$1 SIGNALS', '$1 SEÑALES'),
    P(/^(\d+) ABERTA · VIP$/, '$1 OPEN · VIP', '$1 ABIERTA · VIP'),
    P(/^(\d+) ABERTAS · VIP$/, '$1 OPEN · VIP', '$1 ABIERTAS · VIP'),
    P(/^(\d+) DE (\d+) CENÁRIOS$/, '$1 OF $2 SCENARIOS', '$1 DE $2 ESCENARIOS'),
    P(/^histórico ([+-]?\d+)$/, 'history $1', 'historial $1'),
    P(/^Liberar VIP · (\S+) USDC \/ (\d+) dias$/, 'Unlock VIP · $1 USDC / $2 days', 'Liberar VIP · $1 USDC / $2 días'),
    P(/^\/ (\d+) DIAS · REDE SOLANA$/, '/ $1 DAYS · SOLANA NETWORK', '/ $1 DÍAS · RED SOLANA'),
    P(/^Renovar por mais (\d+) dias$/, 'Renew for $1 more days', 'Renovar por $1 días más'),
    P(/^VIP ATIVO ATÉ (.+)\. Um novo pagamento soma mais (\d+) dias\.$/, 'VIP ACTIVE UNTIL $1. A new payment adds $2 more days.', 'VIP ACTIVO HASTA $1. Un nuevo pago suma $2 días más.'),
    P(/^VIP ATIVO ATÉ (.+)$/, 'VIP ACTIVE UNTIL $1', 'VIP ACTIVO HASTA $1'),
    P(/^PLANO FREE · VIP POR (\S+) USDC \/ (\d+) DIAS$/, 'FREE PLAN · VIP FOR $1 USDC / $2 DAYS', 'PLAN FREE · VIP POR $1 USDC / $2 DÍAS'),
    P(/^APRENDIZADO · (\d+)\/(\d+) RESULTADOS$/, 'LEARNING · $1/$2 RESULTS', 'APRENDIZAJE · $1/$2 RESULTADOS'),
    P(/^APRENDIZADO · (\d+) PERFIS VALIDADOS · WALK-FORWARD$/, 'LEARNING · $1 VALIDATED PROFILES · WALK-FORWARD', 'APRENDIZAJE · $1 PERFILES VALIDADOS · WALK-FORWARD'),
    P(/^AGUARDANDO CONFIRMAÇÃO · R:R POSSÍVEL (\S+)$/, 'WAITING FOR CONFIRMATION · POSSIBLE R:R $1', 'ESPERANDO CONFIRMACIÓN · R:R POSIBLE $1'),
    P(/^GATILHO TOCADO · AGUARDANDO FECHAMENTO (\S+) E DEMAIS FILTROS$/, 'TRIGGER TOUCHED · WAITING FOR THE $1 CLOSE AND OTHER FILTERS', 'DISPARADOR TOCADO · ESPERANDO EL CIERRE DE $1 Y DEMÁS FILTROS'),
    P(/^SUCESSO T(\d)$/, 'SUCCESS T$1', 'ÉXITO T$1'),
    P(/^ALVO (\d)$/, 'TARGET $1', 'OBJETIVO $1'),
    P(/^ALVO (\d) FIB$/, 'TARGET $1 FIB', 'OBJETIVO $1 FIB'),
    P(new RegExp(`^ENTRADA ${num}$`), 'ENTRY $1', 'ENTRADA $1'),
    P(new RegExp(`^STOP / INVALIDAÇÃO ${num}$`), 'STOP / INVALIDATION $1', 'STOP / INVALIDACIÓN $1'),
    P(new RegExp(`^ALVO (\\d) FIB ${num}$`), 'TARGET $1 FIB $2', 'OBJETIVO $1 FIB $2'),
    P(/^VOLUME · candles fechados · (\d+) barras$/, 'VOLUME · closed candles · $1 bars', 'VOLUMEN · velas cerradas · $1 barras'),
    P(/^(.+) · (LONG|SHORT) · SCORE (\d+)$/, '$1 · $2 · SCORE $3', '$1 · $2 · PUNTUACIÓN $3'),
    P(/^(CONFIRMADA|INVALIDADA|AGUARDANDO CONFIRMAÇÃO|TARDIA — preço próximo do alvo) · PREÇO (\S+) · VOLUME (\S+)$/,
      (m, l) => `${tr(m[1], l)} · ${l === 'en' ? 'PRICE' : 'PRECIO'} ${m[2]} · ${l === 'en' ? 'VOLUME' : 'VOLUMEN'} ${m[3]}`),
    P(/^CONFIRMADA$/, 'CONFIRMED', 'CONFIRMADA'), P(/^INVALIDADA$/, 'INVALIDATED', 'INVALIDADA'),
    P(/^AGUARDANDO CONFIRMAÇÃO$/, 'WAITING FOR CONFIRMATION', 'ESPERANDO CONFIRMACIÓN'),
    P(/^TARDIA — preço próximo do alvo$/, 'LATE — price near the target', 'TARDÍA — precio cerca del objetivo'),
    // Candidate conditions / context
    P(new RegExp(`^Fechamento acima de ${num}$`), 'Close above $1', 'Cierre por encima de $1'),
    P(new RegExp(`^Fechamento abaixo de ${num}$`), 'Close below $1', 'Cierre por debajo de $1'),
    P(new RegExp(`^Reação compradora e fechamento acima de ${num}$`), 'Buyer reaction and close above $1', 'Reacción compradora y cierre por encima de $1'),
    P(/^BTC em regime diário (de alta|defensivo\/baixista); variação em 30 candles diários: (\S+)$/,
      (m, l) => `${tr('BTC em regime diário ' + m[1], l)}; ${l === 'en' ? 'change over 30 daily candles' : 'variación en 30 velas diarias'}: ${m[2]}`),
    P(new RegExp(`^RSI 14 em ${num}$`), 'RSI 14 at $1', 'RSI 14 en $1'),
    P(/^Volume atual em (\S+) a média de 20 candles$/, 'Current volume at $1 the 20-candle average', 'Volumen actual en $1 el promedio de 20 velas'),
    P(/^ATR 14 em (\S+) \((\S+) do preço\)$/, 'ATR 14 at $1 ($2 of price)', 'ATR 14 en $1 ($2 del precio)'),
    P(new RegExp(`^Suporte técnico mais próximo em ${num}$`), 'Nearest technical support at $1', 'Soporte técnico más cercano en $1'),
    P(new RegExp(`^Resistência técnica mais próxima em ${num}$`), 'Nearest technical resistance at $1', 'Resistencia técnica más cercana en $1'),
    // Plain-language explanations (explanations.py)
    P(new RegExp(`^Ainda não houve rompimento\\. O cenário só ganha força se o candle de (\\S*) fechar acima de ${num} com participação de volume\\.$`),
      'No breakout yet. The scenario only gains strength if the $1 candle closes above $2 with volume participation.',
      'Aún no hubo ruptura. El escenario solo gana fuerza si la vela de $1 cierra por encima de $2 con participación de volumen.'),
    P(new RegExp(`^Espere o fechamento acima de ${num}; tocar o nível não basta\\.$`),
      'Wait for a close above $1; touching the level is not enough.', 'Espera el cierre por encima de $1; tocar el nivel no basta.'),
    P(new RegExp(`^A ideia é de queda somente se o candle de (\\S*) perder ${num} e não recuperar o nível no reteste\\.$`),
      'The idea is bearish only if the $1 candle loses $2 and does not reclaim the level on the retest.',
      'La idea es bajista solo si la vela de $1 pierde $2 y no recupera el nivel en el retesteo.'),
    P(new RegExp(`^Confirme a perda de ${num} antes de considerar o movimento\\.$`),
      'Confirm the loss of $1 before considering the move.', 'Confirma la pérdida de $1 antes de considerar el movimiento.'),
    P(new RegExp(`^A reação ainda não aconteceu\\. Ela fica mais clara se o candle de (\\S*) defender a região e fechar acima de ${num}\\.$`),
      'The reaction has not happened yet. It becomes clearer if the $1 candle defends the area and closes above $2.',
      'La reacción aún no ocurrió. Se vuelve más clara si la vela de $1 defiende la zona y cierra por encima de $2.'),
    P(new RegExp(`^Procure defesa do nível e fechamento acima de ${num}\\.$`),
      'Look for a defense of the level and a close above $1.', 'Busca la defensa del nivel y un cierre por encima de $1.'),
    P(new RegExp(`^Descarte a leitura se o preço fechar (abaixo|acima) de ${num}\\. O alvo de ${num} só vale depois da confirmação\\.$`),
      (m, l) => l === 'en'
        ? `Discard the reading if price closes ${m[1] === 'abaixo' ? 'below' : 'above'} ${m[2]}. The ${m[3]} target only counts after confirmation.`
        : `Descarta la lectura si el precio cierra ${m[1] === 'abaixo' ? 'por debajo' : 'por encima'} de ${m[2]}. El objetivo de ${m[3]} solo vale tras la confirmación.`),
    // Chart acceptance / fallback reasons (web.py)
    P(new RegExp(`^Esperar fechamento de (\\S+) (acima|abaixo) da entrada ${num} ou reteste com rejeição (compradora|vendedora)\\.$`),
      (m, l) => l === 'en'
        ? `Wait for a ${m[1]} close ${m[2] === 'acima' ? 'above' : 'below'} the ${m[3]} entry or a retest with ${m[4] === 'compradora' ? 'bullish' : 'bearish'} rejection.`
        : `Esperar un cierre de ${m[1]} ${m[2] === 'acima' ? 'por encima' : 'por debajo'} de la entrada ${m[3]} o un retesteo con rechazo ${m[4] === 'compradora' ? 'comprador' : 'vendedor'}.`),
    P(new RegExp(`^Não aceitar se o preço fechar (abaixo|acima) de ${num}; essa é a invalidação estrutural\\.$`),
      (m, l) => l === 'en'
        ? `Do not accept if price closes ${m[1] === 'abaixo' ? 'below' : 'above'} ${m[2]}; that is the structural invalidation.`
        : `No aceptar si el precio cierra ${m[1] === 'abaixo' ? 'por debajo' : 'por encima'} de ${m[2]}; esa es la invalidación estructural.`),
    P(/^Setup técnico identificado: (.+)\.$/, (m, l) => (l === 'en' ? 'Technical setup identified: ' : 'Setup técnico identificado: ') + tr(m[1], l) + '.'),
    P(/^Risco\/retorno projetado de (\S+)\.$/, 'Projected risk/reward of $1.', 'Riesgo/beneficio proyectado de $1.'),
    P(/^Pontuação técnica de (\d+)\/100 no momento da abertura\.$/, 'Technical score of $1/100 at opening.', 'Puntuación técnica de $1/100 al abrir.'),
    P(/^Setup (.+) confirmado em candle fechado\.$/, (m, l) => (l === 'en' ? `${tr(m[1], l)} setup confirmed on a closed candle.` : `Setup ${tr(m[1], l)} confirmado en vela cerrada.`)),
    // Signal reasons (analysis.py)
    P(/^Estrutura confirmada: (.+)$/, (m, l) => (l === 'en' ? 'Confirmed structure: ' : 'Estructura confirmada: ') + tr(m[1], l)),
    P(/^Vibe-Trading confirmado: RSI (\S+), MACD histograma (\S+), EMA20 (\S+)$/, 'Vibe-Trading confirmed: RSI $1, MACD histogram $2, EMA20 $3', 'Vibe-Trading confirmado: RSI $1, histograma MACD $2, EMA20 $3'),
    P(/^Stop estrutural (abaixo do suporte|acima da resistência) (\S+) \((\d+) defesa\(s\)\), além do pavio mais profundo (\S+) — folga para caça de stops \((\S+) ATR\)$/,
      (m, l) => l === 'en'
        ? `Structural stop ${m[1].startsWith('abaixo') ? 'below support' : 'above resistance'} ${m[2]} (${m[3]} defense(s)), beyond the deepest wick ${m[4]} — room for stop hunts (${m[5]} ATR)`
        : `Stop estructural ${m[1].startsWith('abaixo') ? 'bajo el soporte' : 'sobre la resistencia'} ${m[2]} (${m[3]} defensa(s)), más allá de la mecha más profunda ${m[4]} — margen para cacerías de stops (${m[5]} ATR)`),
    P(/^Volume relativo (\S+)$/, 'Relative volume $1', 'Volumen relativo $1'),
    P(/^Volume relativo ainda modesto: (\S+)$/, 'Relative volume still modest: $1', 'Volumen relativo aún modesto: $1'),
    P(/^(\w+)=(.+): (\S+)% em (\d+) resultados$/, '$1=$2: $3% over $4 results', '$1=$2: $3% en $4 resultados'),
    // Lifecycle events (storage.py)
    P(/^Oportunidade registrada: (.+?); (.+)$/, (m, l) => (l === 'en' ? 'Opportunity recorded: ' : 'Oportunidad registrada: ') + tr(m[1], l) + '; ' +
      m[2].replace(/alvo (\d)/g, l === 'en' ? 'target $1' : 'objetivo $1')),
    P(/^Bateu alvo (\d); sinal segue ativo até alvo final ou stop$/, 'Hit target $1; signal stays active until the final target or stop', 'Alcanzó el objetivo $1; la señal sigue activa hasta el objetivo final o el stop'),
    P(/^Bateu alvo (\d) \(lucro final\); oportunidade considerada sucesso$/, 'Hit target $1 (final profit); opportunity counted as a success', 'Alcanzó el objetivo $1 (ganancia final); oportunidad considerada éxito'),
    P(/^Bateu alvo (\d) e depois atingiu o stop; oportunidade considerada sucesso$/, 'Hit target $1 and then the stop; opportunity counted as a success', 'Alcanzó el objetivo $1 y luego el stop; oportunidad considerada éxito'),
    P(/^Auditoria: bateu alvo (\d) antes ou no mesmo candle do stop; falha reclassificada como sucesso$/, 'Audit: hit target $1 before or on the same candle as the stop; failure reclassified as success', 'Auditoría: alcanzó el objetivo $1 antes o en la misma vela del stop; fallo reclasificado como éxito'),
    P(/^Auditoria histórica: movimento registrado atingiu o alvo (\d); falha reclassificada como sucesso$/, 'Historical audit: recorded move reached target $1; failure reclassified as success', 'Auditoría histórica: el movimiento registrado alcanzó el objetivo $1; fallo reclasificado como éxito'),
    // Operational logs (app.py)
    P(/^Varredura concluída: (\d+) mercados, (\d+) sinais, (\d+) cenários, (\d+) falhas$/, 'Scan completed: $1 markets, $2 signals, $3 scenarios, $4 failures', 'Escaneo completado: $1 mercados, $2 señales, $3 escenarios, $4 fallos'),
    P(/^Falha ao descobrir mercados em (\S+): (.+)$/, 'Failed to discover markets on $1: $2', 'Fallo al descubrir mercados en $1: $2'),
    P(/^Mercados atualizados: (\d+) ativos em (\d+) plataformas$/, 'Markets updated: $1 assets on $2 venues', 'Mercados actualizados: $1 activos en $2 plataformas'),
    P(/^Aprendizado diário (\S+): (\d+) resultados, (\S+)% de acerto, (\d+) perfis validados$/, 'Daily learning $1: $2 results, $3% hit rate, $4 validated profiles', 'Aprendizaje diario $1: $2 resultados, $3% de acierto, $4 perfiles validados'),
    P(/^Diagnóstico dos filtros: (.+)$/, 'Filter diagnostics: $1', 'Diagnóstico de filtros: $1'),
    P(/^Falhas por plataforma: (.+)$/, 'Failures by venue: $1', 'Fallos por plataforma: $1'),
    P(/^OPORTUNIDADE ENCERRADA (\S+) (\S+): (.+)$/, (m, l) => `${l === 'en' ? 'OPPORTUNITY CLOSED' : 'OPORTUNIDAD CERRADA'} ${m[1]} ${m[2]}: ${tr(m[3], l)}`),
    P(/^AUDITORIA (CORRIGIDA|MANTIDA|sem mercado) (.+)$/, (m, l) => `${l === 'en' ? 'AUDIT' : 'AUDITORÍA'} ${{CORRIGIDA: l === 'en' ? 'FIXED' : 'CORREGIDA', MANTIDA: l === 'en' ? 'KEPT' : 'MANTENIDA', 'sem mercado': l === 'en' ? 'without market' : 'sin mercado'}[m[1]]} ${m[2]}`),
    P(/^Market Sentinel iniciado \(Telegram: (configurado|desativado)\)$/, (m, l) => `Market Sentinel ${l === 'en' ? 'started' : 'iniciado'} (Telegram: ${m[1] === 'configurado' ? (l === 'en' ? 'configured' : 'configurado') : (l === 'en' ? 'disabled' : 'desactivado')})`),
    // VIP dynamic
    P(/^Transferências manuais precisam incluir o memo (\S+)\. Saques de corretoras sem memo não são reconhecidos automaticamente\.$/,
      'Manual transfers must include the memo $1. Exchange withdrawals without a memo are not recognized automatically.',
      'Las transferencias manuales deben incluir el memo $1. Los retiros de exchanges sin memo no se reconocen automáticamente.'),
    P(/^QR e link seguem o padrão Solana Pay \((.+)\)\. Pedido válido até (.+)\. Não é recomendação financeira\.$/,
      'The QR and link follow the Solana Pay standard ($1). Request valid until $2. Not financial advice.',
      'El QR y el enlace siguen el estándar Solana Pay ($1). Solicitud válida hasta $2. No es asesoramiento financiero.'),
    P(/^Valor recebido menor que (\S+) USDC na carteira do projeto$/, 'Amount received is below $1 USDC in the project wallet', 'Monto recibido menor que $1 USDC en la billetera del proyecto'),
    P(/^(.+) · (.+) confirmado ao vivo$/, (m, l) => `${m[1]} · ${tr(m[2], l)} ${l === 'en' ? 'confirmed live' : 'confirmado en vivo'}`),
  ];

  // --------------------------------------------------------------- phrases
  // Fragments inside longer API text (setups, venues' notes). Word-bounded.
  const PHRASES = {
    'rompimento + reteste confirmado': ['breakout + confirmed retest', 'ruptura + retesteo confirmado'],
    'perda + reteste confirmado': ['breakdown + confirmed retest', 'pérdida + retesteo confirmado'],
    'pullback de continuação (alta)': ['continuation pullback (bullish)', 'pullback de continuación (alcista)'],
    'pullback de continuação (baixa)': ['continuation pullback (bearish)', 'pullback de continuación (bajista)'],
    'Possível rompimento de resistência': ['Possible resistance breakout', 'Posible ruptura de resistencia'],
    'Possível reação no suporte': ['Possible reaction at support', 'Posible reacción en el soporte'],
    'Possível perda de suporte': ['Possible support breakdown', 'Posible pérdida de soporte'],
    'Cenário técnico em formação': ['Technical scenario forming', 'Escenario técnico en formación'],
  };

  // ---------------------------------------------------------------- engine
  const cache = {en: new Map(), es: new Map()};
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const phraseList = Object.entries(PHRASES).sort((a, b) => b[0].length - a[0].length)
    .map(([pt, t]) => [new RegExp(`(?<![\\p{L}\\p{N}])${esc(pt)}(?![\\p{L}\\p{N}])`, 'gu'), t]);

  function tr(source, lang = currentLanguage) {
    if (lang === 'pt' || !source || !(lang in IDX)) return source;
    const hit = cache[lang].get(source);
    if (hit !== undefined) return hit;
    let out = null;
    const exact = EXACT[source];
    if (exact) out = exact[IDX[lang]];
    if (out == null) {
      for (const {re, t} of PATTERNS) {
        const m = source.match(re);
        if (!m) continue;
        const tpl = t[IDX[lang]];
        out = typeof t[0] === 'function' ? t[0](m, lang)
          : typeof tpl === 'function' ? tpl(m, lang) : source.replace(re, tpl);
        break;
      }
    }
    if (out == null) {
      out = source;
      for (const [re, t] of phraseList) out = out.replace(re, t[IDX[lang]]);
    }
    if (cache[lang].size > 5000) cache[lang].clear();
    cache[lang].set(source, out);
    return out;
  }
  window.msTranslate = tr;
  window.uiLocale = () => LOCALES[currentLanguage] || 'pt-BR';

  // The page's own translateDOM() calls translateValue() for every text node.
  translateValue = source => tr(source);

  const ATTRS = ['title', 'aria-label', 'placeholder'];
  const attrSources = new WeakMap();
  const translateAttributes = (root = document) => {
    const nodes = root.querySelectorAll ? root.querySelectorAll('[title],[aria-label],[placeholder]') : [];
    [root, ...nodes].forEach(el => {
      if (!el.getAttribute) return;
      const remembered = attrSources.get(el) || {};
      ATTRS.forEach(attr => {
        if (!el.hasAttribute(attr)) return;
        const current = el.getAttribute(attr);
        const known = remembered[attr];
        // Adopt new source text when page code changed the attribute itself.
        if (!known || (current !== known.source && current !== known.shown)) remembered[attr] = {source: current};
        const shown = tr(remembered[attr].source);
        remembered[attr].shown = shown;
        if (current !== shown) el.setAttribute(attr, shown);
      });
      attrSources.set(el, remembered);
    });
  };

  const baseSetLanguage = setLanguage;
  setLanguage = language => {
    baseSetLanguage(language);
    translateAttributes();
    // Re-render dynamic sections so dates/numbers follow the new locale.
    try {
      opsSignature = candidateSignature = lifecycleSignature = logsSignature = '';
      if (typeof refreshDashboard === 'function') refreshDashboard();
      if (typeof renderWallet === 'function') renderWallet();
    } catch (_) { /* first paint: globals not ready yet */ }
  };

  new MutationObserver(records => records.forEach(record => {
    if (record.type === 'attributes') { translateAttributes(record.target); return; }
    record.addedNodes.forEach(node => { if (node.nodeType === Node.ELEMENT_NODE) translateAttributes(node); });
  })).observe(document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ATTRS});

  // Text nodes changed in place (nodeValue) are not "added": catch them too.
  new MutationObserver(records => records.forEach(record => {
    const node = record.target;
    if (node.nodeType === Node.TEXT_NODE && node.parentNode) translateDOM(node.parentNode);
  })).observe(document.body, {characterData: true, subtree: true});

  setLanguage(currentLanguage);
})();
