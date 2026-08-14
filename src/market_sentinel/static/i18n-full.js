/* Complete client-side localization for static UI and API-generated analysis text. */
(() => {
  const localeByLanguage = {pt: 'pt-BR', en: 'en-US', es: 'es-ES'};
  const phrases = {
    en: {
      'Sinais técnicos calculados em candles fechados. BTC como regime global, volume como confirmação e risco/retorno como filtro. Nenhuma ordem é executada.': 'Technical signals calculated from closed candles. BTC is used as the global regime, volume as confirmation, and risk/reward as a filter. No orders are executed.',
      'PODE ACONTECER — NÃO É ENTRADA.': 'MAY HAPPEN — NOT AN ENTRY.',
      'A probabilidade exibida é uma estimativa de prontidão técnica, não chance comprovada de lucro.': 'The displayed probability estimates technical readiness; it is not a proven chance of profit.',
      'Nenhuma varredura concluída.': 'No scan completed yet.', 'Use “Varrer agora” ou inicie o monitor.': 'Use “Scan now” or start the monitor.',
      'Aguardando a próxima varredura para montar cenários.': 'Waiting for the next scan to build scenarios.',
      'Os eventos de criação, alvos e stop aparecerão aqui.': 'Creation, target, and stop events will appear here.',
      'Nenhuma oportunidade nesta plataforma passou pelos filtros.': 'No opportunity on this venue passed the filters.',
      'Nenhum cenário corresponde à combinação atual de filtros.': 'No scenario matches the current filter combination.',
      'Contexto técnico ampliado disponível após a próxima varredura.': 'Expanded technical context will be available after the next scan.',
      'Informativo — não é recomendação financeira': 'For information only — not financial advice',
      'READ-ONLY SIGNAL INTELLIGENCE': 'READ-ONLY SIGNAL INTELLIGENCE', 'VIGILÂNCIA DE MERCADO,': 'MARKET SURVEILLANCE,', 'SEM RUÍDO.': 'WITHOUT NOISE.',
      'Iniciar monitor': 'Start monitor', 'Varrer agora': 'Scan now', 'Parar': 'Stop', 'Atualizar mercados': 'Refresh markets',
      'Mercados': 'Markets', 'Cripto': 'Crypto', 'Commodities': 'Commodities', 'Stocks EUA': 'US stocks',
      'Oportunidades qualificadas': 'Qualified opportunities', 'Console operacional': 'Operations console', 'AO VIVO': 'LIVE',
      'Cenários em preparação': 'Scenarios in preparation', 'Ciclo de vida das oportunidades': 'Opportunity lifecycle', 'AUDITORIA PERSISTENTE': 'PERSISTENT AUDIT',
      'Probabilidade mínima': 'Minimum probability', 'Qualquer %': 'Any %', 'R:R mínimo': 'Minimum R:R', 'Qualquer R:R': 'Any R:R',
      'Plataforma': 'Venue', 'Todas as plataformas': 'All venues', 'Todas': 'All', 'Tempo gráfico': 'Timeframe', 'Todos': 'All',
      '1 hora': '1 hour', '4 horas': '4 hours', 'Diário': 'Daily', 'Direção': 'Direction', 'Long e short': 'Long and short',
      'Ativas': 'Active', 'Concretizadas': 'Successful', 'Falhas': 'Failures', 'Taxa de concretização': 'Success rate',
      'ANÁLISE DA OPORTUNIDADE': 'OPPORTUNITY ANALYSIS', 'Composição da nota': 'Score breakdown', 'O que esperar para aceitar': 'What to wait for before accepting',
      'O que pode dar errado': 'What could go wrong', 'Por que o agente abriu': 'Why the agent opened it', 'Entrada': 'Entry', 'Alvos': 'Targets',
      'Aguardando eventos…': 'Waiting for events…', 'CARREGANDO ANÁLISE…': 'LOADING ANALYSIS…', 'CARREGANDO ANÁLISE...': 'LOADING ANALYSIS...',
      'ATUALIZADO AGORA': 'UPDATED NOW', 'VARRENDO AGORA': 'SCANNING NOW', 'INICIANDO MONITOR': 'STARTING MONITOR',
      'AGUARDANDO 1ª VARREDURA': 'WAITING FOR FIRST SCAN', 'EM ESPERA': 'IDLE', 'CONECTADO': 'CONNECTED', 'AINDA NÃO DEFINIDO': 'NOT CONFIGURED',
      'PODE ACONTECER': 'MAY HAPPEN', 'PREÇO ATUAL': 'CURRENT PRICE', 'CLIQUE PARA ABRIR O GRÁFICO': 'CLICK TO OPEN CHART',
      'Estimativa de prontidão técnica': 'Technical readiness estimate', 'GATILHO TOCADO': 'TRIGGER TOUCHED', 'AGUARDANDO FECHAMENTO': 'WAITING FOR CLOSE',
      'E DEMAIS FILTROS': 'AND OTHER FILTERS', 'AGUARDANDO O PREÇO TOCAR O GATILHO': 'WAITING FOR PRICE TO TOUCH THE TRIGGER',
      'Invalidação:': 'Invalidation:', 'Alvo projetado somente após confirmar:': 'Projected target only after confirmation:',
      'R:R POSSÍVEL': 'POSSIBLE R:R', 'estimativa antes da confirmação': 'estimate before confirmation', 'Leitura técnica ampliada': 'Expanded technical reading',
      'SINAIS': 'SIGNALS', 'CENÁRIOS': 'SCENARIOS', 'DE': 'OF', 'ENTRADA': 'ENTRY', 'ALVO': 'TARGET', 'STOP / INVALIDAÇÃO': 'STOP / INVALIDATION',
      'VOLUME': 'VOLUME', 'PREÇO': 'PRICE', 'candles fechados': 'closed candles', 'barras': 'bars', 'SCORE': 'SCORE',
      'CONFIRMADA': 'CONFIRMED', 'INVALIDADA': 'INVALIDATED', 'TARDIA — preço próximo do alvo': 'LATE — price near the target',
      'AGUARDANDO CONFIRMAÇÃO': 'WAITING FOR CONFIRMATION', 'Sinal anterior ao novo modelo': 'Signal created before the new model',
      'ABERTA': 'OPENED', 'REATIVADA': 'REACTIVATED', 'SUCESSO': 'SUCCESS',
      'Monitor iniciado': 'Monitor started', 'Monitor parado': 'Monitor stopped', 'Varredura concluída': 'Scan completed', 'Universo atualizado': 'Market universe updated',
      'Já existe uma varredura em andamento': 'A scan is already in progress', 'Oportunidade não encontrada': 'Opportunity not found',
      'Mercado não está mais disponível na venue': 'Market is no longer available on this venue',
      'Falha ao descobrir mercados em': 'Failed to discover markets on', 'mercados relevantes': 'relevant markets', 'Universo consolidado:': 'Consolidated universe:', 'Nenhum mercado BTC disponível para calcular o regime': 'No BTC market is available to calculate the regime', 'Radar ativo:': 'Active radar:', 'mercados': 'markets',
      'Falha ao enviar alerta ao Telegram; snapshot será preservado': 'Failed to send Telegram alert; snapshot will be preserved', 'Falha ao enviar resolução ao Telegram; snapshot será preservado': 'Failed to send Telegram resolution; snapshot will be preserved', 'Falha no ciclo de varredura': 'Scan cycle failed', 'Falha na varredura manual': 'Manual scan failed', 'Falha no ciclo automático': 'Automatic cycle failed', 'sem mercado': 'without market',
      'rompimento + reteste confirmado': 'confirmed breakout + retest', 'reteste de suporte': 'support retest', 'perda + reteste confirmado': 'confirmed breakdown + retest',
      'Estrutura': 'Structure', 'Tendência': 'Trend', 'Contexto BTC': 'BTC context', 'Risco/retorno': 'Risk/reward', 'Liquidez': 'Liquidity', 'Precisão da entrada': 'Entry precision',
      'Estrutura confirmada:': 'Confirmed structure:', 'Vibe-Trading confirmado:': 'Vibe-Trading confirmed:', 'histograma': 'histogram',
      'Tendência alinhada em 20/50/200 períodos': 'Trend aligned across 20/50/200 periods',
      'Sinal não está plenamente alinhado à tendência principal': 'Signal is not fully aligned with the main trend',
      'Contexto do BTC alinhado': 'BTC context is aligned', 'Contexto do BTC contrário ao sinal': 'BTC context opposes the signal',
      'Volume relativo ainda modesto:': 'Relative volume is still modest:', 'Volume relativo': 'Relative volume', 'Liquidez diária abaixo do filtro preferencial': 'Daily liquidity is below the preferred filter',
      'BTC em regime diário de alta': 'BTC in a bullish daily regime', 'BTC em regime diário defensivo/baixista': 'BTC in a defensive/bearish daily regime',
      'variação nos últimos 30 candles diários:': 'change over the last 30 daily candles:',
      'Preço acima das SMA 20/50/200; tendência compradora alinhada': 'Price above the 20/50/200 SMAs; bullish trend aligned',
      'Preço abaixo das SMA 20/50/200; tendência vendedora alinhada': 'Price below the 20/50/200 SMAs; bearish trend aligned',
      'Médias 20/50/200 sem alinhamento completo; mercado em transição': '20/50/200 averages are not fully aligned; market in transition',
      'RSI 14 em': 'RSI 14 at', 'ATR 14 em': 'ATR 14 at',
      'Volume atual em': 'Current volume at', 'a média de 20 candles': 'the 20-candle average', 'do preço': 'of price',
      'Suporte técnico mais próximo em': 'Nearest technical support at', 'Resistência técnica mais próxima em': 'Nearest technical resistance at',
      'Possível rompimento de resistência': 'Possible resistance breakout', 'Possível reação no suporte': 'Possible reaction at support', 'Possível perda de suporte': 'Possible support breakdown',
      'Fechamento acima de': 'Close above', 'Fechamento abaixo de': 'Close below', 'Volume do candle de confirmação': 'Confirmation candle volume',
      'Sustentar o nível rompido no reteste': 'Hold the broken level on the retest', 'Rejeição na resistência': 'Rejection at resistance',
      'Rompimento sem volume pode ser falso': 'A breakout without volume may be false', 'BTC enfraquecer antes da confirmação': 'BTC may weaken before confirmation',
      'Reação compradora e fechamento acima de': 'Bullish reaction and close above', 'Pavio de rejeição ou candle de força': 'Rejection wick or momentum candle',
      'Volume crescente na defesa': 'Increasing volume on the defense', 'Reteste do suporte perdido sem recuperação': 'Retest of lost support without recovery',
      'O nível pode não confirmar': 'The level may fail to confirm', 'Movimento antecipado aumenta o risco': 'An early move increases risk',
      'Mudança brusca no BTC invalida o contexto': 'A sharp BTC move invalidates the context',
      'Esperar fechamento de': 'Wait for a', 'acima da entrada': 'close above the entry', 'abaixo da entrada': 'close below the entry',
      'ou reteste com rejeição compradora.': 'or a retest with bullish rejection.', 'ou reteste com rejeição vendedora.': 'or a retest with bearish rejection.',
      'Preferir volume igual ou superior à média de 20 candles na confirmação.': 'Prefer confirmation volume at or above the 20-candle average.',
      'Não aceitar se o preço fechar abaixo de': 'Do not accept if price closes below', 'Não aceitar se o preço fechar acima de': 'Do not accept if price closes above',
      'essa é a invalidação estrutural.': 'this is the structural invalidation.', 'Evitar perseguir o preço quando mais de 80% do caminho até o primeiro alvo já foi percorrido.': 'Avoid chasing price after more than 80% of the path to the first target has already been covered.',
      'Rompimento sem volume pode ser falso e retornar rapidamente à faixa anterior.': 'A breakout without volume may be false and quickly return to the previous range.',
      'Slippage, spread e baixa liquidez podem piorar a entrada e o stop executável.': 'Slippage, spread, and low liquidity may worsen the executable entry and stop.',
      'Setup técnico identificado:': 'Technical setup identified:', 'Pontuação técnica de': 'Technical score of', 'no momento da abertura.': 'at the time it was opened.',
      'Oportunidade reativada; não há mais expiração por quantidade de candles': 'Opportunity reactivated; signals no longer expire after a candle count',
      'Auditoria histórica: movimento registrado atingiu o alvo': 'Historical audit: recorded move reached target', 'falha reclassificada como sucesso': 'failure reclassified as success',
      'Oportunidade registrada:': 'Opportunity recorded:', 'Bateu alvo': 'Reached target', 'lucro final': 'final profit',
      'alvo final': 'final target', 'alvos': 'targets', 'alvo': 'target',
      'sinal segue ativo até alvo final ou stop': 'signal remains active until the final target or stop', 'oportunidade considerada sucesso': 'opportunity counted as successful',
      'e depois atingiu o stop': 'and later hit the stop', 'Stop/invalidação atingido sem nenhum alvo alcançado': 'Stop/invalidation hit without reaching any target',
      'Auditoria:': 'Audit:', 'antes ou no mesmo candle do stop': 'before or in the same candle as the stop',
      'Idioma': 'Language', 'Filtrar por plataforma': 'Filter by venue', 'Gráfico técnico da oportunidade': 'Opportunity technical chart', 'Abrir gráfico e análise': 'Open chart and analysis'
    },
    es: {
      'Sinais técnicos calculados em candles fechados. BTC como regime global, volume como confirmação e risco/retorno como filtro. Nenhuma ordem é executada.': 'Señales técnicas calculadas con velas cerradas. BTC se usa como régimen global, el volumen como confirmación y el riesgo/beneficio como filtro. No se ejecutan órdenes.',
      'PODE ACONTECER — NÃO É ENTRADA.': 'PUEDE OCURRIR — NO ES UNA ENTRADA.', 'A probabilidade exibida é uma estimativa de prontidão técnica, não chance comprovada de lucro.': 'La probabilidad mostrada estima la preparación técnica; no es una probabilidad comprobada de beneficio.',
      'Nenhuma varredura concluída.': 'Aún no se completó ningún escaneo.', 'Use “Varrer agora” ou inicie o monitor.': 'Usa “Escanear ahora” o inicia el monitor.',
      'Aguardando a próxima varredura para montar cenários.': 'Esperando el próximo escaneo para crear escenarios.', 'Os eventos de criação, alvos e stop aparecerão aqui.': 'Los eventos de creación, objetivos y stop aparecerán aquí.',
      'Nenhuma oportunidade nesta plataforma passou pelos filtros.': 'Ninguna oportunidad de esta plataforma superó los filtros.', 'Nenhum cenário corresponde à combinação atual de filtros.': 'Ningún escenario coincide con la combinación actual de filtros.',
      'Contexto técnico ampliado disponível após a próxima varredura.': 'El contexto técnico ampliado estará disponible tras el próximo escaneo.', 'Informativo — não é recomendação financeira': 'Solo informativo — no es asesoramiento financiero',
      'READ-ONLY SIGNAL INTELLIGENCE': 'INTELIGENCIA DE SEÑALES DE SOLO LECTURA', 'VIGILÂNCIA DE MERCADO,': 'VIGILANCIA DE MERCADO,', 'SEM RUÍDO.': 'SIN RUIDO.',
      'Iniciar monitor': 'Iniciar monitor', 'Varrer agora': 'Escanear ahora', 'Parar': 'Detener', 'Atualizar mercados': 'Actualizar mercados', 'Mercados': 'Mercados', 'Cripto': 'Cripto', 'Stocks EUA': 'Acciones de EE. UU.',
      'Oportunidades qualificadas': 'Oportunidades calificadas', 'Console operacional': 'Consola operativa', 'AO VIVO': 'EN VIVO', 'Cenários em preparação': 'Escenarios en preparación',
      'Ciclo de vida das oportunidades': 'Ciclo de vida de oportunidades', 'AUDITORIA PERSISTENTE': 'AUDITORÍA PERSISTENTE', 'Probabilidade mínima': 'Probabilidad mínima', 'Qualquer %': 'Cualquier %',
      'R:R mínimo': 'R:R mínimo', 'Qualquer R:R': 'Cualquier R:R', 'Plataforma': 'Plataforma', 'Todas as plataformas': 'Todas las plataformas', 'Todas': 'Todas', 'Tempo gráfico': 'Temporalidad', 'Todos': 'Todos',
      '1 hora': '1 hora', '4 horas': '4 horas', 'Diário': 'Diario', 'Direção': 'Dirección', 'Long e short': 'Long y short', 'Ativas': 'Activas', 'Concretizadas': 'Concretadas', 'Falhas': 'Fallos', 'Taxa de concretização': 'Tasa de concreción',
      'ANÁLISE DA OPORTUNIDADE': 'ANÁLISIS DE LA OPORTUNIDAD', 'Composição da nota': 'Composición de la puntuación', 'O que esperar para aceitar': 'Qué esperar antes de aceptar', 'O que pode dar errado': 'Qué puede salir mal', 'Por que o agente abriu': 'Por qué lo abrió el agente',
      'Entrada': 'Entrada', 'Alvos': 'Objetivos', 'Aguardando eventos…': 'Esperando eventos…', 'CARREGANDO ANÁLISE…': 'CARGANDO ANÁLISIS…', 'CARREGANDO ANÁLISE...': 'CARGANDO ANÁLISIS...',
      'ATUALIZADO AGORA': 'ACTUALIZADO AHORA', 'VARRENDO AGORA': 'ESCANEANDO AHORA', 'INICIANDO MONITOR': 'INICIANDO MONITOR', 'AGUARDANDO 1ª VARREDURA': 'ESPERANDO EL PRIMER ESCANEO', 'EM ESPERA': 'EN ESPERA', 'CONECTADO': 'CONECTADO', 'AINDA NÃO DEFINIDO': 'NO CONFIGURADO',
      'PODE ACONTECER': 'PUEDE OCURRIR', 'PREÇO ATUAL': 'PRECIO ACTUAL', 'CLIQUE PARA ABRIR O GRÁFICO': 'HAZ CLIC PARA ABRIR EL GRÁFICO', 'Estimativa de prontidão técnica': 'Estimación de preparación técnica',
      'GATILHO TOCADO': 'DISPARADOR TOCADO', 'AGUARDANDO FECHAMENTO': 'ESPERANDO CIERRE', 'E DEMAIS FILTROS': 'Y LOS DEMÁS FILTROS', 'AGUARDANDO O PREÇO TOCAR O GATILHO': 'ESPERANDO QUE EL PRECIO TOQUE EL DISPARADOR',
      'Invalidação:': 'Invalidación:', 'Alvo projetado somente após confirmar:': 'Objetivo proyectado solo tras confirmar:', 'R:R POSSÍVEL': 'R:R POSIBLE', 'estimativa antes da confirmação': 'estimación antes de la confirmación', 'Leitura técnica ampliada': 'Lectura técnica ampliada',
      'SINAIS': 'SEÑALES', 'CENÁRIOS': 'ESCENARIOS', 'DE': 'DE', 'ENTRADA': 'ENTRADA', 'ALVO': 'OBJETIVO', 'STOP / INVALIDAÇÃO': 'STOP / INVALIDACIÓN', 'PREÇO': 'PRECIO', 'candles fechados': 'velas cerradas', 'barras': 'barras',
      'CONFIRMADA': 'CONFIRMADA', 'INVALIDADA': 'INVALIDADA', 'TARDIA — preço próximo do alvo': 'TARDÍA — precio cerca del objetivo', 'AGUARDANDO CONFIRMAÇÃO': 'ESPERANDO CONFIRMACIÓN', 'Sinal anterior ao novo modelo': 'Señal anterior al nuevo modelo',
      'ABERTA': 'ABIERTA', 'REATIVADA': 'REACTIVADA', 'SUCESSO': 'ÉXITO', 'Monitor iniciado': 'Monitor iniciado', 'Monitor parado': 'Monitor detenido', 'Varredura concluída': 'Escaneo completado', 'Universo atualizado': 'Universo de mercados actualizado',
      'Já existe uma varredura em andamento': 'Ya hay un escaneo en curso', 'Oportunidade não encontrada': 'Oportunidad no encontrada', 'Mercado não está mais disponível na venue': 'El mercado ya no está disponible en la plataforma',
      'Falha ao descobrir mercados em': 'Error al descubrir mercados en', 'mercados relevantes': 'mercados relevantes', 'Universo consolidado:': 'Universo consolidado:', 'Nenhum mercado BTC disponível para calcular o regime': 'No hay un mercado BTC disponible para calcular el régimen', 'Radar ativo:': 'Radar activo:', 'mercados': 'mercados',
      'Falha ao enviar alerta ao Telegram; snapshot será preservado': 'Error al enviar la alerta a Telegram; se conservará la instantánea', 'Falha ao enviar resolução ao Telegram; snapshot será preservado': 'Error al enviar la resolución a Telegram; se conservará la instantánea', 'Falha no ciclo de varredura': 'Error en el ciclo de escaneo', 'Falha na varredura manual': 'Error en el escaneo manual', 'Falha no ciclo automático': 'Error en el ciclo automático', 'sem mercado': 'sin mercado',
      'rompimento + reteste confirmado': 'ruptura + retesteo confirmado', 'reteste de suporte': 'retesteo de soporte', 'perda + reteste confirmado': 'pérdida + retesteo confirmado',
      'Estrutura': 'Estructura', 'Tendência': 'Tendencia', 'Contexto BTC': 'Contexto BTC', 'Risco/retorno': 'Riesgo/beneficio', 'Liquidez': 'Liquidez', 'Precisão da entrada': 'Precisión de entrada',
      'Estrutura confirmada:': 'Estructura confirmada:', 'Vibe-Trading confirmado:': 'Vibe-Trading confirmado:', 'histograma': 'histograma', 'Tendência alinhada em 20/50/200 períodos': 'Tendencia alineada en 20/50/200 períodos',
      'Sinal não está plenamente alinhado à tendência principal': 'La señal no está totalmente alineada con la tendencia principal', 'Contexto do BTC alinhado': 'Contexto de BTC alineado', 'Contexto do BTC contrário ao sinal': 'El contexto de BTC contradice la señal',
      'Volume relativo ainda modesto:': 'Volumen relativo todavía modesto:', 'Volume relativo': 'Volumen relativo', 'Liquidez diária abaixo do filtro preferencial': 'Liquidez diaria por debajo del filtro preferido',
      'BTC em regime diário de alta': 'BTC en régimen diario alcista', 'BTC em regime diário defensivo/baixista': 'BTC en régimen diario defensivo/bajista', 'variação nos últimos 30 candles diários:': 'variación en las últimas 30 velas diarias:',
      'Preço acima das SMA 20/50/200; tendência compradora alinhada': 'Precio por encima de las SMA 20/50/200; tendencia alcista alineada', 'Preço abaixo das SMA 20/50/200; tendência vendedora alinhada': 'Precio por debajo de las SMA 20/50/200; tendencia bajista alineada',
      'Médias 20/50/200 sem alinhamento completo; mercado em transição': 'Medias 20/50/200 sin alineación completa; mercado en transición', 'Volume atual em': 'Volumen actual en', 'a média de 20 candles': 'la media de 20 velas', 'do preço': 'del precio',
      'RSI 14 em': 'RSI 14 en', 'ATR 14 em': 'ATR 14 en',
      'Suporte técnico mais próximo em': 'Soporte técnico más cercano en', 'Resistência técnica mais próxima em': 'Resistencia técnica más cercana en', 'Possível rompimento de resistência': 'Posible ruptura de resistencia', 'Possível reação no suporte': 'Posible reacción en el soporte', 'Possível perda de suporte': 'Posible pérdida del soporte',
      'Fechamento acima de': 'Cierre por encima de', 'Fechamento abaixo de': 'Cierre por debajo de', 'Volume do candle de confirmação': 'Volumen de la vela de confirmación', 'Sustentar o nível rompido no reteste': 'Mantener el nivel roto en el retesteo', 'Rejeição na resistência': 'Rechazo en la resistencia',
      'Rompimento sem volume pode ser falso': 'Una ruptura sin volumen puede ser falsa', 'BTC enfraquecer antes da confirmação': 'BTC puede debilitarse antes de la confirmación', 'Reação compradora e fechamento acima de': 'Reacción alcista y cierre por encima de', 'Pavio de rejeição ou candle de força': 'Mecha de rechazo o vela de impulso',
      'Volume crescente na defesa': 'Volumen creciente en la defensa', 'Reteste do suporte perdido sem recuperação': 'Retesteo del soporte perdido sin recuperación', 'O nível pode não confirmar': 'El nivel puede no confirmarse', 'Movimento antecipado aumenta o risco': 'Un movimiento anticipado aumenta el riesgo', 'Mudança brusca no BTC invalida o contexto': 'Un movimiento brusco de BTC invalida el contexto',
      'Esperar fechamento de': 'Esperar un cierre de', 'acima da entrada': 'por encima de la entrada', 'abaixo da entrada': 'por debajo de la entrada', 'ou reteste com rejeição compradora.': 'o un retesteo con rechazo alcista.', 'ou reteste com rejeição vendedora.': 'o un retesteo con rechazo bajista.',
      'Preferir volume igual ou superior à média de 20 candles na confirmação.': 'Preferir un volumen igual o superior a la media de 20 velas en la confirmación.', 'Não aceitar se o preço fechar abaixo de': 'No aceptar si el precio cierra por debajo de', 'Não aceitar se o preço fechar acima de': 'No aceptar si el precio cierra por encima de',
      'essa é a invalidação estrutural.': 'esta es la invalidación estructural.', 'Evitar perseguir o preço quando mais de 80% do caminho até o primeiro alvo já foi percorrido.': 'Evitar perseguir el precio cuando ya se recorrió más del 80% del camino al primer objetivo.',
      'Rompimento sem volume pode ser falso e retornar rapidamente à faixa anterior.': 'Una ruptura sin volumen puede ser falsa y volver rápidamente al rango anterior.', 'Slippage, spread e baixa liquidez podem piorar a entrada e o stop executável.': 'El slippage, el spread y la baja liquidez pueden empeorar la entrada y el stop ejecutable.',
      'Setup técnico identificado:': 'Configuración técnica identificada:', 'Pontuação técnica de': 'Puntuación técnica de', 'no momento da abertura.': 'en el momento de apertura.',
      'Oportunidade reativada; não há mais expiração por quantidade de candles': 'Oportunidad reactivada; ya no hay expiración por cantidad de velas', 'Auditoria histórica: movimento registrado atingiu o alvo': 'Auditoría histórica: el movimiento registrado alcanzó el objetivo', 'falha reclassificada como sucesso': 'fallo reclasificado como éxito',
      'Oportunidade registrada:': 'Oportunidad registrada:', 'Bateu alvo': 'Alcanzó el objetivo', 'lucro final': 'beneficio final', 'sinal segue ativo até alvo final ou stop': 'la señal sigue activa hasta el objetivo final o el stop', 'oportunidade considerada sucesso': 'oportunidad contabilizada como éxito',
      'alvo final': 'objetivo final', 'alvos': 'objetivos', 'alvo': 'objetivo',
      'e depois atingiu o stop': 'y después alcanzó el stop', 'Stop/invalidação atingido sem nenhum alvo alcançado': 'Stop/invalidación alcanzado sin llegar a ningún objetivo', 'Auditoria:': 'Auditoría:', 'antes ou no mesmo candle do stop': 'antes o en la misma vela del stop',
      'Idioma': 'Idioma', 'Filtrar por plataforma': 'Filtrar por plataforma', 'Gráfico técnico da oportunidade': 'Gráfico técnico de la oportunidad', 'Abrir gráfico e análise': 'Abrir gráfico y análisis'
    }
  };

  const sourceAttributes = new WeakMap();
  const replacePhrases = (source, language = currentLanguage) => {
    if (language === 'pt' || !source) return source;
    const age = source.match(/^ATUALIZADO HÁ (\d+) MIN$/);
    if (age) return language === 'en' ? `UPDATED ${age[1]} MIN AGO` : `ACTUALIZADO HACE ${age[1]} MIN`;
    const late = source.match(/^ATRASADO · (\d+) MIN$/);
    if (late) return language === 'en' ? `DELAYED · ${late[1]} MIN` : `RETRASADO · ${late[1]} MIN`;
    return Object.entries(phrases[language] || {}).sort((a, b) => b[0].length - a[0].length)
      .reduce((value, [from, to]) => value.split(from).join(to), source);
  };

  translateValue = replacePhrases;

  const translateAttributes = (root = document) => {
    root.querySelectorAll('[title],[aria-label]').forEach(element => {
      const remembered = sourceAttributes.get(element) || {};
      ['title', 'aria-label'].forEach(attribute => {
        if (!element.hasAttribute(attribute)) return;
        if (!remembered[attribute]) remembered[attribute] = element.getAttribute(attribute);
        element.setAttribute(attribute, replacePhrases(remembered[attribute]));
      });
      sourceAttributes.set(element, remembered);
    });
  };

  const baseSetLanguage = setLanguage;
  setLanguage = language => {
    baseSetLanguage(language);
    translateAttributes();
  };

  new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
    if (node.nodeType === Node.ELEMENT_NODE) translateAttributes(node);
  }))).observe(document.body, {childList: true, subtree: true});

  setLanguage(currentLanguage);
})();
