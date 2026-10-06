# Áudio local da Rodada 7.1

## Fonte de verdade

Os únicos arquivos de reprodução são os MP3 já fornecidos em
`apps/frontend/public/audio/`. O cliente não faz download, busca externa ou
síntese de áudio.

- `animals/`: `A_bear`, `A_bull`, `A_camel`, `A_cat`, `A_crowned-crane`,
  `A_deer`, `A_eagle`, `A_elephant`, `A_goat`, `A_gorilla`, `A-hilsa`,
  `A_horse`, `A_japonese-macaque`, `A_kangaroo`, `A_komodo-dragon`, `A_lion`,
  `A_llama`, `A_macaw`, `A_octopus`, `A_otter`, `A_panda`, `A_pinguin`,
  `A_rooster`, `A_shark`, `A_tiger`, `A_zebra` e `A_zumbie` (todos `.mp3`).
- `effects/`: `countdown_beep.mp3`, `heart_break.mp3`, `champion.mp3` e
  `podium.mp3`.
- `background/`: `background.mp3`.

`AUDIO_ASSETS` em `src/app/audio-manager.mjs` contém o mapeamento explícito
entre o identificador canônico do mascote e o nome local real. O arquivo não é
renomeado nem duplicado.

## Comportamento

`AudioManager` utiliza elementos `HTMLAudioElement` em canais exclusivos:

- `animal`: uma seleção/vitória substitui a reprodução anterior;
- `effect`: um efeito substitui o anterior;
- `background`: uma única faixa em loop;
- TTS é separado, usando Web Speech somente para nome localizado + nome
  científico.

Com efeitos desligados, os canais de animal e efeito não tocam. Música continua
independente. A música só é configurada na Arena e usa volume conservador.
Ao trocar de tela, resetar execução ou desmontar a página, os canais são
interrompidos.

Uma pessoa com `second_chance` usa `A_zumbie.mp3` para a entrada da Segunda
Chance e para vitórias subsequentes. O `animal_id` canônico não é alterado.
`resetRun()` encerra a reprodução e preserva os controles; por isso uma nova
execução volta a usar o MP3 normal até uma nova Segunda Chance oficial.

## Timeline

O frontend permanece uma camada de apresentação dos eventos oficiais. A fila
não produz decisões competitivas. Efeitos são limitados a:

- `round_resolved`: `countdown_beep.mp3` em 3, 2 e 1;
- `heart_lost`: `heart_break.mp3`;
- `match_completed`: MP3 do vencedor (ou Zumbi);
- `champion`: `champion.mp3`, seguido do estágio visual e sonoro de pódio com
  `podium.mp3`.

Eliminação é deliberadamente visual e não tem asset nem chamada de áudio.
Embora `podium_decided` possa chegar antes de `champion` no log oficial, a fila
apresenta o pódio somente após o estágio de campeão e substitui o canal de
efeitos, evitando sobreposição.

## Limites de validação

Testes unitários simulam o navegador e validam mapeamento, exclusividade de
canais, Zumbi, vencedor, controles independentes, TTS, contagem, timeline e
deduplicação. A integração local verifica HTTP 200 para todos os 32 MP3.
Qualidade/volume audível e a voz disponível dependem do dispositivo do usuário
e devem ser ouvidos no navegador antes de uma publicação pública.
