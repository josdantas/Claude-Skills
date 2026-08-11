# ARCA — Semana 1: resultados dos spikes de risco

**Data de execução:** 10 de agosto de 2026
**Referência:** [`arca-plano-de-implementacao.md`](./arca-plano-de-implementacao.md) §13
**Regra da semana 1:** nenhuma tarefa de produção começa antes destas três respostas.

## Ambiente de medição — leia antes dos números

| Item | Valor |
|---|---|
| Máquina | Container Linux, 4 vCPU x86_64, 15 GB RAM, disco virtual |
| Python | 3.11.15 (o plano especifica 3.12; sem impacto nestas medições) |
| Bibliotecas | `cryptography` 50.0.0, `lancedb` 0.37.1, `argon2-cffi`, `numpy` |

**Isto não é o hardware de referência do plano** (MacBook Air M2 / Ryzen 7 7840U). Os números abaixo são indicativos, não os oficiais do contrato. O que sustenta os vereditos é a **ordem de grandeza das margens** — 26 ms contra um limiar de 1.500 ms, 0,27 s contra um limiar de 10 s. Nenhuma diferença plausível de hardware inverte conclusões com essa folga. As medições oficiais nas duas máquinas de referência ficam pendentes.

---

## S1 — A cifra por registro inviabiliza a busca vetorial?

**Critério:** 10k registros, p95 do recall completo. `p95 > 1,5 s` → plano B (índice inteiro em volume SQLCipher).

Código: [`bench/spikes/s1_recall_latency.py`](../bench/spikes/s1_recall_latency.py) — 10.000 registros, 768 dims, top-k 30, 200 consultas.

| Braço | Mediana | p95 | p99 |
|---|---|---|---|
| **A** baseline, corpo em claro | 21,2 ms | 136,5 ms | 298,1 ms |
| **B** envelope por registro | 23,6 ms | **26,0 ms** | 141,6 ms |
| └ só o decrypt do top-30 | 0,3 ms | 0,5 ms | 0,6 ms |

Cifrar os 10.000 registros na ingestão: **0,08 s** (8 µs por registro).

**Braço C (perfil `hardened`)** — shard de vetores de 30,7 MB: cifrar 440 ms, decifrar **272 ms** a 113 MB/s. Custo único no início da sessão, não por consulta.

### Veredito: **PASSA**, com margem de ~58×

A sobrecarga mediana da cifra por registro é **+2,4 ms**, e o decrypt do top-30 custa **0,3 ms** — três ordens de grandeza abaixo do orçamento de 800 ms do produto. O gargalo do recall é a busca ANN em si (~21 ms), não a criptografia.

**Consequência para o plano:** o plano B (índice inteiro em SQLCipher) **sai do registro de riscos**. Ele existia para o caso de a cifra granular ser cara; ela não é. Manter a granularidade por registro é gratuito e preserva a propriedade que importa — cada registro tem sua própria DEK, então comprometer um não compromete os outros.

**Ressalva honesta:** o p95 do braço A ficou *acima* do braço B (136 ms contra 26 ms). Isso é artefato de cold start — o braço A rodou primeiro e absorveu o aquecimento do índice. Não é a criptografia deixando a busca mais rápida. O número a levar é a mediana, onde a comparação é limpa: 21,2 contra 23,6 ms.

---

## S2 — O embedding local é bom o bastante?

**Critério:** comparar EmbeddingGemma-300M local contra `text-embedding-3-small` no LongMemEval. Queda de recall@10 > 8 pontos → avaliar `gte-large` ou embedding remoto opt-in.

### Veredito: **BLOQUEADO — não executado**

`huggingface.co` é negado pela política de rede deste ambiente (403 no CONNECT, confirmado no status do proxy). Sem pesos de modelo não há braço local, e sem acesso à API de embedding não há baseline. Não há como produzir um número aqui, e não vou estimar um: S2 é exatamente a pergunta cuja resposta não se adivinha.

**Desbloqueio — duas opções:**
1. Liberar `huggingface.co` na política de rede do ambiente (feito em claude.ai/code, nas configurações do ambiente) e eu rodo o spike aqui.
2. Rodar o spike numa máquina local com os pesos já baixados; o harness fica pronto para isso.

**Impacto na programação:** S2 é pré-requisito da Fase 1 (semanas 3–5), não da Fase 0. A fundação pode começar sem ele, mas **S2 precisa fechar antes da semana 3**, ou a escolha do modelo de embedding vira decisão por chute.

---

## S3 — O rebuild de shard é rápido o bastante para ser o padrão da deleção?

**Critério:** shard de 5k registros. `rebuild > 10 s` → reduzir o tamanho do shard.

Código: [`bench/spikes/s3_shard_rebuild.py`](../bench/spikes/s3_shard_rebuild.py) — vault real em disco (5.000 arquivos Markdown, 26 MB), índice descartado e refeito por completo a partir dos arquivos.

| Execução | Leitura + decrypt | Insert + índice | Total |
|---|---|---|---|
| #1 (cache frio) | 0,27 s | 0,68 s | 0,95 s |
| #2 | 0,19 s | 0,21 s | 0,40 s |
| #3 | 0,19 s | 0,08 s | **0,27 s** |

**Cenário real de deleção** — apagar 100 registros e refazer o shard inteiro: **0,26 s**.

### Veredito: **PASSA**, com margem de ~37×

Deleção verdadeira custa **um quarto de segundo**. Isso confirma a decisão central do desenho: não existe motivo para soft-delete ou tombstone no ARCA, que é justamente onde a categoria inteira falha (*Ghost Vectors*). O caminho correto também é o caminho barato.

**Consequências para o plano:**

1. **O sharding pode ser bem mais grosso.** A extrapolação linear dá ~186 mil registros por shard antes de estourar os 10 s. O plano previa particionar por `scope` + mês; isso é conservador por mais de uma ordem de grandeza. Proposta: particionar só por `scope`, com divisão por mês acionada apenas acima de 50 mil registros. Menos shards significa menos código de coordenação e menos superfície de bug.

2. **A decisão de guardar o embedding dentro do envelope do registro está validada** e passa a ser obrigatória, não opcional. É ela que faz o rebuild ser leitura + insert, sem re-embedar. Se o vetor não estivesse no registro, todo rebuild exigiria passar o shard inteiro pelo modelo de embedding e a deleção barata desapareceria.

---

## Medição extra: custo de desbloqueio (Argon2id)

Não estava nos spikes, mas é o número de UX que o perfil de cifra impõe: quanto o usuário espera ao abrir o cofre.

| Parâmetros | Tempo de derivação |
|---|---|
| m=64 MiB, t=3, p=4 | 86 ms |
| m=128 MiB, t=3, p=4 | 151 ms |
| **m=256 MiB, t=3, p=4** (contrato) | **468 ms** |
| m=512 MiB, t=3, p=4 | 906 ms |

468 ms de espera única por sessão é aceitável e mantém o custo de ataque por dicionário alto. **Os parâmetros de contrato ficam como estão** — nenhuma mudança necessária.

---

## Estado do registro de riscos após a semana 1

| Risco (plano §15) | Estado |
|---|---|
| Cifra por registro mata a latência | **Descartado** — S1 mediu +2,4 ms de sobrecarga mediana |
| Rebuild caro demais para deleção padrão | **Descartado** — S3 mediu 0,27 s, 37× abaixo do limiar |
| Embedding local insuficiente | **Em aberto** — S2 bloqueado por política de rede; precisa fechar antes da semana 3 |
| Extração de fatos por LLM local é ruim demais | Em aberto — avaliação prevista para a Fase 1 |
| Fricção da classificação afasta usuários | Em aberto — só mensurável no piloto |

## O que já existe de código

Não é protótipo descartável: os dois módulos abaixo são entregáveis da Fase 0, escritos com as primitivas de produção.

- `arca/crypto/kdf.py` — Argon2id com os parâmetros de contrato, versionados
- `arca/crypto/envelope.py` — envelope AES-256-GCM, DEK por registro, AAD amarrando o ciphertext ao `record_id` e à versão do esquema
- `bench/spikes/` — os dois harnesses, reexecutáveis

## Próximo passo

Fase 0 (semanas 1–2) pode começar: keyring com Secure Enclave/TPM, recuperação BIP39 + Shamir, vault com escrita atômica e git, audit log encadeado, servidor MCP mínimo. A única dependência externa em aberto é o desbloqueio do S2 antes da semana 3.
